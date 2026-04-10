import base64
import os
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.app import create_app
from src.config import TestConfig
from src.extensions import Base
from src.models.auth_attempt import AuthAttempt
from src.models.command import Command
from src.models.download import Download
from src.models.session import Session as HoneypotSession

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://honeywatch:changeme@localhost:5432/honeywatch_test",
)


@pytest.fixture(scope="session")
def engine() -> Generator[Any, None, None]:
    eng = create_engine(TEST_DB_URL)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
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
def auth_headers() -> dict[str, str]:
    credentials = base64.b64encode(b"testuser:testpass").decode("utf-8")
    return {"Authorization": f"Basic {credentials}"}


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
