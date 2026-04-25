"""Thin adapter around the `CowrieEvent` pydantic union."""

from __future__ import annotations

import logging

from pydantic import TypeAdapter, ValidationError

from src.events import CowrieEvent

logger = logging.getLogger(__name__)

_ADAPTER: TypeAdapter[CowrieEvent] = TypeAdapter(CowrieEvent)


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
        logger.debug("Skipping event: %s", exc.errors()[0].get("msg", exc))
        return None
