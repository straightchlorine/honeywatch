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

import psycopg
from prometheus_client import start_http_server

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

# Sentinel pushed by the producer to tell the consumer to drain and exit.
_STOP_SENTINEL = object()


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
            # block on backpressure - cowrie's file still holds the line so
            # the next loop will catch up once the consumer drains.
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
    """Drain `in_queue`, parse + persist via `writer`. Heartbeat liveness."""
    # Touching, so probes won't kill the pod during cold start.
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
        logger.debug("cowrie event: %s", line)

        event = parse_event(line)
        if event is not None:
            writer.write(event, line)

        _touch_healthy(config)


def _touch_healthy(config: Config) -> None:
    """Refresh the liveness sentinel from the consumer loop.

    Not "after successful DB write" - DB stalls (which the fuse rides out)
    must not age the file out and trigger restarts that lose the backlog.
    """
    try:
        config.healthcheck_path.touch()
    except OSError:
        logger.warning(
            "failed to touch healthcheck path %s",
            config.healthcheck_path,
            exc_info=True,
        )


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
        start_http_server(config.metrics_port)
        logger.info("Metrics server listening on :%d", config.metrics_port)
    else:
        logger.info("Metrics server disabled (METRICS_ENABLED=0)")

    stop_event = threading.Event()

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
    finally:
        logger.info("Ingestor shut down")


if __name__ == "__main__":
    main()
