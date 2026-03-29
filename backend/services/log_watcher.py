"""
log_watcher.py — Real-time OS log ingestion service.

Watches OS log sources and feeds new lines into the AgentSOC pipeline.
Supports:
  - Windows Event Log  (via pywin32 — install: pip install pywin32)
  - Linux journald     (via systemd.journal — install: pip install systemd-python)
  - Log files          (via watchdog — install: pip install watchdog)
  - /var/log/syslog    (tail-style, no extra deps)

Usage (from main.py lifespan):
    from services.log_watcher import LogWatcherService
    watcher = LogWatcherService(db_factory, broadcast_fn)
    await watcher.start()
    ...
    await watcher.stop()
"""

import asyncio
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# Maximum log lines queued before dropping (backpressure)
QUEUE_MAXSIZE = 500


class LogWatcherService:
    """
    Orchestrates one or more OS log sources.
    Each source pushes raw log strings into a shared asyncio.Queue.
    A consumer coroutine drains the queue through process_log_event.
    """

    def __init__(
        self,
        db_factory,            # async context manager that yields an AsyncSession
        broadcast_fn: Callable[..., Awaitable[None]],   # ws_manager.broadcast
        sources: list[str] | None = None,               # override auto-detect
    ):
        self._db_factory = db_factory
        self._broadcast = broadcast_fn
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._sources = sources or self._auto_detect_sources()

    # ─── Public API ────────────────────────────────────────────────────────────

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info(f"LogWatcher starting with sources: {self._sources}")

        # Start one reader task per source
        for source in self._sources:
            task = asyncio.create_task(self._run_source(source), name=f"watcher:{source}")
            self._tasks.append(task)

        # Start the consumer that processes queued logs
        consumer = asyncio.create_task(self._consume(), name="watcher:consumer")
        self._tasks.append(consumer)

    async def stop(self):
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("LogWatcher stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    # ─── Source router ─────────────────────────────────────────────────────────

    async def _run_source(self, source: str):
        try:
            if source == "windows_event":
                await self._watch_windows_event_log()
            elif source == "journald":
                await self._watch_journald()
            elif source.startswith("file:"):
                path = source[5:]
                await self._tail_file(path)
            elif source == "syslog":
                await self._tail_file("/var/log/syslog")
            elif source == "auth_log":
                await self._tail_file("/var/log/auth.log")
            else:
                logger.warning(f"Unknown log source: {source}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Log source '{source}' crashed: {e}", exc_info=True)

    # ─── OS-specific readers ───────────────────────────────────────────────────

    async def _watch_windows_event_log(self):
        """
        Read Windows Security/System/Application event logs in real time.
        Requires: pip install pywin32
        """
        try:
            import win32evtlog
            import win32evtlogutil
            import win32con
            import pywintypes
        except ImportError:
            logger.error(
                "pywin32 not installed. Run: pip install pywin32\n"
                "Then run: python Scripts/pywin32_postinstall.py -install"
            )
            return

        channels = ["Security", "System", "Application"]
        handles = {}
        for ch in channels:
            try:
                handles[ch] = win32evtlog.OpenEventLog(None, ch)
            except Exception as e:
                logger.warning(f"Cannot open Windows Event Log '{ch}': {e}")

        logger.info(f"Watching Windows Event Log channels: {list(handles.keys())}")

        while self._running:
            for ch, handle in handles.items():
                try:
                    flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
                    events = win32evtlog.ReadEventLog(handle, flags, 0)
                    for ev in (events or []):
                        try:
                            msg = win32evtlogutil.SafeFormatMessage(ev, ch)
                            if msg:
                                line = f"[{ch}] EventID={ev.EventID} {msg.strip()}"
                                await self._enqueue(line)
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug(f"Event log read error ({ch}): {e}")
            await asyncio.sleep(2)

    async def _watch_journald(self):
        """
        Tail systemd journal in real time.
        Requires: pip install systemd-python  (Linux only)
        """
        try:
            from systemd import journal
        except ImportError:
            logger.error(
                "systemd-python not installed. Run: pip install systemd-python\n"
                "Note: only works on Linux with systemd."
            )
            return

        logger.info("Watching systemd journald...")
        j = journal.Reader()
        j.log_level(journal.LOG_INFO)
        j.seek_tail()
        j.get_previous()   # skip to end

        while self._running:
            j.wait(timeout=2000)    # ms
            for entry in j:
                msg = entry.get("MESSAGE", "")
                unit = entry.get("_SYSTEMD_UNIT", "")
                pid = entry.get("_PID", "")
                if msg:
                    line = f"[journald] unit={unit} pid={pid} {msg}"
                    await self._enqueue(line)
            await asyncio.sleep(0.1)

    async def _tail_file(self, path: str):
        """
        Tail a log file, yielding new lines as they are appended.
        Works on any platform, no dependencies beyond stdlib.
        """
        p = Path(path)
        if not p.exists():
            logger.warning(f"Log file not found, will retry: {path}")
            # Wait for file to appear (e.g. log rotation)
            while self._running and not p.exists():
                await asyncio.sleep(5)
            if not self._running:
                return

        logger.info(f"Tailing log file: {path}")

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)    # seek to end
            while self._running:
                line = f.readline()
                if line:
                    stripped = line.strip()
                    if stripped:
                        await self._enqueue(stripped)
                else:
                    await asyncio.sleep(0.25)

                # Handle log rotation (file replaced)
                try:
                    if os.stat(path).st_ino != os.fstat(f.fileno()).st_ino:
                        logger.info(f"Log rotation detected: {path}")
                        break   # outer _run_source will restart
                except Exception:
                    pass

    # ─── Queue helpers ─────────────────────────────────────────────────────────

    async def _enqueue(self, log_text: str):
        try:
            self._queue.put_nowait(log_text)
        except asyncio.QueueFull:
            logger.warning("Log queue full — dropping oldest entry")
            try:
                self._queue.get_nowait()   # drop oldest
                self._queue.put_nowait(log_text)
            except Exception:
                pass

    # ─── Consumer ──────────────────────────────────────────────────────────────

    async def _consume(self):
        """
        Drains the queue and runs each log through the full AgentSOC pipeline.
        Broadcasts results to all connected WebSocket clients.
        """
        from services.ingestion import process_log_event

        logger.info("LogWatcher consumer started.")
        while self._running:
            try:
                log_text = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                async with self._db_factory() as db:
                    result = await process_log_event(
                        db=db,
                        log_text=log_text,
                        source_ip=None,
                        include_explanation=False,   # fast path — no LLM for live logs
                        include_similar=False,
                        add_similarity=True,
                    )

                # Broadcast to all WS clients
                await self._broadcast("new_alert", {
                    "id": result["id"],
                    "log_text": result["log_text"][:200],
                    "label": result["label"],
                    "confidence": result["confidence"],
                    "risk_score": result["risk_score"],
                    "risk_tier": result["risk_tier"],
                    "source_ip": result["source_ip"],
                    "timestamp": result["timestamp"].isoformat(),
                    "chain_count": result["chain_count"],
                })

                if result["risk_tier"] in ("CRITICAL", "HIGH"):
                    logger.warning(
                        f"[LiveLog] {result['risk_tier']} alert: "
                        f"{result['label']} from {result['source_ip']}"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"LogWatcher consumer error: {e}", exc_info=True)

        logger.info("LogWatcher consumer stopped.")

    # ─── Auto-detect ───────────────────────────────────────────────────────────

    @staticmethod
    def _auto_detect_sources() -> list[str]:
        system = platform.system()
        sources = []

        if system == "Windows":
            sources.append("windows_event")
        elif system == "Linux":
            # Prefer journald if available
            try:
                import systemd.journal  # noqa: F401
                sources.append("journald")
            except ImportError:
                pass

            # Also tail common log files
            for log_path in ["/var/log/auth.log", "/var/log/syslog", "/var/log/messages"]:
                if Path(log_path).exists():
                    sources.append(f"file:{log_path}")
        elif system == "Darwin":    # macOS
            if Path("/var/log/system.log").exists():
                sources.append("file:/var/log/system.log")

        if not sources:
            logger.warning(
                "No OS log sources auto-detected. "
                "Pass explicit sources= to LogWatcherService, e.g. sources=['file:/var/log/syslog']"
            )

        return sources