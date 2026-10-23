"""Constants the sessions queries and schemas share."""

from __future__ import annotations

VALID_HAS_FILTERS = frozenset({"commands", "downloads", "success", "tcpip", "none"})

# A run is RUN_MIN or more consecutive sessions (in the requested order) that are similar:
# the "N more like this" functionality
RUN_MIN = 3
