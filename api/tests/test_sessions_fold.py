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
from src.services.sessions import cache, checkpoints, layout, pages
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


@pytest.fixture()
def checkpoint_seed(db_session: Session) -> list[str]:
    """Sessions for the checkpoint-seek tests, newest first.

    Only two of the four source IPs resolve to a country *name*, so some rows
    have a NULL country (which sorts last) and several share one (ties), which is
    what the keyset predicate has to get right.
    """
    ids: list[str] = []
    for i in range(14):
        sid = f"ck{i:04d}"
        make_counter_session(
            db_session,
            sid,
            src_ip=f"198.51.100.{i % 4 + 1}",
            started_at=T0 - timedelta(minutes=i),
            ended_at=T0 - timedelta(minutes=i) + timedelta(seconds=i),
            n_commands=i % 3,
        )
        ids.append(sid)
    for ip, code, name in [
        ("198.51.100.1", "PE", "Peru"),
        ("198.51.100.2", "CL", "Chile"),
    ]:
        db_session.merge(GeoLocation(ip=ip, country_code=code, country=name))
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
            ended_at=T0 - timedelta(minutes=i) + timedelta(seconds=30),
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


def test_open_sessions_never_fold(client: Any, db_session: Session) -> None:
    """Counters of an open session still move, so it is never part of a run."""
    for i in range(4):
        make_counter_session(
            db_session, f"open{i}", started_at=T0 - timedelta(minutes=i)
        )
    items = client.get("/api/v1/sessions/?fold=true&sort=recent").get_json()["items"]
    assert [i["run"] for i in items] == [None] * 4


def test_a_close_after_the_layout_does_not_reshape_its_pages(
    client: Any, db_session: Session
) -> None:
    """A session that ends after the layout was built (as_of) must hash the same
    for the page query as it did for the layout, or the page would fold it into
    a run the layout counted without it."""
    now = datetime.now(timezone.utc)
    for i in range(3):
        make_counter_session(
            db_session,
            f"old{i}",
            started_at=now - timedelta(hours=2, minutes=i),
            ended_at=now - timedelta(hours=1, minutes=i),
        )
    live = make_counter_session(db_session, "live", started_at=now)
    url = "/api/v1/sessions/?fold=true&sort=recent"
    before = client.get(url).get_json()["items"]
    assert [(i["id"], bool(i["run"])) for i in before] == [
        ("live", False),
        ("old0", True),
    ]

    live.ended_at = now
    db_session.flush()
    after = client.get(url).get_json()["items"]  # cached layout, fresh page query
    assert [(i["id"], bool(i["run"])) for i in after] == [
        ("live", False),
        ("old0", True),
    ]


def test_run_members_page_through_a_large_run(client: Any, db_session: Session) -> None:
    for i in range(8):
        make_counter_session(
            db_session,
            f"big{i}",
            started_at=T0 - timedelta(minutes=i),
            ended_at=T0 - timedelta(minutes=i) + timedelta(seconds=30),
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
    build = pages.build_layout

    def counted(*args: Any) -> Any:
        passes.append(args[2])
        return build(*args)

    monkeypatch.setattr(pages, "build_layout", counted)
    for per_page in (1, 3, 4, 40):
        client.get(f"/api/v1/sessions/?fold=true&sort=recent&per_page={per_page}")
    assert passes == ["recent"]


def _layout() -> Any:
    return layout.Layout(
        as_of=T0,
        total=0,
        rows_before=[],
        hidden=[],
        built_at=0.0,
        checkpoints=[],
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
            target=lambda: got.append(cache.cached_layout(MagicMock(), ("k",), build))
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


def test_a_layout_pass_runs_without_parallel_workers() -> None:
    db = MagicMock()
    layout = _layout()
    assert cache._build_in_slot(db, lambda _db: layout, 0) is layout
    stmts = [str(call.args[0]) for call in db.execute.call_args_list]
    assert any("max_parallel_workers_per_gather = 0" in stmt for stmt in stmts)


def test_a_layout_pass_gets_the_build_work_mem() -> None:
    """At the default work_mem the build's sort and both hashes spill to disk,
    so the slot raises it for the pass. See _BUILD_WORK_MEM.
    """
    db = MagicMock()
    layout = _layout()
    assert cache._build_in_slot(db, lambda _db: layout, 0) is layout
    stmts = [str(call.args[0]) for call in db.execute.call_args_list]
    assert any(
        stmt.startswith("SET LOCAL work_mem") and cache._BUILD_WORK_MEM in stmt
        for stmt in stmts
    )


def test_a_layout_collects_checkpoints(
    db_session: Session, checkpoint_seed: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """One checkpoint every _CHECKPOINT_EVERY rows, holding the session shown
    there, so a page can seek from it."""
    monkeypatch.setattr(layout, "_CHECKPOINT_EVERY", 3)
    lay = layout.build_layout(db_session, [], "recent", None)
    assert [pos for pos, _ in lay.checkpoints] == [0, 3, 6, 9, 12]
    assert {sid for _, sid in lay.checkpoints} <= set(checkpoint_seed)


def test_checkpoint_before_picks_the_last_checkpoint_strictly_before() -> None:
    lay = layout.Layout(
        as_of=T0,
        total=10,
        rows_before=[],
        hidden=[],
        built_at=0.0,
        checkpoints=[(0, "a"), (5, "b"), (10, "c")],
    )
    assert lay.checkpoint_before(0) is None
    assert lay.checkpoint_before(1) == (0, "a")
    assert lay.checkpoint_before(5) == (0, "a")
    assert lay.checkpoint_before(6) == (5, "b")
    assert lay.checkpoint_before(11) == (10, "c")
    assert lay.checkpoint_before(99) == (10, "c")


def test_a_layout_without_checkpoints_never_seeks() -> None:
    lay = layout.Layout(
        as_of=T0,
        total=3,
        rows_before=[],
        hidden=[],
        built_at=0.0,
        checkpoints=[],
    )
    assert lay.checkpoints == []
    assert lay.checkpoint_before(5) is None


def test_a_seeked_page_matches_the_offset_page(
    db_session: Session, checkpoint_seed: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every page of every sort and order: the keyset seek returns exactly what
    the OFFSET walk returns. Checkpoints every 2 rows so pages after the first
    seek, and the seed has both NULL and tied countries."""
    monkeypatch.setattr(layout, "_CHECKPOINT_EVERY", 2)
    cache.clear_layout_cache()
    original = pages.checkpoint_seek

    def rows(pages: list[Any]) -> list[list[tuple[str, Any]]]:
        return [
            [(s["id"], (s["run"] or {}).get("count")) for s in p["sessions"]]
            for p in pages
        ]

    for sort in ("recent", "country", "active", "interest", "duration"):
        for order in (None, "asc", "desc"):
            seeked = [
                pages.get_sessions_folded(db_session, pg, 3, sort=sort, order=order)
                for pg in range(1, 8)
            ]
            monkeypatch.setattr(pages, "checkpoint_seek", lambda *a, **k: None)
            try:
                plain = [
                    pages.get_sessions_folded(db_session, pg, 3, sort=sort, order=order)
                    for pg in range(1, 8)
                ]
            finally:
                monkeypatch.setattr(pages, "checkpoint_seek", original)
            assert rows(seeked) == rows(plain), f"{sort} order={order}"


def test_a_deep_page_seeks_and_page_one_does_not(
    db_session: Session, checkpoint_seed: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The seek has to engage, or the optimisation is silently dead; and page 1
    must not pay for it, since its snapshot offset is 0."""
    monkeypatch.setattr(layout, "_CHECKPOINT_EVERY", 2)
    cache.clear_layout_cache()
    calls: list[str] = []
    original = checkpoints._checkpoint_values

    def spy(db: Any, sort: str, order: Any, as_of: Any, sid: str) -> Any:
        calls.append(sid)
        return original(db, sort, order, as_of, sid)

    monkeypatch.setattr(checkpoints, "_checkpoint_values", spy)
    pages.get_sessions_folded(db_session, 1, 3, sort="country")
    assert calls == []
    pages.get_sessions_folded(db_session, 2, 3, sort="country")
    assert calls


def test_a_vanished_checkpoint_falls_back_to_the_offset(
    db_session: Session, checkpoint_seed: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(layout, "_CHECKPOINT_EVERY", 2)
    monkeypatch.setattr(checkpoints, "_checkpoint_values", lambda *a, **k: None)
    cache.clear_layout_cache()
    page = pages.get_sessions_folded(db_session, 3, 3, sort="country")
    assert len(page["sessions"]) == 3


def test_a_failed_layout_pass_yields_no_layout() -> None:
    db = MagicMock()

    def broken(_db: Any) -> Any:
        raise OperationalError("x", {}, Exception("boom"))

    assert cache._build_in_slot(db, broken, 0) is None
    db.rollback.assert_called_once()


def test_without_a_layout_the_plain_list_is_served(
    client: Any, pattern_seed: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cache, "_build_in_slot", lambda *_: None)
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
    cache._store_layout(key, old)
    monkeypatch.setattr(cache, "_LAYOUT_TTL_S", -1.0)
    rebuilt = threading.Event()
    started: list[int] = []
    monkeypatch.setattr(cache, "get_session_factory", lambda: MagicMock())

    def build(_db: Any) -> Any:
        started.append(1)
        rebuilt.set()
        return new

    assert cache.cached_layout(MagicMock(), key, build) is old
    assert rebuilt.wait(5)
    # the background pass replaces the stale entry; wait for it to land
    for _ in range(100):
        with cache._layouts_lock:
            if cache._layouts[key] is new:
                break
        time.sleep(0.05)
    assert cache._layouts[key] is new
    assert started == [1]


def test_the_layout_cache_evicts_its_oldest_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cache, "_LAYOUT_CACHE_SIZE", 2)
    for k in ("a", "b", "c"):
        cache._store_layout((k,), _layout())
    assert list(cache._layouts) == [("b",), ("c",)]


def test_a_busy_build_slot_yields_no_layout() -> None:
    assert cache._build_slot.acquire(timeout=1)
    try:
        assert cache._build_in_slot(MagicMock(), lambda _d: _layout(), 0) is None
    finally:
        cache._build_slot.release()
