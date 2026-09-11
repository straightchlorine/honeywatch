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

# Strip whole ANSI escape sequences, not just ESC. A bare ESC strip leaves
# the printable tail (e.g. "[31m") right before the payload, and that
# trailing character defeats redact_ips's alnum-adjacency guard (exists to
# avoid matching an IP embedded in an identifier): "\x1b[31mssh 192.168.1.1"
# would store as "[31mssh 192.168.1.1", with "m" blocking redaction of the
# IP. Not CSI-only: an OSC sequence (window title, e.g. "\x1b]0;x\x07") or
# any other ESC-introduced sequence leaves the identical residue and the
# identical bypass, so all three ECMA-48 families are covered:
#   - CSI:            ESC '[' params/intermediate bytes, final byte
#   - OSC/DCS/APC/PM:  ESC ']'/'P'/'X'/'^'/'_' ... terminated by BEL or ST
#   - simple (Fp/Fe/Fs): ESC + one more printable byte (e.g. reset, save-cursor)
# A malformed/unterminated sequence still loses at least its introducer to
# the last alternative, and any single stray byte falls through to the
# control-char strip below.
_ANSI_ESCAPE = re.compile(
    r"\x1b(?:"
    r"\[[0-9:;<=>?]*[ -/]*[@-~]"  # CSI
    r"|\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC, BEL- or ST-terminated
    r"|[PX^_][^\x1b]*\x1b\\"  # DCS/SOS/PM/APC, ST-terminated
    r"|[!-~]"  # any other simple escape, or a malformed introducer
    r")"
)


def truncate(s: str | None, max_len: int) -> str | None:
    """Strip ANSI escapes and control chars (keep `\\t`), cap length for DB storage.

    Preserves None for nullable columns. Strips whole ANSI/VT100 escape
    sequences (not just the ESC byte - see `_ANSI_ESCAPE`), NUL (Postgres
    rejects it), and other C0/DEL chars (prevent log injection downstream).
    `\\t` is kept - legitimate in attacker input. Stripped before the length
    cap so max_len counts stored bytes.

    Arguments:
      s: attacker-supplied string or None
      max_len: max stored length in bytes

    Returns:
      sanitized string or None; empty string never returned
    """
    if s is None:
        return s
    s = _ANSI_ESCAPE.sub("", s)
    s = _STORAGE_CONTROL_CHARS.sub("", s)
    if len(s) <= max_len:
        return s
    return s[:max_len]
