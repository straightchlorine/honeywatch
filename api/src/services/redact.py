"""Blot IP literals out of attacker-controlled free text.

Commands and download URLs are whatever the attacker typed, so they can carry
third-party IPs that must not reach a client. Mirrors
dashboard/src/utils/redactIps.ts - keep the two in sync.
"""

from __future__ import annotations

import re
from typing import overload

IP_BLOT = "<ip>"  # must stay byte-identical to dashboard IP_BLOT

_IPV4 = (
    r"(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
)

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

# Use digit-dot guards, not \b: underscore is a word char, so \b fails on
# banners like MGLNDD_IP_PORT. Guards prevent false negatives (version strings
# like lib.so.1.2.3.4.5) and false positives (embedded IPs in filenames).
_IPV4_STANDALONE = r"(?<!\d\.)(?<![0-9A-Za-z])" + _IPV4 + r"(?![0-9A-Za-z])(?!\.\d)"

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

# Shell commands pass numeric IPs without scheme (nc host port); boundedness
# and range-check avoid false positives on ports/flags/durations (bash literals).
# Tradeoff: bare 10-digit timestamps (1735689600) also match IPv4 range; better
# to over-redact timestamps than leak third-party hosts.
_SCHEMELESS_NUMERIC_HOST = (
    r"(?<![\w.:-])"
    r"(?P<numtok>0[xX][0-9A-Fa-f]{5,8}|0[0-7]{8,11}|\d{8,10})"
    r"(?![\w.:-])"
)

# Order: token (idempotent), IPv6 (wins over numeric rules), dotted-quad,
# scheme-qualified numeric-host, schemeless last (most conservative, range-checked).
_LITERAL_ALTS = (
    "(?:"
    + re.escape(IP_BLOT)
    + ")|(?:"
    + _IPV6
    + ")|(?:"
    + _IPV4_STANDALONE
    + ")|(?:"
    + _URL_NUMERIC_HOST
    + ")"
)
_IP_RE = re.compile(_LITERAL_ALTS + "|(?:" + _SCHEMELESS_NUMERIC_HOST + ")")

# Exclude schemeless bare-integer heuristic: safe for shell commands (nc host)
# but unsafe for credentials (123456789 is a common password, would blot into <ip>).
_IP_RE_LITERAL = re.compile(_LITERAL_ALTS)

# Detects numeric-only hosts (including 0.0.0.1) that bypass the range gate,
# while leaving real DNS names alone.
# No separate octal branch: `0[0-7]+` is a subset of `\d+`, so listing both made
# the alternation ambiguous and "9." + "00."*n backtracked exponentially. This
# only tests shape, never value, so `\d+` alone matches the same language.
_NUMERIC_HOST_ONLY = re.compile(
    r"^(?:0[xX][0-9A-Fa-f]+|\d+)(?:\.(?:0[xX][0-9A-Fa-f]+|\d+))*\.?$"
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


@overload
def redact_ips(text: str, *, numeric_hosts: bool = True) -> str:
    pass


@overload
def redact_ips(text: None, *, numeric_hosts: bool = True) -> None:
    pass


def redact_ips(text: str | None, *, numeric_hosts: bool = True) -> str | None:
    """Replace IP literals and numeric URL hosts with <ip>.

    Set numeric_hosts=False for credentials and SSH banners where numbers
    like "123456789" are valid passwords, not hosts to redact.
    """
    if text is None:
        return None
    pattern = _IP_RE if numeric_hosts else _IP_RE_LITERAL
    return pattern.sub(_replace, text)


def safe_host(host: str | None) -> str | None:
    """Return host only when it is a real DNS name that embeds no IP.

    Used for the payload `host` and relay `network` labels, which the schema
    promises are "never an IP". `ipaddress.ip_address()` alone was too weak: it
    accepts neither `0x7f000001` nor `192.168.001.1` nor a trailing-dot
    `1.2.3.4.`, and it cannot see an IP wrapped in wildcard DNS
    (`185.220.101.5.nip.io`). There is nothing truthful to substitute, so a
    host that fails either check becomes None rather than a blot.

    Deliberately tolerant of anything that is not an address encoding: the
    relay `network` column is usually an AS org name, so "Cloudflare, Inc."
    and "YANDEX LLC" must survive untouched.
    """
    if not host:
        return None
    if redact_ips(host) != host:
        return None
    if _NUMERIC_HOST_ONLY.match(host):
        return None
    return host
