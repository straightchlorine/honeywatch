"""Retry + fuse around `EventWriter.write_event`.

`Writer` glues `Retry` and `Fuse` to the raw `EventWriter`. Both take an
injected `sleep` so tests can pin time; `Fuse` takes an injected `probe`
to verify backend recovery before closing.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import Enum, auto

import psycopg

from src import metrics
from src.events import CowrieEvent
from src.sanitize import sanitize
from src.writer import EventWriter

logger = logging.getLogger(__name__)


class Outcome(Enum):
    SUCCESS = auto()
    RETRY_EXHAUSTED = auto()
    FATAL = auto()


class Retry:
    """Bounded exponential-backoff retry around an idempotent callable.

    Exception classes:
      - `psycopg.Error`            -> retryable
      - `ValueError`, `TypeError`  -> fatal
      - any other `Exception`      -> fatal
    """

    def __init__(
        self,
        attempts: int,
        initial_backoff: float,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be >= 1")
        self._attempts = attempts
        self._initial_backoff = initial_backoff
        self._sleep = sleep

    def run(self, fn: Callable[[], None]) -> Outcome:
        backoff = self._initial_backoff
        for attempt in range(1, self._attempts + 1):
            try:
                fn()
                return Outcome.SUCCESS
            except psycopg.Error:
                if attempt == self._attempts:
                    logger.exception("write failed after %d attempts", self._attempts)
                    return Outcome.RETRY_EXHAUSTED
                logger.warning(
                    "psycopg error on attempt %d/%d, retrying in %.0fs",
                    attempt,
                    self._attempts,
                    backoff,
                )
                self._sleep(backoff)
                backoff *= 2
            except (ValueError, TypeError):
                logger.exception("non-retryable error writing event")
                return Outcome.FATAL
            except Exception:
                logger.exception("unexpected error writing event")
                return Outcome.FATAL
        return Outcome.RETRY_EXHAUSTED


class Fuse:
    """Counts consecutive failures, blows at threshold, probes before closing.

    On blow:
      - sleep `sleep_seconds`, then call `probe()`
      - on success: close, reset counter
      - on failure: sleep again with exponential backoff (cap 5min), reprobe
    """

    _PROBE_BACKOFF_CAP = 300.0

    def __init__(
        self,
        threshold: int,
        sleep_seconds: float,
        probe: Callable[[], bool],
        sleep: Callable[[float], None] = time.sleep,
        on_wait: Callable[[], None] | None = None,
    ) -> None:
        self._threshold = threshold
        self._sleep_seconds = sleep_seconds
        self._probe = probe
        self._sleep = sleep
        self._on_wait = on_wait
        self._consecutive_failures = 0
        self._open = False

    @property
    def open(self) -> bool:
        return self._open

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def record_success(self) -> None:
        if self._consecutive_failures or self._open:
            logger.info("fuse: recovered after %d failures", self._consecutive_failures)
        self._consecutive_failures = 0
        self._open = False
        metrics.consecutive_failures.set(0)
        metrics.fuse_open.set(0)

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        metrics.consecutive_failures.set(self._consecutive_failures)
        if self._consecutive_failures >= self._threshold and not self._open:
            self._blow_and_wait()

    def _blow_and_wait(self) -> None:
        self._open = True
        metrics.fuse_open.set(1)
        metrics.fuse_blown_total.inc()
        logger.warning(
            "fuse blown: %d consecutive failures, sleeping %.0fs",
            self._consecutive_failures,
            self._sleep_seconds,
        )
        backoff = self._sleep_seconds
        while True:
            self._sleep(backoff)
            # Heartbeat after each sleep so a long outage doesn't age out the
            # liveness file and get the pod restarted mid-backlog.
            if self._on_wait is not None:
                self._on_wait()
            if self._probe():
                logger.warning("fuse: probe ok, closing")
                self._open = False
                self._consecutive_failures = 0
                metrics.consecutive_failures.set(0)
                metrics.fuse_open.set(0)
                return
            logger.warning("fuse: probe failed, sleeping %.0fs again", backoff)
            backoff = min(backoff * 2, self._PROBE_BACKOFF_CAP)


class Writer:
    """Wraps `EventWriter` with retry, fuse, and structured drop logging."""

    def __init__(self, writer: EventWriter, retry: Retry, fuse: Fuse) -> None:
        self._writer = writer
        self._retry = retry
        self._fuse = fuse

    def write(self, event: CowrieEvent, raw_line: str) -> Outcome:
        outcome = self._retry.run(lambda: self._writer.write_event(event))
        if outcome is Outcome.SUCCESS:
            self._fuse.record_success()
            metrics.events_processed_total.labels(outcome="success").inc()
            return outcome
        # raw_line carries attacker bytes - defang before it hits log sinks
        safe = sanitize(raw_line)
        if outcome is Outcome.RETRY_EXHAUSTED:
            logger.error("event_dropped reason=retry_exhausted raw=%s", safe)
            metrics.events_processed_total.labels(outcome="retry_exhausted").inc()
            metrics.events_dropped_total.labels(reason="retry_exhausted").inc()
            self._fuse.record_failure()
        else:
            # Fatal = bug / schema drift, not backend health. Fuse stays closed.
            logger.error("event_dropped reason=fatal raw=%s", safe)
            metrics.events_processed_total.labels(outcome="fatal").inc()
            metrics.events_dropped_total.labels(reason="fatal").inc()
        return outcome
