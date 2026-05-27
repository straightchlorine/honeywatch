"""Tail a file with rotation + truncation awareness.

Yields each newly-appended line indefinitely. Starts at EOF so the ingestor
never re-reads history on restart; the source-of-truth log file on disk is
the recovery surface.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator

logger = logging.getLogger(__name__)


def tail_follow(path: str, poll_interval: float = 0.1) -> Iterator[str]:
    """Tail `path` from EOF, handling rotation and truncation.

    Args:
        path: Filesystem path to follow.
        poll_interval: Seconds to sleep between read attempts at EOF.

    Yields:
        Each new non-empty line appended to the file, indefinitely.
    """
    while True:
        try:
            with open(path) as f:
                f.seek(0, os.SEEK_END)
                logger.info("Opened %s, seeking to end (position %d)", path, f.tell())

                while True:
                    line = f.readline()
                    if line:
                        line = line.strip()
                        if line:
                            yield line
                        continue

                    try:
                        current_stat = os.stat(path)
                        fd_stat = os.fstat(f.fileno())

                        # File replaced (different inode) - re-open from start.
                        if current_stat.st_ino != fd_stat.st_ino:
                            logger.info("File rotated, reopening from beginning")
                            break

                        # File truncated - seek back to 0 and keep going.
                        if f.tell() > fd_stat.st_size:
                            logger.info("File truncated, seeking to beginning")
                            f.seek(0)
                            continue
                    except OSError as exc:
                        # stat() can race with rotation (file briefly missing).
                        logger.debug("stat failed on %s: %s", path, exc)

                    time.sleep(poll_interval)
        except FileNotFoundError:
            logger.warning("Log file %s not found, retrying in 1s...", path)
            time.sleep(1.0)
