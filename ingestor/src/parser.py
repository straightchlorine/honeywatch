"""Parse a cowrie JSON log line into a typed pydantic event.

All known event types live in `src.events`. This module is a thin adapter:
wire validation + discrimination happen inside pydantic via the `CowrieEvent`
union; everything this file does is catch `ValidationError` and translate it
to `None` so the caller can skip unhandled or malformed lines.
"""

from __future__ import annotations

import logging

from pydantic import TypeAdapter, ValidationError

from src.events import CowrieEvent

logger = logging.getLogger(__name__)

_ADAPTER: TypeAdapter[CowrieEvent] = TypeAdapter(CowrieEvent)


def parse_event(line: str) -> CowrieEvent | None:
    """Parse a raw cowrie JSON line. Returns None if unhandled or malformed.

    The caller should already have logged the raw line at INFO so unhandled
    events stay visible.
    """
    try:
        return _ADAPTER.validate_json(line)
    except ValidationError as exc:
        logger.debug("Skipping event: %s", exc.errors()[0].get("msg", exc))
        return None
