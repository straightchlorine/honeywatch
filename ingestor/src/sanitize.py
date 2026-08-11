"""Defang attacker-controlled bytes before they hit operator log sinks.

Cowrie events embed raw attacker input (usernames, passwords, shell input).
Logging the bytes verbatim lets an attacker inject ANSI escapes that mangle
`docker logs`/Loki output, or forge log-line prefixes via embedded CR/LF.
"""

from __future__ import annotations

import re

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def sanitize(s: str | None, max_len: int = 500) -> str:
    """Escape control chars and truncate for log output.

    Replaces every C0 control char and DEL with `\\xNN` to defang log-injection
    (ANSI escapes, CR/LF forging). Returns empty string if input is None.
    """
    if s is None:
        return ""
    truncated = s[:max_len] + ("..." if len(s) > max_len else "")
    return _CONTROL_CHARS.sub(lambda m: f"\\x{ord(m.group()):02x}", truncated)


_STORAGE_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")


def truncate(s: str | None, max_len: int) -> str | None:
    """Strip control chars (keep `\\t`) and cap length for DB storage.

    Preserves None for nullable columns. Strips NUL (Postgres rejects it)
    and other C0/DEL chars (prevent log injection downstream). `\\t` is
    kept—legitimate in attacker input. Control chars stripped before
    length cap so max_len counts stored bytes.

    Arguments:
      s: attacker-supplied string or None
      max_len: max stored length in bytes

    Returns:
      sanitized string or None; empty string never returned
    """
    if s is None:
        return s
    s = _STORAGE_CONTROL_CHARS.sub("", s)
    if len(s) <= max_len:
        return s
    return s[:max_len]
