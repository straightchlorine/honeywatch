"""Thin adapter around the `CowrieEvent` pydantic union."""

from __future__ import annotations

import logging
import re

from pydantic import TypeAdapter, ValidationError

from src.events import CowrieEvent

logger = logging.getLogger(__name__)

_ADAPTER: TypeAdapter[CowrieEvent] = TypeAdapter(CowrieEvent)
# Probe for the eventid. When validation fails (drift, unknown event),
# the eventid shows whether there is a new type we don't model or known
# type changed.
_EVENTID_RE = re.compile(r'"eventid"\s*:\s*"([^"]+)"')
_RAW_EXCERPT_LIMIT = 200


def parse_event(line: str) -> CowrieEvent | None:
    """Parse a raw cowrie JSON line.

    Args:
        line: One JSON-encoded cowrie event.

    Returns:
        The parsed `CowrieEvent`, or `None` if the line is unhandled or malformed.
    """
    try:
        return _ADAPTER.validate_json(line)
    except ValidationError as exc:
        # cowrie shape drift warning
        match = _EVENTID_RE.search(line)
        eventid = match.group(1) if match else None
        first_err = exc.errors()[0].get("msg", str(exc)) if exc.errors() else str(exc)
        excerpt = line[:_RAW_EXCERPT_LIMIT]
        if len(line) > _RAW_EXCERPT_LIMIT:
            excerpt += "..."
        logger.warning(
            "parser: dropped event id=%s err=%s raw=%s",
            eventid,
            first_err,
            excerpt,
        )
        return None
