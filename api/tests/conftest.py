import os
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import pytest
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from src.app import create_app
from src.config import TestConfig
from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.download import Download
from src.models.session import Session as HoneypotSession

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://honeywatch:testpass@localhost:5432/honeywatch_test",
)


def _apply_migrations() -> None:
    """Bring the test DB up to head via alembic. Single source of truth for
    schema -- no more `Base.metadata.create_all`."""
    u = urlparse(TEST_DB_URL.replace("postgresql+psycopg://", "postgresql://", 1))
    os.environ.setdefault("POSTGRES_USER", u.username or "honeywatch")
    os.environ.setdefault("POSTGRES_PASSWORD", u.password or "testpass")
    os.environ.setdefault("POSTGRES_HOST", u.hostname or "localhost")
    os.environ.setdefault("POSTGRES_PORT", str(u.port or 5432))
    os.environ.setdefault("POSTGRES_DB", (u.path or "/honeywatch_test").lstrip("/"))
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
    test_app = create_app(TestConfig)
    return test_app


@pytest.fixture()
def client(app: Any, db_session: Session) -> Generator[Any, None, None]:
    import src.extensions as ext

    original_session_local = ext.SessionLocal

    # Override SessionLocal to use the test session's connection
    test_factory = sessionmaker(bind=db_session.get_bind())
    ext.SessionLocal = test_factory

    with app.test_client() as test_client:
        yield test_client

    ext.SessionLocal = original_session_local


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
