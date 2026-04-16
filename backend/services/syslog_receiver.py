"""
syslog_receiver.py — Local UDP syslog server.

Listens on UDP port 5140 (non-privileged syslog port).
Accepts RFC 3164 syslog packets, strips the header, and feeds the
raw log message into the AgentSOC analysis pipeline.

RFC 3164 packet format:
    <PRI>TIMESTAMP HOSTNAME TAG: MESSAGE
    <14>Apr 15 10:00:01 siemsim agentsoc: Failed password for root from 10.0.0.1...
"""

import asyncio
import logging
import re
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# Matches the RFC 3164 syslog header:
#   <14>Apr 15 10:00:01 siemsim agentsoc:
_SYSLOG_HDR = re.compile(
    r"^<\d+>"                     # <PRI>
    r"[A-Z][a-z]{2}\s+\d{1,2}\s+"  # Month Day
    r"\d{2}:\d{2}:\d{2}\s+"        # HH:MM:SS
    r"\S+\s+"                       # HOSTNAME
    r"\S+:\s*"                      # TAG:
)

QUEUE_MAXSIZE = 500


def _parse_message(raw: str) -> str | None:
    """Strip RFC 3164 header and return the log message, or None if empty."""
    text = raw.strip()
    if not text:
        return None
    m = _SYSLOG_HDR.match(text)
    msg = text[m.end():].strip() if m else text
    return msg if msg else None


class _SyslogProtocol(asyncio.DatagramProtocol):
    """asyncio UDP protocol: receives datagrams and enqueues log messages."""

    def __init__(self, queue: asyncio.Queue):
        self._queue = queue

    def datagram_received(self, data: bytes, addr: tuple):
        try:
            raw = data.decode("utf-8", errors="replace")
        except Exception:
            return
        msg = _parse_message(raw)
        if not msg:
            return
        try:
            self._queue.put_nowait(msg)
        except asyncio.QueueFull:
            # Drop oldest entry to make room
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(msg)
            except Exception:
                pass

    def error_received(self, exc: Exception):
        logger.debug(f"SyslogProtocol error: {exc}")

    def connection_lost(self, exc):
        pass


class SyslogReceiver:
    """
    Manages the UDP syslog server and the consumer that runs logs
    through the AgentSOC pipeline.

    Usage:
        receiver = SyslogReceiver(host, port, db_factory, broadcast_fn)
        await receiver.start()
        ...
        await receiver.stop()
    """

    def __init__(
        self,
        host: str,
        port: int,
        db_factory,
        broadcast_fn: Callable[..., Awaitable[None]],
    ):
        self._host = host
        self._port = port
        self._db_factory = db_factory
        self._broadcast = broadcast_fn
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._transport = None
        self._consumer_task: asyncio.Task | None = None
        self._running = False
        self._processed_count = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    async def start(self):
        if self._running:
            return
        loop = asyncio.get_running_loop()
        try:
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: _SyslogProtocol(self._queue),
                local_addr=(self._host, self._port),
            )
            logger.info(f"Syslog receiver listening on UDP {self._host}:{self._port}")
        except OSError as e:
            logger.error(f"Failed to bind syslog UDP socket on {self._host}:{self._port}: {e}")
            return

        self._running = True
        self._consumer_task = asyncio.create_task(
            self._consume(), name="syslog:consumer"
        )

    async def stop(self):
        self._running = False
        if self._transport:
            self._transport.close()
            self._transport = None
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
        logger.info("Syslog receiver stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    # ── Consumer ───────────────────────────────────────────────────────────────

    async def _consume(self):
        from services.ingestion import process_log_event

        logger.info("Syslog consumer started.")
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
                        include_explanation=False,
                        include_similar=False,
                        add_similarity=True,
                    )

                await self._broadcast("new_alert", {
                    "id":         result["id"],
                    "log_text":   result["log_text"][:200],
                    "label":      result["label"],
                    "confidence": result["confidence"],
                    "risk_score": result["risk_score"],
                    "risk_tier":  result["risk_tier"],
                    "source_ip":  result["source_ip"],
                    "timestamp":  result["timestamp"].isoformat(),
                    "chain_count": result["chain_count"],
                })
                await self._broadcast("stats_refresh", {})
                self._processed_count += 1
                if self._processed_count <= 3 or self._processed_count % 25 == 0:
                    logger.info(
                        "Syslog consumer processed packet #%d -> alert #%d (%s / %s)",
                        self._processed_count,
                        result["id"],
                        result["label"],
                        result["risk_tier"],
                    )

                if result["risk_tier"] in ("CRITICAL", "HIGH"):
                    logger.warning(
                        "[Syslog] %s alert: %s from %s",
                        result["risk_tier"], result["label"], result["source_ip"],
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Syslog consumer error: {e}", exc_info=True)

        logger.info("Syslog consumer stopped.")
