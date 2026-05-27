from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
from collections.abc import Generator
from pathlib import Path

import psycopg
import pytest

# Schema lives in api/alembic/. We shell out to `uv run alembic upgrade head`
# from the api directory so its env.py finds its own models and venv, and we
# avoid pulling alembic + sqlalchemy into the ingestor's dependency tree.
_API_DIR = Path(__file__).resolve().parents[2] / "api"


def _resolve_test_db_components() -> dict[str, str]:
    """Resolve test-DB connection parts.

    Mirrors ``api/tests/conftest.py``: ``TEST_DATABASE_URL`` wins if set
    (CI's path), otherwise build from ``POSTGRES_USER`` / ``POSTGRES_PASSWORD``
    / ``POSTGRES_HOST`` / ``POSTGRES_PORT`` plus ``POSTGRES_TEST_DB`` (the
    local justfile path; avoids URL-encoding ``+``/``=`` in dev passwords).
    """
    raw = os.environ.get("TEST_DATABASE_URL")
    if raw:
        raw = raw.replace("postgresql+psycopg://", "postgresql://", 1)
        u = urllib.parse.urlparse(raw)
        return {
            "user": u.username or "honeywatch",
            "password": u.password or "testpass",
            "host": u.hostname or "localhost",
            "port": str(u.port or 5433),
            "db": (u.path or "/honeywatch_test").lstrip("/"),
        }
    return {
        "user": os.environ.get("POSTGRES_USER", "honeywatch"),
        "password": os.environ.get("POSTGRES_PASSWORD", "testpass"),
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": os.environ.get("POSTGRES_PORT", "5433"),
        "db": os.environ.get("POSTGRES_TEST_DB", "honeywatch_test"),
    }


@pytest.fixture(scope="session")
def db_url() -> str:
    c = _resolve_test_db_components()
    # URL-encode the password so ``+`` / ``=`` characters from the project
    # ``.env`` round-trip cleanly into a libpq DSN.
    pw = urllib.parse.quote(c["password"], safe="")
    return f"postgresql://{c['user']}:{pw}@{c['host']}:{c['port']}/{c['db']}"


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(db_url: str) -> None:
    """Run `alembic upgrade head` against the test DB once per session."""
    c = _resolve_test_db_components()
    env = {
        **os.environ,
        "POSTGRES_USER": c["user"],
        "POSTGRES_PASSWORD": c["password"],
        "POSTGRES_HOST": c["host"],
        "POSTGRES_PORT": c["port"],
        "POSTGRES_DB": c["db"],
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
