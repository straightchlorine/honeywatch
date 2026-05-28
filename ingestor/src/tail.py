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
from typing import TextIO

from src import metrics

logger = logging.getLogger(__name__)

# 1 MiB cap; legit cowrie events << 64 KiB. Bounds memory on attacker TTY payload.
MAX_LINE_BYTES = 1_048_576
# Abandon drain after this many bytes per oversize line; seek to EOF instead.
MAX_DRAIN_BYTES = 64 * 1024 * 1024


def tail_follow(path: str, poll_interval: float = 0.1) -> Iterator[str]:
    """Tail `path` from EOF, handling rotation and truncation.

    Lines over `MAX_LINE_BYTES` are dropped and counted in metrics. Drain
    of the offending tail is itself capped by `MAX_DRAIN_BYTES`; on cap
    the file is seeked to EOF and a separate metric is incremented.
    """
    while True:
        try:
            # errors="replace": attacker bytes must not raise UnicodeDecodeError
            # and kill the producer thread.
            with open(path, encoding="utf-8", errors="replace") as f:
                f.seek(0, os.SEEK_END)
                logger.info("Opened %s, seeking to end (position %d)", path, f.tell())

                while True:
                    try:
                        line = f.readline(MAX_LINE_BYTES)
                    except OSError as exc:
                        logger.warning(
                            "tail: read error on %s: %s; reopening", path, exc
                        )
                        break
                    if line:
                        if not line.endswith("\n"):
                            try:
                                drained_ok = _drain_oversize(f)
                            except OSError as exc:
                                logger.warning(
                                    "tail: read error draining %s: %s; reopening",
                                    path,
                                    exc,
                                )
                                break
                            metrics.events_dropped_total.labels(
                                reason="oversize_line"
                            ).inc()
                            if not drained_ok:
                                metrics.events_dropped_total.labels(
                                    reason="oversize_drain_abandoned"
                                ).inc()
                                logger.warning(
                                    "tail: abandoned drain after %d MiB on %s",
                                    MAX_DRAIN_BYTES // (1 << 20),
                                    path,
                                )
                            else:
                                logger.warning(
                                    "tail: dropped oversize line (>%d bytes) from %s",
                                    MAX_LINE_BYTES,
                                    path,
                                )
                            continue
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
        except OSError as exc:
            logger.warning("tail: open failed for %s: %s; retrying in 1s", path, exc)
            time.sleep(1.0)


def _drain_oversize(f: TextIO) -> bool:
    """Skip remainder of an oversize line up to newline/EOF.

    Returns True on clean drain. Returns False (and seeks to EOF) if more
    than MAX_DRAIN_BYTES were consumed without finding a newline - prevents
    an attacker piping a never-newline stream from stalling the producer.
    """
    drained = 0
    while drained < MAX_DRAIN_BYTES:
        chunk = f.readline(MAX_LINE_BYTES)
        if not chunk:
            return True
        drained += len(chunk)
        if chunk.endswith("\n"):
            return True
    f.seek(0, os.SEEK_END)
    return False
