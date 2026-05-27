"""Tests for `tail_follow` rotation, truncation, and missing-file paths.

A background thread mutates the file while the main thread consumes from
the iterator. Hard timeouts on every assertion prevent test hangs.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from src.tail import tail_follow


def _drain_next(it: Iterator[str], timeout: float = 5.0) -> str:
    """Pull the next line from `it` or fail with a deadline."""
    box: list[str | BaseException] = []

    def pump() -> None:
        try:
            box.append(next(it))
        except BaseException as exc:
            box.append(exc)

    t = threading.Thread(target=pump, daemon=True)
    t.start()
    t.join(timeout)
    if not box:
        pytest.fail(f"tail_follow did not yield within {timeout}s")
    item = box[0]
    if isinstance(item, BaseException):
        raise item
    return item


def _spawn_writer(fn: Callable[[], None]) -> threading.Thread:
    t = threading.Thread(target=fn, daemon=True)
    t.start()
    return t


def test_tail_yields_appended_lines(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    path.write_text("")
    it = tail_follow(str(path), poll_interval=0.01)

    def appender() -> None:
        time.sleep(0.05)
        with path.open("a") as f:
            f.write("hello\n")
            f.flush()

    _spawn_writer(appender)
    assert _drain_next(it) == "hello"


def test_tail_handles_rotation(tmp_path: Path) -> None:
    """Replacing the file (new inode) reopens and yields lines written after."""
    path = tmp_path / "log.jsonl"
    path.write_text("")
    it = tail_follow(str(path), poll_interval=0.01)

    def rotate_then_append() -> None:
        time.sleep(0.1)
        # Logrotate-style: rename old, recreate empty, append after tail reopens.
        os.rename(path, tmp_path / "log.jsonl.1")
        path.touch()
        time.sleep(0.5)  # let tail notice inode change + reopen
        with path.open("a") as f:
            f.write("post-rotate\n")
            f.flush()

    _spawn_writer(rotate_then_append)
    assert _drain_next(it, timeout=3.0) == "post-rotate"


def test_tail_handles_truncation(tmp_path: Path) -> None:
    """Truncating the file in place (same inode) seeks to 0 and resumes."""
    path = tmp_path / "log.jsonl"
    path.write_text("first\n")
    it = tail_follow(str(path), poll_interval=0.01)

    def truncate_then_append() -> None:
        time.sleep(0.1)
        # Empty the file (same inode), then give tail time to seek(0).
        path.open("w").close()
        time.sleep(0.5)
        with path.open("a") as f:
            f.write("post-trunc\n")
            f.flush()

    _spawn_writer(truncate_then_append)
    assert _drain_next(it, timeout=3.0) == "post-trunc"


def test_tail_retries_when_file_missing(tmp_path: Path) -> None:
    """File appears later - tail must not crash, just keep retrying."""
    path = tmp_path / "log.jsonl"
    # tail_follow's missing-file retry sleeps 1s; reopen then seeks to EOF -
    # so we need to keep appending until the consumer is reading the file.
    it = tail_follow(str(path), poll_interval=0.01)

    def create_then_append() -> None:
        time.sleep(0.1)
        path.touch()
        # Let tail's 1s missing-file backoff elapse and the open() succeed.
        time.sleep(1.5)
        with path.open("a") as f:
            f.write("late\n")
            f.flush()

    _spawn_writer(create_then_append)
    assert _drain_next(it, timeout=5.0) == "late"


def test_tail_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    path.write_text("")
    it = tail_follow(str(path), poll_interval=0.01)

    def writer() -> None:
        time.sleep(0.05)
        with path.open("a") as f:
            f.write("\n\nreal\n")
            f.flush()

    _spawn_writer(writer)
    assert _drain_next(it) == "real"
