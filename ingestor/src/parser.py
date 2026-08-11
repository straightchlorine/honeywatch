"""Parse a single cowrie JSON line into a `CowrieEvent`."""

from __future__ import annotations

import json
import logging

from pydantic import TypeAdapter, ValidationError

from src import metrics
from src.events import CowrieEvent
from src.sanitize import sanitize

logger = logging.getLogger(__name__)

_ADAPTER: TypeAdapter[CowrieEvent] = TypeAdapter(CowrieEvent)

# Log unknown eventids at WARNING on first sighting, DEBUG thereafter.
_seen_drift: set[str] = set()


def parse_event(line: str) -> CowrieEvent | None:
    """Validate `line` against the cowrie schema.

    Args:
        line: A single JSON object as text.

    Returns:
        The matched `CowrieEvent` subtype, or None if the line doesn't
        match any known schema (drift, unknown event, malformed JSON).
    """
    try:
        return _ADAPTER.validate_json(line)
    except ValidationError as exc:
        _log_drift(line, exc)
        return None


def _log_drift(line: str, exc: ValidationError) -> None:
    """Emit a sanitized, rate-limited warning for a line that failed validation."""
    eventid = _extract_eventid(line)
    safe_eventid = sanitize(eventid, max_len=64) if eventid else "<unknown>"
    first_err = exc.errors()[0].get("msg", str(exc)) if exc.errors() else str(exc)
    safe_err = sanitize(str(first_err), max_len=200)
    safe_raw = sanitize(line, max_len=200)

    metrics.parser_drift_total.labels(eventid=safe_eventid).inc()

    if safe_eventid not in _seen_drift:
        _seen_drift.add(safe_eventid)
        logger.warning(
            "parser: dropped event id=%s err=%s raw=%s (first sighting)",
            safe_eventid,
            safe_err,
            safe_raw,
        )
    else:
        logger.debug(
            "parser: dropped event id=%s err=%s raw=%s",
            safe_eventid,
            safe_err,
            safe_raw,
        )


def _extract_eventid(line: str) -> str | None:
    """Safely pull `eventid` from a possibly-malformed JSON line.

    Uses `json.loads` so JSON escape sequences resolve correctly. If the
    line isn't valid JSON or `eventid` is missing/non-str, returns None.
    """
    try:
        obj = json.loads(line)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    value = obj.get("eventid")
    return value if isinstance(value, str) else None
