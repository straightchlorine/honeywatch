import os
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from src.app import create_app
from src.config import TestingConfig
from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.download import Download
from src.models.session import Session as HoneypotSession


def _resolve_test_db_url() -> str:
    """Resolve the test database URL.

    Two supported inputs:

    1. ``TEST_DATABASE_URL`` set directly (CI uses this with a literal password).
    2. ``POSTGRES_USER``/``POSTGRES_PASSWORD``/``POSTGRES_HOST``/``POSTGRES_PORT``
       plus ``POSTGRES_TEST_DB``. Used locally by the justfile, which sources the
       project ``.env`` (its passwords contain ``+`` / ``=`` characters that
       refuse to round-trip through a hand-rolled URL string).

    Either path always points at a dedicated test database; tests must never
    mutate ``$POSTGRES_DB`` (the live dev DB).
    """
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
    # Overwrite (not setdefault): the developer shell may have POSTGRES_*
    # exported from the project's .env pointing at the dev database. Alembic
    # must always target whatever TEST_DATABASE_URL points at.
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
    # Route the app's session factory at the per-test transaction so every
    # request sees (and rolls back) the same data as the test body.
    original_factory = app.extensions.get("db_session_factory")
    app.extensions["db_session_factory"] = sessionmaker(bind=db_session.get_bind())

    with app.test_client() as test_client:
        yield test_client

    if original_factory is not None:
        app.extensions["db_session_factory"] = original_factory


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
        timestamp=now,
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
        "auth_attempts": [auth1, auth2, auth3],
        "commands": [cmd1],
        "downloads": [dl1],
    }
