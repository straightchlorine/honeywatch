from __future__ import annotations

import logging
import os
import signal
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import psycopg

from src.config import Config
from src.parser import parse_event
from src.writer import EventWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Per-event retry budget. Three attempts at 1s, 2s, 4s gives a total
# bounded wait of ~7s before declaring failure and dead-lettering.
_RETRY_ATTEMPTS = 3
_RETRY_INITIAL_BACKOFF = 1.0

# Process-level circuit breaker. After this many consecutive failures
# (Postgres down, network partition, etc.) sleep instead of grinding.
_CIRCUIT_BREAKER_THRESHOLD = 50
_CIRCUIT_BREAKER_SLEEP = 30.0

# Dead-letter file collects raw cowrie lines that exhausted the retry budget.
_DEADLETTER_PATH = Path("/tmp/deadletter.jsonl")


def tail_follow(path: str) -> Iterator[str]:
    """Tail a file from its current end, handling rotation and truncation.

    Args:
        path: Filesystem path to follow.

    Yields:
        Each new non-empty line appended to the file, indefinitely.
    """
    while True:
        try:
            with open(path) as f:
                # Seek to end - only process new events
                f.seek(0, os.SEEK_END)
                logger.info("Opened %s, seeking to end (position %d)", path, f.tell())

                while True:
                    line = f.readline()
                    if line:
                        line = line.strip()
                        if line:
                            yield line
                    else:
                        # Check for file rotation or truncation
                        try:
                            current_stat = os.stat(path)
                            fd_stat = os.fstat(f.fileno())

                            # File was replaced (different inode)
                            if current_stat.st_ino != fd_stat.st_ino:
                                logger.info("File rotated, reopening from beginning")
                                break

                            # File was truncated (current position > file size)
                            if f.tell() > fd_stat.st_size:
                                logger.info("File truncated, seeking to beginning")
                                f.seek(0)
                                continue
                        except OSError as exc:
                            # Stat can race with rotation (file briefly missing).
                            # Log and fall through to sleep; next iteration retries.
                            logger.debug("stat failed on %s: %s", path, exc)

                        time.sleep(0.1)
        except FileNotFoundError:
            logger.warning("Log file %s not found, retrying in 1s...", path)
            time.sleep(1.0)


def _dead_letter(raw: str) -> None:
    """Append a raw cowrie line to the dead-letter file."""
    try:
        with _DEADLETTER_PATH.open("a", encoding="utf-8") as f:
            f.write(raw + "\n")
    except OSError:
        logger.exception("failed to append to dead-letter file %s", _DEADLETTER_PATH)


def main() -> None:
    """Run the ingestor event loop until interrupted."""
    config = Config.from_env()
    logger.info("Starting ingestor, watching %s", config.log_path)

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("Received signal %d, shutting down", signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    consecutive_failures = 0
    try:
        with EventWriter(config.conninfo) as writer:
            for line in tail_follow(config.log_path):
                # Log the full raw event first so unhandled event types are
                # still visible.
                logger.info("cowrie event: %s", line)
                event = parse_event(line)
                if event is None:
                    continue
                logger.debug("parsed as %s", type(event).__name__)

                tripped_breaker = False
                backoff = _RETRY_INITIAL_BACKOFF
                for attempt in range(1, _RETRY_ATTEMPTS + 1):
                    try:
                        writer.write_event(event)
                        Path("/tmp/healthy").touch()
                        consecutive_failures = 0
                        break
                    except psycopg.Error:
                        if attempt == _RETRY_ATTEMPTS:
                            logger.exception(
                                "Failed to write event after %d attempts; "
                                "appending to %s",
                                _RETRY_ATTEMPTS,
                                _DEADLETTER_PATH,
                            )
                            _dead_letter(line)
                            consecutive_failures += 1
                            tripped_breaker = (
                                consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD
                            )
                            break
                        logger.warning(
                            "psycopg error on attempt %d/%d, retrying in %.0fs",
                            attempt,
                            _RETRY_ATTEMPTS,
                            backoff,
                        )
                        time.sleep(backoff)
                        backoff *= 2
                    except (ValueError, TypeError):
                        # Programming error/malformed event - non-recoverable
                        logger.exception("Failed to write event")
                        break

                if tripped_breaker:
                    logger.warning(
                        "circuit breaker: %d consecutive failures, sleeping %.0fs",
                        consecutive_failures,
                        _CIRCUIT_BREAKER_SLEEP,
                    )
                    time.sleep(_CIRCUIT_BREAKER_SLEEP)
                    consecutive_failures = 0
    finally:
        logger.info("Ingestor shut down")


if __name__ == "__main__":
    main()
