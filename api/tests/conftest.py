import os
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from alembic.config import Config as AlembicConfig
from flask import url_for
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from src.app import create_app
from src.config import TestingConfig
from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.download import Download
from src.models.geo_location import GeoLocation
from src.models.session import Session as HoneypotSession


def _resolve_test_db_url() -> str:
    """Prefer TEST_DATABASE_URL env var; fall back to POSTGRES_* vars."""
    direct = os.environ.get("TEST_DATABASE_URL")
    if direct:
        return direct
    return URL.create(
        "postgresql+psycopg",
        username=os.environ.get("POSTGRES_USER", "honeywatch"),
        password=os.environ.get("POSTGRES_PASSWORD", "testpass"),
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5433")),
        database=os.environ.get("POSTGRES_TEST_DB", "honeywatch_test"),
    ).render_as_string(hide_password=False)


TEST_DB_URL = _resolve_test_db_url()


def _apply_migrations() -> None:
    from sqlalchemy.engine.url import make_url

    url_obj = make_url(TEST_DB_URL)
    os.environ["POSTGRES_USER"] = url_obj.username or "honeywatch"
    os.environ["POSTGRES_PASSWORD"] = url_obj.password or "testpass"
    os.environ["POSTGRES_HOST"] = url_obj.host or "localhost"
    os.environ["POSTGRES_PORT"] = str(url_obj.port or 5433)
    os.environ["POSTGRES_DB"] = url_obj.database or "honeywatch_test"
    cfg = AlembicConfig("alembic.ini")
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def engine() -> Generator[Any, None, None]:
    _apply_migrations()
    eng = create_engine(TEST_DB_URL)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine: Any) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="session")
def app(engine: Any) -> Any:
    os.environ.setdefault("ENVIRONMENT", "development")
    return create_app(TestingConfig)


@pytest.fixture()
def client(app: Any, db_session: Session) -> Generator[Any, None, None]:
    original_factory = app.extensions.get("db_session_factory")
    app.extensions["db_session_factory"] = sessionmaker(bind=db_session.get_bind())

    with app.test_client() as test_client:
        yield test_client

    if original_factory is not None:
        app.extensions["db_session_factory"] = original_factory


# Path args no fixture can synthesize.
_UNCOVERABLE = {"static"}
# Endpoints whose required query arg has no load_default.
_REQUIRED_QUERY = {"stats.stats_passwords_by_length": {"length": 12}}


@pytest.fixture()
def get_urls(app: Any) -> Any:
    """Every GET route in url_map, path/query args filled in.

    Enumerated, not listed: a route added later is covered without anyone
    remembering to add it to a privacy test.
    """

    def _build(**path_values: Any) -> list[str]:
        urls: list[str] = []
        with app.test_request_context():
            for rule in app.url_map.iter_rules():
                if "GET" not in (rule.methods or ()):
                    continue
                # api-docs.* passes today, but the 50 KB openapi.json would break
                # this test the day someone writes an example like 192.0.2.1.
                if rule.endpoint in _UNCOVERABLE or rule.endpoint.startswith(
                    "api-docs."
                ):
                    continue
                missing = set(rule.arguments) - set(path_values)
                assert not missing, (
                    f"{rule.rule} needs path args {sorted(missing)}: pass a value "
                    f"from the fixture or add it to _UNCOVERABLE"
                )
                args = {k: path_values[k] for k in rule.arguments}
                args.update(_REQUIRED_QUERY.get(rule.endpoint, {}))
                urls.append(url_for(rule.endpoint, **args))
        return sorted(urls)

    return _build


def make_counter_session(
    db_session: Session,
    session_id: str,
    *,
    src_ip: str = "203.0.113.10",
    n_commands: int = 0,
    n_downloads: int = 0,
    n_tcpip: int = 0,
    auth_success: bool = False,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    country_code: str | None = None,
) -> HoneypotSession:
    """Counter-only session (no child rows) shared by test_sessions.py and
    test_stats.py for testing summary columns directly rather than via joins.
    """
    session = HoneypotSession(
        id=session_id,
        src_ip=src_ip,
        src_port=1,
        dst_port=22,
        protocol="ssh",
        started_at=started_at or datetime.now(timezone.utc),
        ended_at=ended_at,
        n_commands=n_commands,
        n_downloads=n_downloads,
        n_tcpip=n_tcpip,
        auth_success=auth_success,
    )
    db_session.add(session)
    db_session.flush()
    if country_code is not None:
        db_session.add(GeoLocation(ip=src_ip, country_code=country_code))
        db_session.flush()
    return session


@pytest.fixture()
def seed_data(db_session: Session) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    session1 = HoneypotSession(
        id="sess-001",
        src_ip="192.168.1.100",
        src_port=54321,
        dst_ip="10.0.0.1",
        dst_port=22,
        protocol="ssh",
        started_at=now,
        sensor="sensor-1",
    )
    session2 = HoneypotSession(
        id="sess-002",
        src_ip="192.168.1.200",
        src_port=12345,
        dst_port=22,
        protocol="ssh",
        started_at=now,
        sensor="sensor-1",
    )
    db_session.add_all([session1, session2])
    db_session.flush()

    geo1 = GeoLocation(
        ip="192.168.1.100",
        country_code="US",
        country="United States",
        city="Ashburn",
        latitude=39.04,
        longitude=-77.49,
        asn=14618,
        as_org="Example Org",
        last_updated=now,
    )
    db_session.add(geo1)
    db_session.flush()

    auth1 = AuthAttempt(
        session_id="sess-001",
        username="root",
        password="password123",
        success=False,
        timestamp=now,
    )
    auth2 = AuthAttempt(
        session_id="sess-001",
        username="admin",
        password="admin",
        success=False,
        # Distinct from auth1's timestamp: (session_id, timestamp) is unique.
        timestamp=now + timedelta(microseconds=1),
    )
    auth3 = AuthAttempt(
        session_id="sess-002",
        username="root",
        password="toor",
        success=True,
        timestamp=now,
    )
    db_session.add_all([auth1, auth2, auth3])
    db_session.flush()

    cmd1 = Command(
        session_id="sess-001",
        input="whoami",
        success=True,
        timestamp=now,
    )
    db_session.add(cmd1)

    dl1 = Download(
        session_id="sess-001",
        url="http://evil.com/malware.sh",
        sha256="abc123",
        timestamp=now,
    )
    db_session.add(dl1)
    db_session.flush()

    return {
        "sessions": [session1, session2],
        "geo": [geo1],
        "auth_attempts": [auth1, auth2, auth3],
        "commands": [cmd1],
        "downloads": [dl1],
    }


# Exercises each charset class and PASSWORD_LENGTH_CAP behavior.
LONG_PASSWORD = "abcdefghijklmnopqr"
_CHARSET_PASSWORDS: dict[str, str] = {
    "empty": "",
    "symbol": "p@ss!",
    "digits": "12345",
    "lower": "secret",
    "upper": "ROOT",
    "alnum": "abc123",
    "long": LONG_PASSWORD,
}


@pytest.fixture()
def charset_seed(db_session: Session) -> dict[str, Any]:
    """Seed one auth attempt per charset class plus >= cap-length sample.

    Isolated from seed_data so exact-count assertions remain valid.
    """
    now = datetime.now(timezone.utc)
    session = HoneypotSession(
        id="charset-001",
        src_ip="203.0.113.10",
        src_port=40000,
        dst_port=22,
        protocol="ssh",
        started_at=now,
        sensor="sensor-1",
    )
    db_session.add(session)
    db_session.flush()

    attempts = [
        # Offset per row: (session_id, timestamp) is unique.
        AuthAttempt(
            session_id="charset-001",
            username="attacker",
            password=password,
            success=False,
            timestamp=now + timedelta(microseconds=i),
        )
        for i, password in enumerate(_CHARSET_PASSWORDS.values())
    ]
    db_session.add_all(attempts)
    db_session.flush()
    return {"expected": dict(_CHARSET_PASSWORDS), "attempts": attempts}


@pytest.fixture()
def ip_fanout_seed(db_session: Session) -> dict[str, Any]:
    """Seed shared credentials from two IPs (fanout=2) and one IP (fanout=1).

    Isolated from seed_data so ip_fanout ranking is unambiguous.
    """
    now = datetime.now(timezone.utc)
    sessions = [
        HoneypotSession(
            id="fanout-001",
            src_ip="198.51.100.10",
            src_port=50001,
            dst_port=22,
            protocol="ssh",
            started_at=now,
            sensor="sensor-1",
        ),
        HoneypotSession(
            id="fanout-002",
            src_ip="198.51.100.20",
            src_port=50002,
            dst_port=22,
            protocol="ssh",
            started_at=now,
            sensor="sensor-1",
        ),
        HoneypotSession(
            id="fanout-003",
            src_ip="198.51.100.30",
            src_port=50003,
            dst_port=22,
            protocol="ssh",
            started_at=now,
            sensor="sensor-1",
        ),
    ]
    db_session.add_all(sessions)
    db_session.flush()

    attempts = [
        AuthAttempt(
            session_id="fanout-001",
            username="botnet",
            password="sharedpw",
            success=False,
            timestamp=now,
        ),
        AuthAttempt(
            session_id="fanout-002",
            username="botnet",
            password="sharedpw",
            success=False,
            timestamp=now,
        ),
        AuthAttempt(
            session_id="fanout-003",
            username="loner",
            password="lonelypw",
            success=False,
            timestamp=now,
        ),
    ]
    db_session.add_all(attempts)
    db_session.flush()
    return {"sessions": sessions, "attempts": attempts}


@pytest.fixture()
def failed_and_probe_seed(db_session: Session) -> None:
    """Seed 'failed' (one rejected auth) and 'probe' (no auth) sessions."""
    now = datetime.now(timezone.utc)
    db_session.add(
        HoneypotSession(
            id="failsess001",
            src_ip="203.0.113.9",
            src_port=1,
            dst_port=22,
            protocol="ssh",
            started_at=now,
        )
    )
    db_session.add(
        HoneypotSession(
            id="probesess01",
            src_ip="203.0.113.10",
            src_port=2,
            dst_port=22,
            protocol="ssh",
            started_at=now,
        )
    )
    db_session.flush()
    db_session.add(
        AuthAttempt(
            session_id="failsess001",
            username="root",
            password="x",
            success=False,
            timestamp=now,
        )
    )
    db_session.flush()
