"""Tests for `tail_follow` rotation, truncation, and missing-file paths.

A background thread mutates the file while the main thread consumes from
the iterator. Hard timeouts on every assertion prevent test hangs.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from prometheus_client import REGISTRY

from src.tail import MAX_LINE_BYTES, tail_follow


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


def _dropped(reason: str) -> float:
    return (
        REGISTRY.get_sample_value("ingestor_events_dropped_total", {"reason": reason})
        or 0.0
    )


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


def test_tail_drops_oversize_line(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "log.jsonl"
    path.write_text("")
    before = _dropped("oversize_line")
    it = tail_follow(str(path), poll_interval=0.01)

    def writer() -> None:
        time.sleep(0.05)
        with path.open("a") as f:
            f.write("x" * (MAX_LINE_BYTES * 2) + "\n")
            f.write("after-oversize\n")
            f.flush()

    with caplog.at_level(logging.WARNING, logger="src.tail"):
        _spawn_writer(writer)
        assert _drain_next(it, timeout=5.0) == "after-oversize"

    assert _dropped("oversize_line") >= before + 1
    assert any("oversize line" in r.message for r in caplog.records)


def test_tail_drops_oversize_at_eof_without_newline(tmp_path: Path) -> None:
    """Oversize line with no trailing newline still drains cleanly to EOF."""
    path = tmp_path / "log.jsonl"
    path.write_text("")
    before = _dropped("oversize_line")
    it = tail_follow(str(path), poll_interval=0.01)

    def writer() -> None:
        time.sleep(0.05)
        with path.open("a") as f:
            f.write("x" * (MAX_LINE_BYTES + 100))  # no trailing newline
            f.flush()
        time.sleep(0.2)
        with path.open("a") as f:
            f.write("\nrecovered\n")
            f.flush()

    _spawn_writer(writer)
    assert _drain_next(it, timeout=5.0) == "recovered"
    assert _dropped("oversize_line") >= before + 1


def test_tail_abandons_drain_when_no_newline_ever_arrives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never-newline stream must hit MAX_DRAIN_BYTES cap and seek to EOF."""
    # Shrink the drain cap so the test stays cheap.
    monkeypatch.setattr("src.tail.MAX_DRAIN_BYTES", 64 * 1024)

    path = tmp_path / "log.jsonl"
    path.write_text("")
    before_abandon = _dropped("oversize_drain_abandoned")
    before_oversize = _dropped("oversize_line")
    it = tail_follow(str(path), poll_interval=0.01)

    def writer() -> None:
        time.sleep(0.05)
        with path.open("a") as f:
            # 2 * MAX_LINE_BYTES of no-newline data: triggers oversize then
            # exceeds the shrunken drain cap.
            f.write("y" * (2 * MAX_LINE_BYTES))
            f.flush()
        time.sleep(0.5)
        with path.open("a") as f:
            f.write("\nlive-resumed\n")
            f.flush()

    _spawn_writer(writer)
    assert _drain_next(it, timeout=10.0) == "live-resumed"
    assert _dropped("oversize_line") >= before_oversize + 1
    assert _dropped("oversize_drain_abandoned") >= before_abandon + 1


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


def test_tail_survives_invalid_utf8(tmp_path: Path) -> None:
    """Attacker-controlled bytes must not raise UnicodeDecodeError."""
    path = tmp_path / "log.jsonl"
    path.write_text("")
    it = tail_follow(str(path), poll_interval=0.01)

    def writer() -> None:
        time.sleep(0.05)
        with path.open("ab") as f:
            f.write(b"\xff\xfe\xfdbad\n")
            f.write(b"good\n")
            f.flush()

    _spawn_writer(writer)
    # First line decodes with replacement chars; either accept or skip - but
    # tail must NOT crash. We assert the clean follow-up arrives.
    first = _drain_next(it, timeout=5.0)
    if first != "good":
        second = _drain_next(it, timeout=5.0)
        assert second == "good"
