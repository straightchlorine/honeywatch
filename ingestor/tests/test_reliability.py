"""Unit tests for `Retry`, `Fuse`, and `Writer`.

Sleep is injected so tests run in milliseconds and pin the exact backoff
sequence.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from unittest.mock import MagicMock

import psycopg
import pytest

from src.events import LoginFailed
from src.reliability import (
    Fuse,
    Outcome,
    Retry,
    Writer,
)


def _make_recorder() -> tuple[Callable[[float], None], list[float]]:
    calls: list[float] = []

    def sleep(s: float) -> None:
        calls.append(s)

    return sleep, calls


def test_retry_policy_zero_attempts_rejected() -> None:
    with pytest.raises(ValueError, match="attempts must be >= 1"):
        Retry(attempts=0, initial_backoff=1.0)


def test_retry_policy_success_first_try() -> None:
    sleep, calls = _make_recorder()
    policy = Retry(attempts=3, initial_backoff=1.0, sleep=sleep)
    fn = MagicMock()
    assert policy.run(fn) is Outcome.SUCCESS
    assert fn.call_count == 1
    assert calls == []


def test_retry_policy_exhausts_with_expected_backoff() -> None:
    sleep, calls = _make_recorder()
    policy = Retry(attempts=3, initial_backoff=1.0, sleep=sleep)
    fn = MagicMock(side_effect=psycopg.OperationalError("boom"))
    assert policy.run(fn) is Outcome.RETRY_EXHAUSTED
    assert fn.call_count == 3
    # Two sleeps between three attempts; backoff doubles each time.
    assert calls == [1.0, 2.0]


def test_retry_policy_value_error_is_fatal() -> None:
    sleep, calls = _make_recorder()
    policy = Retry(attempts=3, initial_backoff=1.0, sleep=sleep)
    fn = MagicMock(side_effect=ValueError("bad shape"))
    assert policy.run(fn) is Outcome.FATAL
    assert fn.call_count == 1
    assert calls == []


def test_retry_policy_unexpected_exception_is_fatal() -> None:
    sleep, _ = _make_recorder()
    policy = Retry(attempts=3, initial_backoff=1.0, sleep=sleep)
    fn = MagicMock(side_effect=KeyError("unexpected"))
    assert policy.run(fn) is Outcome.FATAL


def test_retry_policy_eventual_success() -> None:
    sleep, calls = _make_recorder()
    policy = Retry(attempts=5, initial_backoff=0.5, sleep=sleep)
    fn = MagicMock(
        side_effect=[psycopg.OperationalError(), psycopg.OperationalError(), None]
    )
    assert policy.run(fn) is Outcome.SUCCESS
    assert fn.call_count == 3
    assert calls == [0.5, 1.0]


def test_fuse_blows_at_threshold_and_probe_succeeds_first() -> None:
    sleep, calls = _make_recorder()
    probe = MagicMock(return_value=True)
    fuse = Fuse(threshold=3, sleep_seconds=10.0, probe=probe, sleep=sleep)
    fuse.record_failure()
    fuse.record_failure()
    assert not fuse.open
    fuse.record_failure()  # threshold reached -> trip + probe + close
    assert not fuse.open
    assert fuse.consecutive_failures == 0
    assert probe.call_count == 1
    assert calls == [10.0]


def test_fuse_probe_retries_with_exp_backoff_until_healthy() -> None:
    sleep, calls = _make_recorder()
    # Probe fails twice then succeeds.
    probe = MagicMock(side_effect=[False, False, True])
    fuse = Fuse(threshold=1, sleep_seconds=5.0, probe=probe, sleep=sleep)
    fuse.record_failure()  # trip immediately
    assert not fuse.open
    assert probe.call_count == 3
    # Exp backoff doubling: 5, 10, 20.
    assert calls == [5.0, 10.0, 20.0]


def test_fuse_probe_backoff_caps() -> None:
    sleep, calls = _make_recorder()
    probe = MagicMock(side_effect=[False] * 9 + [True])
    fuse = Fuse(threshold=1, sleep_seconds=200.0, probe=probe, sleep=sleep)
    fuse.record_failure()
    # 200 -> 300 (capped) -> 300 -> ... -> success on 10th probe.
    assert calls[0] == 200.0
    assert calls[1] == 300.0
    assert all(s == 300.0 for s in calls[1:])


def test_fuse_on_wait_fires_once_per_probe_attempt() -> None:
    sleep, _ = _make_recorder()
    on_wait_calls: list[None] = []
    probe = MagicMock(side_effect=[False, False, True])
    fuse = Fuse(
        threshold=1,
        sleep_seconds=5.0,
        probe=probe,
        sleep=sleep,
        on_wait=lambda: on_wait_calls.append(None),
    )
    fuse.record_failure()  # trip immediately
    assert not fuse.open
    assert probe.call_count == 3
    assert len(on_wait_calls) == 3


def test_fuse_without_on_wait_still_works() -> None:
    # on_wait defaults to None for backward compatibility.
    sleep, _ = _make_recorder()
    probe = MagicMock(return_value=True)
    fuse = Fuse(threshold=1, sleep_seconds=1.0, probe=probe, sleep=sleep)
    fuse.record_failure()
    assert not fuse.open


def test_fuse_record_success_clears_state() -> None:
    sleep, _ = _make_recorder()
    fuse = Fuse(threshold=5, sleep_seconds=1.0, probe=lambda: True, sleep=sleep)
    fuse.record_failure()
    fuse.record_failure()
    assert fuse.consecutive_failures == 2
    fuse.record_success()
    assert fuse.consecutive_failures == 0
    assert not fuse.open


def _event() -> LoginFailed:
    return LoginFailed(
        session_id="sess-rel-1",
        username="root",
        password="x",
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )


def test_writer_happy_path_resets_fuse() -> None:
    sleep, _ = _make_recorder()
    event_writer = MagicMock()
    retry = Retry(attempts=3, initial_backoff=1.0, sleep=sleep)
    fuse = Fuse(threshold=5, sleep_seconds=1.0, probe=lambda: True, sleep=sleep)
    fuse.record_failure()  # pre-seed a failure
    writer = Writer(event_writer, retry, fuse)

    assert writer.write(_event(), "raw") is Outcome.SUCCESS
    assert fuse.consecutive_failures == 0


def test_writer_exhaustion_counts_toward_fuse() -> None:
    sleep, _ = _make_recorder()
    event_writer = MagicMock()
    event_writer.write_event.side_effect = psycopg.OperationalError("boom")
    probe = MagicMock(return_value=True)
    retry = Retry(attempts=2, initial_backoff=0.5, sleep=sleep)
    fuse = Fuse(threshold=10, sleep_seconds=1.0, probe=probe, sleep=sleep)
    writer = Writer(event_writer, retry, fuse)

    assert writer.write(_event(), "raw") is Outcome.RETRY_EXHAUSTED
    assert fuse.consecutive_failures == 1


def test_writer_fatal_does_not_count_toward_fuse() -> None:
    """FATAL = bug/schema drift, not backend health -> fuse not tripped."""
    sleep, _ = _make_recorder()
    event_writer = MagicMock()
    event_writer.write_event.side_effect = ValueError("bug")
    retry = Retry(attempts=3, initial_backoff=1.0, sleep=sleep)
    fuse = Fuse(threshold=10, sleep_seconds=1.0, probe=lambda: True, sleep=sleep)
    writer = Writer(event_writer, retry, fuse)

    assert writer.write(_event(), "raw") is Outcome.FATAL
    assert fuse.consecutive_failures == 0


def test_writer_sanitizes_raw_in_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Attacker-controlled bytes in raw_line must not reach log sink raw."""
    sleep, _ = _make_recorder()
    event_writer = MagicMock()
    event_writer.write_event.side_effect = psycopg.OperationalError("boom")
    retry = Retry(attempts=1, initial_backoff=1.0, sleep=sleep)
    fuse = Fuse(threshold=10, sleep_seconds=1.0, probe=lambda: True, sleep=sleep)
    writer = Writer(event_writer, retry, fuse)

    raw_with_escape = "X\x1b[31mFAKE\nLOG_INJECT"
    with caplog.at_level("ERROR", logger="src.reliability"):
        writer.write(_event(), raw_with_escape)

    msg = " ".join(r.message for r in caplog.records)
    assert "\x1b" not in msg
    assert "\n" not in msg
    assert "\\x1b" in msg
