"""Defang attacker-controlled bytes before they hit operator log sinks.

Cowrie events embed raw attacker input (usernames, passwords, shell input).
Logging the bytes verbatim lets an attacker inject ANSI escapes that mangle
`docker logs`/Loki output, or forge log-line prefixes via embedded CR/LF.
"""

from __future__ import annotations

import re

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def sanitize(s: str | None, max_len: int = 500) -> str:
    """Escape control chars and truncate.

    Replaces every C0 control char (including `\\t`, `\\n`, `\\r`) and DEL
    with a `\\xNN` escape so attacker-supplied bytes cannot forge log-line
    boundaries or drive terminal escape sequences. Truncates to `max_len`
    with an ellipsis marker.
    """
    if s is None:
        return ""
    truncated = s[:max_len] + ("..." if len(s) > max_len else "")
    return _CONTROL_CHARS.sub(lambda m: f"\\x{ord(m.group()):02x}", truncated)
