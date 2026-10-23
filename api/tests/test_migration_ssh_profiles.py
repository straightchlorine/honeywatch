"""The ssh_client_profiles split (a3c5e7f9b1d4) against real data, not empty tables.

CI runs `alembic upgrade head` against an empty schema, so a migration that moves
data is only ever exercised by hand. This module seeds the revision *before* the
split, upgrades, and compares the result with a copy taken beforehand - in a
scratch database, so the shared test database and its fixtures are untouched.

What it pins:

* no row is lost, added or changed by the split (compared with EXCEPT, which
  treats NULL as equal to NULL, so NULL columns are covered too);
* `first_seen` and `client_version` survive;
* a row with no handshake columns keeps `profile_id IS NULL` instead of pointing
  at an all-NULL profile;
* the profile `digest` is `md5(row(<the seven columns>)::text)` - the same
  expression the ingestor's upsert uses, so a profile written before and after
  the migration is the same row;
* the downgrade rebuilds the wide table losslessly and the upgrade can run again;
* the app roles can use the new table (when the cluster has them).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import ProgrammingError

from alembic import command
from tests.conftest import TEST_DB_URL

BEFORE = "b8f3e6a1d942"  # the revision before the split
AFTER = "a3c5e7f9b1d4"  # the split

# The seven columns that moved into ssh_client_profiles, in the order the digest
# expression and the migration use.
PROFILE_COLS = (
    "hassh",
    "hassh_algorithms",
    "kex_algorithms",
    "key_algorithms",
    "encryption_algorithms",
    "mac_algorithms",
    "compression_algorithms",
)
PROFILE_COL_LIST = ", ".join(PROFILE_COLS)

# Five shared handshakes (one per g % 5) plus the row with long lists.
EXPECTED_PROFILES = 6
EXPECTED_ROWS = 1500 + 100 + 100 + 1


def _seed(conn: object) -> None:
    """Sessions plus wide ssh_clients rows covering every case the split faces."""
    conn.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO sessions (id, src_ip, src_port, dst_port, protocol, started_at)
            SELECT 'sess-' || lpad(g::text, 4, '0'),
                   ('10.0.0.' || (1 + g % 250))::inet,
                   1024 + g,
                   22,
                   'ssh',
                   now() - (g || ' seconds')::interval
            FROM generate_series(1, 2001) g
            """
        )
    )
    # 1..1500: five distinct handshakes, so the profiles actually deduplicate.
    conn.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO ssh_clients (
                session_id, client_version, hassh, hassh_algorithms,
                kex_algorithms, key_algorithms, encryption_algorithms,
                mac_algorithms, compression_algorithms, first_seen
            )
            SELECT 'sess-' || lpad(g::text, 4, '0'),
                   'libssh_' || (g % 3) || '.0',
                   lpad((g % 5)::text, 32, '0'),
                   'hassh-algs-' || (g % 5),
                   'kex-' || (g % 5),
                   'key-' || (g % 5),
                   'enc-' || (g % 5),
                   'mac-' || (g % 5),
                   'comp-' || (g % 5),
                   now() - (g || ' minutes')::interval
            FROM generate_series(1, 1500) g
            """
        )
    )
    # 1501..1600: a version and no handshake at all -> profile_id must stay NULL.
    conn.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO ssh_clients (session_id, client_version, first_seen)
            SELECT 'sess-' || lpad(g::text, 4, '0'), 'version-only',
                   now() - (g || ' minutes')::interval
            FROM generate_series(1501, 1600) g
            """
        )
    )
    # 1601..1700: a handshake and no version -> shares the profiles above.
    conn.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO ssh_clients (
                session_id, client_version, hassh, hassh_algorithms,
                kex_algorithms, key_algorithms, encryption_algorithms,
                mac_algorithms, compression_algorithms, first_seen
            )
            SELECT 'sess-' || lpad(g::text, 4, '0'), NULL,
                   lpad((g % 5)::text, 32, '0'),
                   'hassh-algs-' || (g % 5),
                   'kex-' || (g % 5),
                   'key-' || (g % 5),
                   'enc-' || (g % 5),
                   'mac-' || (g % 5),
                   'comp-' || (g % 5),
                   now()
            FROM generate_series(1601, 1700) g
            """
        )
    )
    # One handshake with long algorithm lists, near the column caps.
    conn.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO ssh_clients (
                session_id, client_version, hassh, hassh_algorithms,
                kex_algorithms, key_algorithms, encryption_algorithms,
                mac_algorithms, compression_algorithms, first_seen
            )
            VALUES (
                'sess-2001', 'long-lists',
                repeat('a', 32), repeat('h', 1024),
                repeat('kex,', 800), repeat('key,', 800),
                repeat('enc,', 800), repeat('mac,', 800), repeat('comp,', 800),
                now()
            )
            """
        )
    )
    # 1701..2000 deliberately have no ssh_clients row: the split must not invent one.


@pytest.fixture()
def scratch_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """An empty database of its own, dropped afterwards.

    Roles live in the cluster, but default privileges are recorded per database,
    so the grants init.sql installs are replayed *inside the scratch database* -
    installing them on the base connection would put them in the wrong database.
    """
    name = f"hw_mig_{os.getpid()}"
    admin = create_engine(TEST_DB_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    # alembic/env.py builds its URL from POSTGRES_*, which the justfile sets but
    # CI does not (CI sets TEST_DATABASE_URL), so derive them here rather than
    # inheriting whatever the runner happens to export.
    url = make_url(TEST_DB_URL).set(database=name)
    monkeypatch.setenv("POSTGRES_USER", url.username or "honeywatch")
    monkeypatch.setenv("POSTGRES_PASSWORD", url.password or "testpass")
    monkeypatch.setenv("POSTGRES_HOST", url.host or "localhost")
    monkeypatch.setenv("POSTGRES_PORT", str(url.port or 5432))
    monkeypatch.setenv("POSTGRES_DB", name)
    scratch = create_engine(url.render_as_string(hide_password=False))
    try:
        with scratch.begin() as conn:  # begin(), so the grants are committed
            _install_role_grants(conn)
        yield name
    finally:
        scratch.dispose()  # drop needs no other session on the scratch database
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _install_role_grants(conn: object) -> None:
    """The parts of postgres/init.sql that a fresh database needs, if roles exist."""
    roles = [
        r[0]
        for r in conn.execute(  # type: ignore[attr-defined]
            text(
                "SELECT rolname FROM pg_roles "
                "WHERE rolname IN ('honeywatch_ingestor', 'honeywatch_api')"
            )
        ).all()
    ]
    if len(roles) < 2:
        return
    for sql in (
        "GRANT USAGE ON SCHEMA public TO honeywatch_ingestor, honeywatch_api",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT INSERT, SELECT, UPDATE, DELETE ON TABLES TO honeywatch_ingestor",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO honeywatch_ingestor",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT ON TABLES TO honeywatch_api",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT ON SEQUENCES TO honeywatch_api",
    ):
        conn.execute(text(sql))  # type: ignore[attr-defined]


def _engine(scratch: str) -> object:
    url = make_url(TEST_DB_URL).set(database=scratch)
    return create_engine(url.render_as_string(hide_password=False))


def _migrate(revision: str, *, down: bool = False) -> None:
    cfg = AlembicConfig("alembic.ini")
    if down:
        command.downgrade(cfg, revision)
    else:
        command.upgrade(cfg, revision)


def _rows_differing(conn: object, left: str, right: str) -> int:
    """Rows in one side but not the other. EXCEPT treats NULL as equal to NULL."""
    return conn.execute(  # type: ignore[attr-defined]
        text(f"SELECT count(*) FROM (({left}) EXCEPT ({right})) x")
    ).scalar_one()


# The wide table as the split must leave it reachable: the narrow row plus its
# profile's columns. Compared with EXCEPT against the pre-upgrade copy, so both
# sides must list the columns in exactly the same order.
_WIDE_FROM_SPLIT = (
    "SELECT c.session_id, c.client_version, c.first_seen, "
    + ", ".join(f"p.{c}" for c in PROFILE_COLS)
    + " FROM ssh_clients c LEFT JOIN ssh_client_profiles p ON p.id = c.profile_id"
)


def _wide_from(table: str) -> str:
    """The wide table's columns, in the one order the comparisons use."""
    cols = f"session_id, client_version, first_seen, {PROFILE_COL_LIST}"
    return f"SELECT {cols} FROM {table}"


_WIDE_FROM_COPY = _wide_from("_pre")


def test_the_split_preserves_every_row_and_its_digest(scratch_db: str) -> None:
    """Upgrade, compare with the copy, downgrade, compare, upgrade again.

    Each step opens its own short-lived connection: holding one open across a
    migration would keep locks on ssh_clients and block the swap.
    """
    engine = _engine(scratch_db)
    _migrate(BEFORE)
    with engine.begin() as conn:  # type: ignore[attr-defined]
        _seed(conn)
        conn.execute(text("CREATE TABLE _pre AS SELECT * FROM ssh_clients"))

    _migrate(AFTER)
    with engine.connect() as conn:  # type: ignore[attr-defined]

        def one(sql: str) -> int:
            return conn.execute(text(sql)).scalar_one()  # type: ignore[attr-defined]

        # Same rows, same values, NULLs included, both directions.
        assert _rows_differing(conn, _WIDE_FROM_SPLIT, _WIDE_FROM_COPY) == 0
        assert _rows_differing(conn, _WIDE_FROM_COPY, _WIDE_FROM_SPLIT) == 0
        assert one("SELECT count(*) FROM ssh_clients") == EXPECTED_ROWS
        assert one("SELECT count(*) FROM ssh_client_profiles") == EXPECTED_PROFILES
        # The version-only rows got no all-NULL profile, and kept their version.
        assert (
            one(
                "SELECT count(*) FROM ssh_client_profiles "
                f"WHERE num_nonnulls({PROFILE_COL_LIST}) = 0"
            )
            == 0
        )
        assert (
            one(
                "SELECT count(*) FROM ssh_clients WHERE session_id "
                "BETWEEN 'sess-1501' AND 'sess-1600' "
                "AND profile_id IS NULL AND client_version = 'version-only'"
            )
            == 100
        )
        # A kex-only row keeps a NULL version and still finds its profile.
        assert (
            one(
                "SELECT count(*) FROM ssh_clients WHERE session_id "
                "BETWEEN 'sess-1601' AND 'sess-1700' "
                "AND profile_id IS NOT NULL AND client_version IS NULL"
            )
            == 100
        )
        # Sessions that never had a handshake row still have none.
        assert (
            one(
                "SELECT count(*) FROM ssh_clients WHERE session_id "
                "BETWEEN 'sess-1701' AND 'sess-2000'"
            )
            == 0
        )
        # The digest is the expression the ingestor's upsert writes, so a profile
        # written before and after the migration is the same row.
        assert (
            one(
                "SELECT count(*) FROM ssh_client_profiles "
                f"WHERE digest <> md5(row({PROFILE_COL_LIST})::text)"
            )
            == 0
        )

    # The downgrade rebuilds the wide table losslessly...
    _migrate(BEFORE, down=True)
    with engine.connect() as conn:  # type: ignore[attr-defined]
        wide = _wide_from("ssh_clients")
        assert _rows_differing(conn, wide, _WIDE_FROM_COPY) == 0
        assert _rows_differing(conn, _WIDE_FROM_COPY, wide) == 0
        assert (
            conn.execute(text("SELECT count(*) FROM ssh_clients")).scalar_one()
            == EXPECTED_ROWS
        )

    # ...and it can go forward again.
    _migrate(AFTER)
    with engine.connect() as conn:  # type: ignore[attr-defined]
        assert (
            conn.execute(text("SELECT count(*) FROM ssh_clients")).scalar_one()
            == EXPECTED_ROWS
        )
        assert (
            conn.execute(text("SELECT count(*) FROM ssh_client_profiles")).scalar_one()
            == EXPECTED_PROFILES
        )
    engine.dispose()  # type: ignore[attr-defined]


def test_the_app_roles_can_use_the_new_table(scratch_db: str) -> None:
    """The split creates a table; the ingestor and the API need privileges on it.

    Privileges are checked *as* the roles via `SET ROLE`, so the session's
    superuser-ness cannot mask the result and no role password is needed. Default
    privileges are recorded per database, so the fixture replays
    postgres/init.sql's grants before the migrations run.

    Neither the dev compose file nor CI mounts postgres/init.sql, so in those
    clusters the roles do not exist and this skips; run it against a restored
    prod dump (which has them) to actually exercise the check.
    """
    engine = _engine(scratch_db)
    _migrate(AFTER)

    with engine.begin() as conn:  # type: ignore[attr-defined]
        present = conn.execute(
            text(
                "SELECT count(*) FROM pg_roles WHERE rolname IN "
                "('honeywatch_ingestor', 'honeywatch_api')"
            )
        ).scalar_one()
        if present < 2:
            pytest.skip("the ingestor/api roles are not in this cluster")

        # The ingestor writes the session and its handshake rows.
        conn.execute(text("SET ROLE honeywatch_ingestor"))
        conn.execute(
            text(
                "INSERT INTO sessions (id, src_ip, src_port, dst_port, protocol) "
                "VALUES ('role-check', '10.9.9.9', 1, 22, 'ssh')"
            )
        )
        profile_id = conn.execute(
            text(
                "INSERT INTO ssh_client_profiles (digest, hassh) "
                "VALUES (repeat('b', 32), 'role-hassh') RETURNING id"
            )
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO ssh_clients (session_id, profile_id) "
                "VALUES ('role-check', :p)"
            ),
            {"p": profile_id},
        )
        conn.execute(text("RESET ROLE"))

    # The API reads what the ingestor wrote, and must not be able to write.
    with engine.connect() as conn:  # type: ignore[attr-defined]
        conn.execute(text("SET ROLE honeywatch_api"))
        try:
            assert (
                conn.execute(
                    text("SELECT count(*) FROM ssh_client_profiles")
                ).scalar_one()
                == 1
            )
            with pytest.raises(ProgrammingError):
                conn.execute(
                    text(
                        "INSERT INTO ssh_client_profiles (digest) "
                        "VALUES (repeat('c', 32))"
                    )
                )
        finally:
            # ROLLBACK discards the failed insert and reverts SET ROLE, so the
            # pooled connection cannot leak the role into another test.
            conn.rollback()
            conn.execute(text("RESET ROLE"))
            conn.commit()
    engine.dispose()  # type: ignore[attr-defined]
