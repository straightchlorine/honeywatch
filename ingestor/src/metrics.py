"""Prometheus metrics for the ingestor; singleton registry reset via
_REGISTRY.clear() in conftest for test isolation."""

from __future__ import annotations

from prometheus_client import Counter, Gauge

events_processed_total = Counter(
    "ingestor_events_processed_total",
    "Cowrie events processed, labelled by terminal outcome.",
    ["outcome"],
)

events_dropped_total = Counter(
    "ingestor_events_dropped_total",
    "Events dropped without being persisted.",
    ["reason"],
)

fuse_blown_total = Counter(
    "ingestor_fuse_blown_total",
    "Number of times the writer fuse blew.",
)

geo_upsert_failures_total = Counter(
    "ingestor_geo_upsert_failures_total",
    "Geo enrichment failures (session row still persisted).",
)

parser_drift_total = Counter(
    "ingestor_parser_drift_total",
    "Cowrie events that failed to parse, by eventid.",
    ["eventid"],
)

orphan_event_total = Counter(
    "ingestor_orphan_event_total",
    "Events for an unknown session_id (likely connect was missed).",
    ["kind"],
)

deduped_write_total = Counter(
    "ingestor_deduped_write_total",
    "Writes rejected by the (session_id, timestamp) unique index - a "
    "Retry-replayed write being correctly ignored, or (rarely) two "
    "distinct events colliding on the same session and microsecond.",
    ["kind"],
)

queue_depth = Gauge(
    "ingestor_queue_depth",
    "Current depth of the tail->writer queue.",
)

consecutive_failures = Gauge(
    "ingestor_consecutive_failures",
    "Consecutive write failures since the last success.",
)

fuse_open = Gauge(
    "ingestor_fuse_open",
    "1 while the fuse is open, 0 otherwise.",
)
