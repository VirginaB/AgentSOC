"""
dataset_replayer.py — Simulated live log stream.

Loads a random sample from the SIEVE dataset CSVs and replays one log
per second as a UDP syslog packet to the local SyslogReceiver.

Packet format (RFC 3164):
    <14>Apr 15 10:00:01 siemsim agentsoc: {log_text}

The replayer shuffles its sample pool on each start so every run
produces a different sequence.
"""

import asyncio
import csv
import logging
import random
import socket
import struct
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to dataset directory (relative to this file: ../../dataset/)
_DATASET_DIR = Path(__file__).parent.parent.parent / "dataset"

# How many rows to sample per CSV file (6 files × 5 000 = 30 000 total)
_ROWS_PER_FILE = 100

# Syslog PRI: facility=1 (user-level), severity=6 (informational) → 14
_SYSLOG_PRI = 14


def _build_syslog_packet(log_text: str) -> bytes:
    """Wrap a log message in an RFC 3164 syslog header."""
    now = datetime.now(timezone.utc)
    # RFC 3164 timestamp has no year and single-space-pads day < 10
    day = f"{now.day:2d}"
    ts = now.strftime(f"%b {day} %H:%M:%S")
    packet = f"<{_SYSLOG_PRI}>{ts} siemsim agentsoc: {log_text}"
    return packet.encode("utf-8", errors="replace")


def _load_sample(dataset_dir: Path) -> list[str]:
    """
    Load a random sample of log lines from every SIEVE CSV in dataset_dir.
    Returns a flat list of raw log strings (no labels — the pipeline classifies them).
    """
    csv_files = sorted(dataset_dir.glob("SIEVE_*.csv"))
    if not csv_files:
        logger.warning(f"No SIEVE_*.csv files found in {dataset_dir}")
        return []

    logs: list[str] = []
    for csv_path in csv_files:
        try:
            with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                rows = [row["log"] for row in reader if row.get("log")]

            if not rows:
                continue

            sample_size = min(_ROWS_PER_FILE, len(rows))
            sampled = random.sample(rows, sample_size)
            logs.extend(sampled)
            logger.info(f"Loaded {sample_size} rows from {csv_path.name}")
        except Exception as e:
            logger.warning(f"Could not read {csv_path.name}: {e}")

    random.shuffle(logs)
    logger.info(f"Dataset replayer pool: {len(logs)} log lines loaded.")
    return logs


class DatasetReplayer:
    """
    Sends one random log line per second to the local syslog receiver via UDP.

    Usage:
        replayer = DatasetReplayer(target_host="127.0.0.1", target_port=5140)
        await replayer.start()
        ...
        await replayer.stop()
    """

    def __init__(self, target_host: str = "127.0.0.1", target_port: int = 5140,
                 interval: float = 1.0):
        self._host = target_host
        self._port = target_port
        self._interval = interval
        self._logs: list[str] = []
        self._task: asyncio.Task | None = None
        self._running = False
        self._sent_count = 0

    async def start(self):
        if self._running:
            return

        # Load dataset in a thread so startup stays non-blocking
        self._logs = await asyncio.to_thread(_load_sample, _DATASET_DIR)
        if not self._logs:
            logger.error("DatasetReplayer: no logs loaded — stream will not start.")
            return

        self._running = True
        self._task = asyncio.create_task(self._replay(), name="replayer:stream")
        logger.info(
            "DatasetReplayer started — sending to %s:%d every %.1fs",
            self._host, self._port, self._interval,
        )

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("DatasetReplayer stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Replay loop ────────────────────────────────────────────────────────────

    async def _replay(self):
        """
        Cycles through the shuffled log pool indefinitely, sending one
        packet per interval. Re-shuffles the pool each full cycle to vary
        the sequence without repeating patterns.
        """
        pool = list(self._logs)
        idx = 0

        # Create a UDP socket for sending (one socket, reused each tick)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            while self._running:
                log_text = pool[idx % len(pool)]
                idx += 1

                # Re-shuffle at the start of each full cycle
                if idx % len(pool) == 0:
                    random.shuffle(pool)

                packet = _build_syslog_packet(log_text)
                try:
                    sock.sendto(packet, (self._host, self._port))
                    self._sent_count += 1
                    if self._sent_count <= 3 or self._sent_count % 25 == 0:
                        logger.info(
                            "DatasetReplayer sent packet #%d to %s:%d",
                            self._sent_count, self._host, self._port,
                        )
                except Exception as e:
                    logger.warning(f"DatasetReplayer send error: {e}")

                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            pass
        finally:
            sock.close()
