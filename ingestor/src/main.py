"""Cowrie log -> Postgres ingestor entrypoint.

Producer thread tails cowrie's log into a bounded queue; the consumer
drives `Writer`. A Postgres outage stalls only the consumer:
  - producer keeps draining cowrie's log into memory (capped)
  - liveness file keeps being touched
  - orchestration doesn't kill the pod mid-backlog
"""

from __future__ import annotations

import logging
import queue
import signal
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import psycopg
from prometheus_client import REGISTRY, start_http_server, write_to_textfile

from src import metrics
from src.config import Config
from src.parser import parse_event
from src.reliability import Fuse, Retry, Writer
from src.tail import tail_follow
from src.writer import EventWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

_STOP_SENTINEL = object()

_TEXTFILE_INTERVAL = 15.0


def _producer(
    lines: Iterator[str],
    out_queue: "queue.Queue[str | object]",
    stop_event: threading.Event,
) -> None:
    """Push tailed lines onto `out_queue`; exit when `stop_event` is set."""
    try:
        for line in lines:
            if stop_event.is_set():
                break
            # Block on backpressure; cowrie's log retains the line until
            # consumer drains.
            while not stop_event.is_set():
                try:
                    out_queue.put(line, timeout=0.5)
                    break
                except queue.Full:
                    continue
            metrics.queue_depth.set(out_queue.qsize())
    finally:
        # Always signal the consumer so it doesn't block forever on shutdown.
        out_queue.put(_STOP_SENTINEL)


def _consumer(
    in_queue: "queue.Queue[str | object]",
    writer: Writer,
    config: Config,
    stop_event: threading.Event,
) -> None:
    """Drain queue, parse and persist events, heartbeat liveness file."""
    # Touch liveness file early to prevent cold-start probe timeout.
    _touch_healthy(config)

    while not stop_event.is_set():
        try:
            item = in_queue.get(timeout=1.0)
        except queue.Empty:
            _touch_healthy(config)
            continue

        metrics.queue_depth.set(in_queue.qsize())

        if item is _STOP_SENTINEL:
            break

        line = item if isinstance(item, str) else ""

        try:
            event = parse_event(line)
            if event is not None:
                writer.write(event, line)
        except Exception:
            # Single bad line shouldn't kill the consumer thread.
            # Writer/fuse already handles DB faults; this catches the
            # truly unexpected (parser bug, queue corruption).
            metrics.events_dropped_total.labels(reason="consumer_error").inc()
            logger.exception("consumer error processing line; skipping")

        _touch_healthy(config)


def _touch_healthy(config: Config) -> None:
    """Refresh the liveness file regardless of DB state to prevent mid-backlog
    restarts."""
    try:
        config.healthcheck_path.touch()
    except OSError:
        logger.warning(
            "failed to touch healthcheck path %s",
            config.healthcheck_path,
            exc_info=True,
        )


def _write_textfile(path: Path) -> None:
    """Atomically write only the `ingestor_*` metrics (no process_/python_)."""
    # restricted_registry matches sample names, not family names: a Counter's
    # family "x" emits "x_total"/"x_created", so list those spellings too.
    names = [
        f"{m.name}{suffix}"
        for m in REGISTRY.collect()
        if m.name.startswith("ingestor_")
        for suffix in ("", "_total", "_created")
    ]
    write_to_textfile(str(path), REGISTRY.restricted_registry(names))


def _textfile_loop(
    path: Path, stop_event: threading.Event, interval: float = _TEXTFILE_INTERVAL
) -> None:
    """Rewrite `path` every `interval` seconds until `stop_event` is set.

    A failing write (missing or unwritable directory) must never affect
    ingestion, so errors are logged once per outage and once on recovery.
    """
    failing = False
    while not stop_event.is_set():
        try:
            _write_textfile(path)
            if failing:
                logger.warning("metrics textfile %s writable again", path)
                failing = False
        except Exception:
            if not failing:
                logger.warning(
                    "failed to write metrics textfile %s; will keep retrying",
                    path,
                    exc_info=True,
                )
                failing = True
        stop_event.wait(interval)


def _build_probe(writer: EventWriter) -> Callable[[], bool]:
    """Fuse probe: True iff a `SELECT 1` round-trips to Postgres."""

    def probe() -> bool:
        try:
            with writer.pool.connection() as conn:
                conn.execute("SELECT 1")
            return True
        except psycopg.Error:
            return False

    return probe


def main() -> None:
    """Run the ingestor event loop until interrupted."""
    config = Config.from_env()
    logger.info("Starting ingestor, watching %s", config.log_path)

    if config.metrics_enabled:
        # Bind loopback only; scraper sidecar / port-forward exposes it.
        start_http_server(config.metrics_port, addr="127.0.0.1")
        logger.info("Metrics server listening on 127.0.0.1:%d", config.metrics_port)
    else:
        logger.info("Metrics server disabled (METRICS_ENABLED=0)")

    stop_event = threading.Event()

    textfile_thread: threading.Thread | None = None
    if config.metrics_textfile is not None:
        textfile_thread = threading.Thread(
            target=_textfile_loop,
            args=(config.metrics_textfile, stop_event),
            name="metrics-textfile",
            daemon=True,
        )
        textfile_thread.start()
        logger.info("Writing metrics textfile to %s", config.metrics_textfile)

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("Received signal %d, shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        with EventWriter(
            config.conninfo, drop_loopback=config.drop_loopback
        ) as event_writer:
            writer = Writer(
                event_writer,
                Retry(
                    attempts=config.retry_attempts,
                    initial_backoff=config.retry_initial_backoff,
                ),
                Fuse(
                    threshold=config.fuse_threshold,
                    sleep_seconds=config.fuse_sleep,
                    probe=_build_probe(event_writer),
                    # Keep the liveness file fresh while the fuse rides out
                    # a DB outage - probing can loop for as long as Postgres
                    # is down.
                    on_wait=lambda: _touch_healthy(config),
                ),
            )

            line_queue: queue.Queue[str | object] = queue.Queue(
                maxsize=config.queue_max
            )
            producer_thread = threading.Thread(
                target=_producer,
                args=(tail_follow(config.log_path), line_queue, stop_event),
                name="tail-producer",
                daemon=True,
            )
            producer_thread.start()

            _consumer(line_queue, writer, config, stop_event)
            stop_event.set()
            producer_thread.join(timeout=2.0)
            if textfile_thread is not None:
                textfile_thread.join(timeout=2.0)
    finally:
        logger.info("Ingestor shut down")


if __name__ == "__main__":
    main()
