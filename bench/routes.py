"""The HTTP requests the bench sends, one entry per request shape.

Every GET route of the API has to appear here: measure.py lists the ones that do
not. Values that depend on the data (a session id, a country, a payload hash) are
looked up in the bench database, so the cases stay valid for any dump. A case whose
value is missing, for example no downloads at all, is skipped.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from sqlalchemy import text
from sqlalchemy.orm import Session

# Windows relative to now: the same data answers differently as the clock moves, so
# only the shape of the response is fingerprinted.
TIME_RELATIVE = ("/api/v1/stats/activity", "/api/v1/stats/trend")
# Docs, the spec and static assets are not part of the API surface.
NOT_API = re.compile(r"^/api/v1/(static|swagger|redoc|openapi)")

TEMPLATES = """
/api/v1/sessions/?per_page=40
/api/v1/sessions/?per_page=100
/api/v1/sessions/?per_page=40&sort=active
/api/v1/sessions/?fold=true&per_page=40
/api/v1/sessions/?fold=true&per_page=40&sort=country
/api/v1/sessions/?fold=true&per_page=40&sort=active
/api/v1/sessions/?fold=true&per_page=40&sort=interest
/api/v1/sessions/?fold=true&per_page=40&sort=duration
/api/v1/sessions/?fold=true&per_page=40&page=300
/api/v1/sessions/?fold=true&per_page=40&category=active
/api/v1/sessions/?fold=true&per_page=40&has=commands
/api/v1/sessions/?fold=true&per_page=40&country={country}
/api/v1/sessions/?fold=true&per_page=40&q={prefix}
/api/v1/sessions/?sha256={sha}
/api/v1/sessions/{busy}
/api/v1/sessions/{probe}
/api/v1/stats/activity
/api/v1/stats/activity?bucket=hour
/api/v1/stats/activity?country={country}
/api/v1/stats/asns
/api/v1/stats/asns?top_n=100
/api/v1/stats/auth-outcomes
/api/v1/stats/countries
/api/v1/stats/countries?top_n=100
/api/v1/stats/countries/{country}
/api/v1/stats/downloads
/api/v1/stats/downloads?top_n=100
/api/v1/stats/downloads/{sha}
/api/v1/stats/fingerprints
/api/v1/stats/heatmap
/api/v1/stats/heatmap?country={country}
/api/v1/stats/map
/api/v1/stats/outcomes
/api/v1/stats/outcomes?country={country}
/api/v1/stats/password-composition
/api/v1/stats/passwords-by-length?length=8
/api/v1/stats/ssh-clients
/api/v1/stats/tcpip-destinations
/api/v1/stats/top-countries
/api/v1/stats/top-credentials
/api/v1/stats/top-credentials?by=password&metric=ip_fanout&outcome=success
/api/v1/stats/top-passwords
/api/v1/stats/top-passwords?top_n=100
/api/v1/stats/totals
/api/v1/stats/trend
/api/v1/stats/trend?period_days=365
/health
/health/ready
""".split()


# What the dashboard sends when a visitor opens Sessions (default sort interest, 40
# rows, folded) and then changes the sort. Each sort has its own layout, so every
# first visit of a sort is a cold layout build.
_LIST = "/api/v1/sessions/?page=1&per_page=40&fold=true&sort="
JOURNEY = [
    ("open interest", _LIST + "interest"),
    ("open outcomes", "/api/v1/stats/outcomes"),
    ("open countries", "/api/v1/stats/top-countries?top_n=100"),
    ("sort recent", _LIST + "recent"),
    ("sort duration", _LIST + "duration"),
    ("sort active", _LIST + "active"),
    ("sort country", _LIST + "country"),
    ("back to interest", _LIST + "interest"),
]


def lookups(db: Session) -> dict[str, str | None]:
    """Data-dependent request values; None when the table has no row for one."""

    def one(sql: str) -> str | None:
        value = db.execute(text(sql)).scalar()
        return None if value is None else str(value)

    busy = one("select id from sessions order by n_commands desc, id limit 1")
    return {
        "busy": busy,  # the largest detail payload
        "probe": one(
            "select id from sessions where n_commands = 0"
            " order by started_at desc limit 1"
        ),
        "prefix": busy[:4] if busy else None,
        "country": one(
            "select g.country_code from sessions s join geo_locations g"
            " on g.ip = s.src_ip where g.country_code is not null"
            " group by 1 order by count(*) desc limit 1"
        ),
        "sha": one(
            "select sha256 from downloads group by 1 order by count(*) desc limit 1"
        ),
    }


def cases(values: dict[str, str | None]) -> list[str]:
    """The request paths, with every {name} filled in from the lookups."""
    paths: list[str] = []
    for template in TEMPLATES:
        names = re.findall(r"{(\w+)}", template)
        if all(values.get(n) for n in names):
            paths.append(template.format(**values))
    return paths


def label(path: str) -> str:
    """The request as the CSV names it: the snapshot time differs on every run."""
    return re.sub(r"as_of=[^&]*", "as_of=SNAPSHOT", path)


def shape(doc: object) -> object:
    """The structure of a response with every value replaced by its type."""
    if isinstance(doc, dict):
        return {k: shape(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [len(doc), shape(doc[0]) if doc else None]
    return type(doc).__name__


def run_members(client: Any) -> str | None:
    """A /sessions/run request built from the first run on the folded list."""
    body = client.get("/api/v1/sessions/?fold=true&per_page=40").get_json()
    for item in body["items"]:
        run = item.get("run")
        if run:
            return (
                f"/api/v1/sessions/run?as_of={quote(body['as_of'])}"
                f"&offset={run['offset']}&count={run['count']}"
            )
    return None


def uncovered(app: Any) -> list[str]:
    """GET routes of the app that no template reaches, whether or not it runs."""
    bare = [p.split("?")[0] for p in [*TEMPLATES, "/api/v1/sessions/run"]]
    missing: list[str] = []
    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods or NOT_API.match(rule.rule):
            continue
        if not rule.rule.startswith(("/api/v1/", "/health")):
            continue
        pattern = re.compile("^" + re.sub(r"<[^>]+>", r"\\{\\w+\\}", rule.rule) + "$")
        if not any(pattern.match(b) for b in bare):
            missing.append(rule.rule)
    return sorted(missing)
