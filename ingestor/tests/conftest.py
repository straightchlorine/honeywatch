from __future__ import annotations

import json
import os
from collections.abc import Generator

import psycopg
import pytest


@pytest.fixture(scope="session")
def db_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://honeywatch:changeme@localhost:5432/honeywatch_test",
    )


_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    src_ip INET,
    src_port INT,
    dst_ip INET,
    dst_port INT,
    protocol TEXT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    sensor TEXT
);

CREATE TABLE IF NOT EXISTS auth_attempts (
    id SERIAL PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    username TEXT,
    password TEXT,
    success BOOL,
    timestamp TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS commands (
    id SERIAL PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    input TEXT,
    success BOOL,
    timestamp TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS downloads (
    id SERIAL PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    url TEXT,
    outfile TEXT,
    sha256 TEXT,
    timestamp TIMESTAMPTZ
);
"""

_TRUNCATE = """
TRUNCATE downloads, commands, auth_attempts, sessions CASCADE;
"""


@pytest.fixture
def db_connection(db_url: str) -> Generator[psycopg.Connection[tuple[object, ...]]]:
    conn = psycopg.connect(db_url)
    conn.execute(_CREATE_TABLES)
    conn.commit()
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
