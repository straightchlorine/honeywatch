from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest

# Schema lives in api/alembic/. We shell out to `uv run alembic upgrade head`
# from the api directory so its env.py finds its own models and venv, and we
# avoid pulling alembic + sqlalchemy into the ingestor's dependency tree.
_API_DIR = Path(__file__).resolve().parents[2] / "api"


@pytest.fixture(scope="session")
def db_url() -> str:
    raw = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://honeywatch:testpass@localhost:5432/honeywatch_test",
    )
    # Raw psycopg rejects SQLAlchemy's `postgresql+psycopg://` dialect qualifier.
    return raw.replace("postgresql+psycopg://", "postgresql://", 1)


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(db_url: str) -> None:
    """Run alembic upgrade once per session against the test DB."""
    u = urlparse(db_url)
    env = {
        **os.environ,
        "POSTGRES_USER": u.username or "honeywatch",
        "POSTGRES_PASSWORD": u.password or "testpass",
        "POSTGRES_HOST": u.hostname or "localhost",
        "POSTGRES_PORT": str(u.port or 5432),
        "POSTGRES_DB": (u.path or "/honeywatch_test").lstrip("/"),
    }
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_API_DIR,
        env=env,
        check=True,
    )


_TRUNCATE = """
TRUNCATE downloads, commands, auth_attempts, sessions CASCADE;
"""


@pytest.fixture
def db_connection(db_url: str) -> Generator[psycopg.Connection[tuple[object, ...]]]:
    conn = psycopg.connect(db_url)
    yield conn
    conn.execute(_TRUNCATE)
    conn.commit()
    conn.close()


@pytest.fixture
def sample_connect_event() -> str:
    return json.dumps(
        {
            "eventid": "cowrie.session.connect",
            "session": "abc123",
            "src_ip": "192.168.1.100",
            "src_port": 54321,
            "dst_ip": "10.0.0.1",
            "dst_port": 2222,
            "protocol": "ssh",
            "timestamp": "2024-01-15T10:30:00.000000Z",
            "sensor": "honeypot-01",
        }
    )


@pytest.fixture
def sample_login_failed() -> str:
    return json.dumps(
        {
            "eventid": "cowrie.login.failed",
            "session": "abc123",
            "username": "root",
            "password": "password123",
            "timestamp": "2024-01-15T10:30:05.000000Z",
        }
    )


@pytest.fixture
def sample_login_success() -> str:
    return json.dumps(
        {
            "eventid": "cowrie.login.success",
            "session": "abc123",
            "username": "root",
            "password": "toor",
            "timestamp": "2024-01-15T10:30:10.000000Z",
        }
    )


@pytest.fixture
def sample_command() -> str:
    return json.dumps(
        {
            "eventid": "cowrie.command.input",
            "session": "abc123",
            "input": "cat /etc/passwd",
            "timestamp": "2024-01-15T10:30:15.000000Z",
        }
    )


@pytest.fixture
def sample_download() -> str:
    return json.dumps(
        {
            "eventid": "cowrie.session.file_download",
            "session": "abc123",
            "url": "http://evil.com/malware.sh",
            "outfile": "/tmp/malware.sh",
            "shasum": "e3b0c44298fc1c149afbf4c8996fb924"
            "27ae41e4649b934ca495991b7852b855",
            "timestamp": "2024-01-15T10:30:20.000000Z",
        }
    )


@pytest.fixture
def sample_session_closed() -> str:
    return json.dumps(
        {
            "eventid": "cowrie.session.closed",
            "session": "abc123",
            "timestamp": "2024-01-15T10:31:00.000000Z",
        }
    )
