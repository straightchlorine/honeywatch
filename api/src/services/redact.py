"""Server-side IP redaction for attacker-controlled free text.

IP addresses should never cross to the API.

Mirrors `dashboard/src/utils/redactIps.ts`; should be kept in sync.
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
# (`http://0x7f.1/`).
_NUMERIC_HOST = (
    r"(?:0[xX][0-9A-Fa-f]+|0[0-7]+|\d{1,10})"
    r"(?:\.(?:0[xX][0-9A-Fa-f]+|0[0-7]+|\d{1,10})){0,3}"
)
_URL_NUMERIC_HOST = (
    r"(?P<scheme>\bhttps?://(?:[^/?#\s@]+@)?)"
    r"(?P<host>" + _NUMERIC_HOST + r")(?!:[0-9A-Fa-f]*:)(?=[/:?#\s]|$)"
)

# Token first (idempotent re-redaction); then IPv6 (incl. embedded-v4) so a full
# literal wins over the numeric-host rule; dotted-quad; numeric-host URL last.
_IP_RE = re.compile(
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


def _replace(m: re.Match[str]) -> str:
    # URL numeric-host branch: keep the scheme/userinfo, blot only the host.
    groups = m.groupdict()
    if groups.get("scheme") is not None and groups.get("host") is not None:
        return groups["scheme"] + IP_BLOT
    return IP_BLOT


def redact_ips(text: str | None) -> str | None:
    """Return `text` with every IP literal replaced by :data:`IP_BLOT`.

    Handles IPv4, IPv6 (including embedded-v4 and bracketed/userinfo URL forms),
    and alternate-encoding numeric URL hosts. `None` passes through unchanged.
    Idempotent: text that is already blotted is returned unchanged.
    """
    if text is None:
        return None
    return _IP_RE.sub(_replace, text)
