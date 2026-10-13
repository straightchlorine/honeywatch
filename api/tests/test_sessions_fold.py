"""?fold=true: runs of look-alike sessions fold into one display row, and
pages count display rows, so every page but the last is full."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import urlencode

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.models.auth_attempt import AuthAttempt
from src.models.geo_location import GeoLocation
from src.models.ssh_client import SshClient
from src.services import sessions as sessions_service
from tests.conftest import make_counter_session

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

# Stories in recent order (newest first): A*5 is a run, C*2 a pair shown as
# two rows, then runs of 4 and 3 split by singles.
PATTERN = "AAAAABCCAAAADEFFFGHIIJK"
COUNTERS = {
    letter: {"n_commands": i, "auth_success": i % 2 == 0}
    for i, letter in enumerate("ABCDEFGHIJK")
}


@pytest.fixture()
def pattern_seed(db_session: Session) -> list[str]:
    """PATTERN as sessions one minute apart, newest first, two countries."""
    ids: list[str] = []
    for i, letter in enumerate(PATTERN):
        sid = f"fd{i:04d}"
        make_counter_session(
            db_session,
            sid,
            src_ip=f"198.51.100.{i % 2 + 1}",
            started_at=T0 - timedelta(minutes=i),
            ended_at=T0 - timedelta(minutes=i) + timedelta(seconds=i),
            **COUNTERS[letter],
        )
        ids.append(sid)
    for n, (code, name) in enumerate([("PE", "Peru"), ("CL", "Chile")], start=1):
        db_session.merge(
            GeoLocation(ip=f"198.51.100.{n}", country_code=code, country=name)
        )
    db_session.flush()
    return ids


def _walk(client: Any, query: str, per_page: int) -> tuple[list[int], list[str]]:
    """Every page's row count, and every session id in list order, run
    members fetched from /sessions/run."""
    sizes: list[int] = []
    ids: list[str] = []
    page = 1
    while True:
        body = client.get(
            f"/api/v1/sessions/?fold=true&per_page={per_page}&page={page}&{query}"
        ).get_json()
        for item in body["items"]:
            ids.append(item["id"])
            run = item["run"]
            if run:
                ids.extend(_members(client, query, body["as_of"], run))
        sizes.append(len(body["items"]))
        if page >= body["meta"]["pages"]:
            return sizes, ids
        page += 1


def _members(client: Any, query: str, as_of: str, run: dict[str, Any]) -> list[str]:
    params = urlencode({"as_of": as_of, "offset": run["offset"], "count": run["count"]})
    body = client.get(f"/api/v1/sessions/run?{params}&per_page=100&{query}")
    assert body.status_code == 200
    return [s["id"] for s in body.get_json()["items"]]


def _plain_ids(client: Any, query: str) -> list[str]:
    body = client.get(f"/api/v1/sessions/?per_page=100&{query}").get_json()
    return [s["id"] for s in body["items"]]


@pytest.mark.parametrize("per_page", [1, 3, 4])
@pytest.mark.parametrize(
    "query",
    [
        "sort=recent",
        "sort=interest",
        "sort=duration",
        "sort=active",
        "sort=country",
        "sort=recent&order=asc",
        "sort=interest&country=PE",
        "sort=recent&q=fd001",
    ],
)
def test_every_page_is_full_and_no_session_is_lost_or_repeated(
    client: Any, pattern_seed: list[str], query: str, per_page: int
) -> None:
    del pattern_seed
    sizes, ids = _walk(client, query, per_page)
    assert all(n == per_page for n in sizes[:-1]), sizes
    assert 0 < sizes[-1] <= per_page
    assert ids == _plain_ids(client, query)


def test_runs_of_three_fold_and_pairs_do_not(
    client: Any, pattern_seed: list[str]
) -> None:
    body = client.get("/api/v1/sessions/?fold=true&per_page=100&sort=recent")
    items = body.get_json()["items"]
    shown = "".join(PATTERN[pattern_seed.index(i["id"])] for i in items)
    assert shown == "ABCCADEFGHIIJK"
    assert [i["run"]["count"] if i["run"] else 0 for i in items] == [
        4, 0, 0, 0, 3, 0, 0, 2, 0, 0, 0, 0, 0, 0,
    ]  # fmt: skip
    meta = body.get_json()["meta"]
    assert meta == {"page": 1, "per_page": 100, "pages": 1, "total": len(PATTERN)}


def test_run_summary_describes_the_folded_sessions(
    client: Any, pattern_seed: list[str]
) -> None:
    del pattern_seed
    first = client.get("/api/v1/sessions/?fold=true&sort=recent").get_json()["items"][0]
    # fd0000 carries the run of fd0001..fd0004: a minute apart, i seconds long.
    assert first["id"] == "fd0000"
    assert first["run"] == {
        "count": 4,
        "offset": 1,
        "countries": 2,
        "country_code": None,
        "country": None,
        "min_duration_s": 1,
        "max_duration_s": 4,
        "oldest": (T0 - timedelta(minutes=4)).isoformat(),
        "newest": (T0 - timedelta(minutes=1)).isoformat(),
    }
    peru = client.get("/api/v1/sessions/?fold=true&sort=recent&country=PE")
    run = next(i["run"] for i in peru.get_json()["items"] if i["run"])
    assert (run["countries"], run["country_code"], run["country"]) == (1, "PE", "Peru")


def test_runs_follow_the_requested_order(client: Any, db_session: Session) -> None:
    """Probes and failed logins alternate in time, so by recency nothing folds;
    by origin each country's sessions sit together and fold into one run."""
    for i in range(6):
        probe = i % 2 == 0
        make_counter_session(
            db_session,
            f"mix{i}",
            src_ip=f"192.0.2.{1 if probe else 2}",
            started_at=T0 - timedelta(minutes=i),
        )
        if not probe:
            db_session.add(
                AuthAttempt(
                    session_id=f"mix{i}",
                    username="root",
                    password="x",
                    success=False,
                    timestamp=T0 - timedelta(minutes=i),
                )
            )
    db_session.merge(
        GeoLocation(ip="192.0.2.1", country_code="AR", country="Argentina")
    )
    db_session.merge(GeoLocation(ip="192.0.2.2", country_code="BR", country="Brazil"))
    db_session.flush()

    def shown(sort: str) -> list[tuple[str, int]]:
        items = client.get(f"/api/v1/sessions/?fold=true&sort={sort}").get_json()
        return [(i["id"], i["run"]["count"] if i["run"] else 0) for i in items["items"]]

    assert shown("recent") == [(f"mix{i}", 0) for i in range(6)]
    assert shown("country") == [("mix0", 2), ("mix1", 2)]


def test_a_differing_client_banner_breaks_a_run(
    client: Any, db_session: Session
) -> None:
    for i in range(4):
        make_counter_session(db_session, f"cv{i}", started_at=T0 - timedelta(minutes=i))
        version = "SSH-2.0-Go" if i != 2 else "SSH-2.0-libssh"
        db_session.add(SshClient(session_id=f"cv{i}", client_version=version))
    db_session.flush()
    items = client.get("/api/v1/sessions/?fold=true&sort=recent").get_json()["items"]
    assert [i["run"] for i in items] == [None] * 4


def test_run_members_page_through_a_large_run(client: Any, db_session: Session) -> None:
    for i in range(8):
        make_counter_session(
            db_session, f"big{i}", started_at=T0 - timedelta(minutes=i)
        )
    body = client.get("/api/v1/sessions/?fold=true&sort=recent").get_json()
    [item] = body["items"]
    run = item["run"]
    assert (item["id"], run["count"], run["offset"]) == ("big0", 7, 1)

    params = urlencode({"as_of": body["as_of"], "offset": 1, "count": 7})
    pages = [
        client.get(f"/api/v1/sessions/run?sort=recent&per_page=3&page={p}&{params}")
        for p in (1, 2, 3, 4)
    ]
    got = [[s["id"] for s in p.get_json()["items"]] for p in pages]
    assert got == [["big1", "big2", "big3"], ["big4", "big5", "big6"], ["big7"], []]
    assert pages[0].get_json()["meta"] == {
        "page": 1,
        "per_page": 3,
        "pages": 3,
        "total": 7,
    }


def test_snapshot_leaves_out_sessions_started_after_as_of(
    client: Any, db_session: Session
) -> None:
    for i in range(4):
        make_counter_session(
            db_session, f"snap{i}", started_at=T0 - timedelta(minutes=i)
        )
    as_of = (T0 - timedelta(seconds=90)).isoformat()
    params = urlencode({"as_of": as_of, "offset": 0, "count": 4})
    body = client.get(f"/api/v1/sessions/run?sort=recent&{params}").get_json()
    assert [s["id"] for s in body["items"]] == ["snap2", "snap3"]


def test_folded_rows_keep_banner_redaction(client: Any, db_session: Session) -> None:
    for i in range(3):
        make_counter_session(
            db_session, f"ban{i}", started_at=T0 - timedelta(minutes=i)
        )
        db_session.add(
            SshClient(session_id=f"ban{i}", client_version="SSH-2.0-x 203.0.113.5")
        )
    db_session.flush()
    body = client.get("/api/v1/sessions/?fold=true&sort=recent").get_json()
    params = urlencode({"as_of": body["as_of"], "offset": 1, "count": 2})
    run = client.get(f"/api/v1/sessions/run?sort=recent&{params}").get_json()
    for raw in (body, run):
        assert "203.0.113.5" not in str(raw)
    assert body["items"][0]["client_version"] == "SSH-2.0-x <ip>"


def test_plain_list_is_unchanged(client: Any, pattern_seed: list[str]) -> None:
    body = client.get("/api/v1/sessions/?sort=recent&per_page=100").get_json()
    assert [s["id"] for s in body["items"]] == pattern_seed
    assert "as_of" not in body
    assert all("run" not in s for s in body["items"])


@pytest.mark.parametrize(
    "query",
    [
        "offset=0&count=1",
        "as_of=2026-01-01T00:00:00Z&count=1",
        "as_of=2026-01-01T00:00:00Z&offset=0",
        "as_of=2026-01-01T00:00:00Z&offset=-1&count=1",
        "as_of=2026-01-01T00:00:00Z&offset=0&count=0",
        "as_of=2026-01-01T00:00:00Z&offset=5000001&count=1",
        "as_of=2026-01-01T00:00:00Z&offset=0&count=5000001",
        "as_of=2026-01-01T00:00:00Z&offset=9223372036854775808&count=1",
    ],
)
def test_run_query_is_validated(client: Any, query: str) -> None:
    assert client.get(f"/api/v1/sessions/run?{query}").status_code == 422


def test_one_layout_pass_serves_every_per_page(
    client: Any, pattern_seed: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    del pattern_seed
    passes: list[str] = []
    build = sessions_service._build_layout

    def counted(*args: Any) -> Any:
        passes.append(args[2])
        return build(*args)

    monkeypatch.setattr(sessions_service, "_build_layout", counted)
    for per_page in (1, 3, 4, 40):
        client.get(f"/api/v1/sessions/?fold=true&sort=recent&per_page={per_page}")
    assert passes == ["recent"]


def _layout() -> Any:
    return sessions_service._Layout(
        as_of=T0,
        total=0,
        rows_before=[],
        hidden=[],
        built_at=0.0,
    )


def test_concurrent_cold_requests_share_one_layout_pass() -> None:
    started, release = threading.Event(), threading.Event()
    calls: list[int] = []
    layout = _layout()

    def build(_db: Any) -> Any:
        calls.append(1)
        started.set()
        release.wait(5)
        return layout

    got: list[Any] = []
    threads = [
        threading.Thread(
            target=lambda: got.append(
                sessions_service._cached_layout(MagicMock(), ("k",), build)
            )
        )
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    started.wait(5)
    release.set()
    for t in threads:
        t.join(5)
    assert calls == [1]
    assert got == [layout] * 4


def test_a_failed_layout_pass_retries_once_without_parallel_workers() -> None:
    db = MagicMock()
    layout = _layout()
    outcomes: list[Any] = [OperationalError("x", {}, Exception("shm")), layout]

    def build(_db: Any) -> Any:
        out = outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    assert sessions_service._build_in_slot(db, build, 0) is layout
    db.rollback.assert_called_once()
    [(stmt,), _] = db.execute.call_args
    assert "max_parallel_workers_per_gather = 0" in str(stmt)

    def broken(_db: Any) -> Any:
        raise OperationalError("x", {}, Exception("shm"))

    assert sessions_service._build_in_slot(MagicMock(), broken, 0) is None


def test_without_a_layout_the_plain_list_is_served(
    client: Any, pattern_seed: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sessions_service, "_build_in_slot", lambda *_: None)
    body = client.get("/api/v1/sessions/?fold=true&sort=recent&per_page=10")
    assert body.status_code == 200
    data = body.get_json()
    assert [s["id"] for s in data["items"]] == pattern_seed[:10]
    assert all(s["run"] is None for s in data["items"])
    assert data["meta"] == {"page": 1, "per_page": 10, "pages": 3, "total": 23}


def test_out_of_range_and_empty_fold_pages_are_empty(
    client: Any, pattern_seed: list[str]
) -> None:
    far = client.get("/api/v1/sessions/?fold=true&sort=recent&per_page=10&page=99")
    assert far.status_code == 200
    assert far.get_json()["items"] == []
    none = client.get("/api/v1/sessions/?fold=true&country=ZZ&per_page=10")
    assert none.status_code == 200
    data = none.get_json()
    assert data["items"] == []
    assert data["meta"]["total"] == 0 and data["meta"]["pages"] == 0
    del pattern_seed


def test_a_stale_layout_is_served_while_one_rebuild_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old, new = _layout(), _layout()
    key = ("stale",)
    sessions_service._store_layout(key, old)
    monkeypatch.setattr(sessions_service, "_LAYOUT_TTL_S", -1.0)
    rebuilt = threading.Event()
    started: list[int] = []
    monkeypatch.setattr(sessions_service, "get_session_factory", lambda: MagicMock())

    def build(_db: Any) -> Any:
        started.append(1)
        rebuilt.set()
        return new

    assert sessions_service._cached_layout(MagicMock(), key, build) is old
    assert rebuilt.wait(5)
    # the background pass replaces the stale entry; wait for it to land
    for _ in range(100):
        with sessions_service._layouts_lock:
            if sessions_service._layouts[key] is new:
                break
        time.sleep(0.05)
    assert sessions_service._layouts[key] is new
    assert started == [1]


def test_the_layout_cache_evicts_its_oldest_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sessions_service, "_LAYOUT_CACHE_SIZE", 2)
    for k in ("a", "b", "c"):
        sessions_service._store_layout((k,), _layout())
    assert list(sessions_service._layouts) == [("b",), ("c",)]


def test_a_busy_build_slot_yields_no_layout() -> None:
    assert sessions_service._build_slot.acquire(timeout=1)
    try:
        assert (
            sessions_service._build_in_slot(MagicMock(), lambda _d: _layout(), 0)
            is None
        )
    finally:
        sessions_service._build_slot.release()
