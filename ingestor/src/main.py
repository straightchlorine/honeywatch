from __future__ import annotations

import logging
import os
import signal
import sys
import time
from collections.abc import Iterator

from src.config import Config
from src.parser import parse_event
from src.writer import EventWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def tail_follow(path: str) -> Iterator[str]:
    """Tail-follow a file, handling rotation and truncation."""
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
                        except OSError:
                            pass

                        time.sleep(0.1)
        except FileNotFoundError:
            logger.warning("Log file %s not found, retrying in 1s...", path)
            time.sleep(1.0)


def main() -> None:
    config = Config.from_env()
    logger.info("Starting ingestor, watching %s", config.log_path)

    writer = EventWriter(config.conninfo)

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("Received signal %d, shutting down", signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        for line in tail_follow(config.log_path):
            event = parse_event(line)
            if event is not None:
                try:
                    writer.write_event(event)
                except Exception:
                    logger.exception("Failed to write event")
    finally:
        writer.close()
        logger.info("Ingestor shut down")


if __name__ == "__main__":
    main()
