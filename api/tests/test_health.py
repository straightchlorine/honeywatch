from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


def test_health_returns_ok(client: Any) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"


def test_ready_returns_ok_when_db_up(client: Any) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ready"


class _ExplodingSession:
    """Unreachable SQLAlchemy Session (execute() raises OperationalError); patching
    at the session-factory seam (not get_session_factory) reproduces realistic
    DB outages where pool acquisition fails."""

    def __enter__(self) -> "_ExplodingSession":
        return self

    def __exit__(self, *_args: Any) -> bool:
        return False

    def execute(self, *_args: Any, **_kwargs: Any) -> Any:
        raise OperationalError(
            "simulated outage", params=None, orig=Exception("connection refused")
        )


class _ExplodingFactory:
    def __call__(self) -> _ExplodingSession:
        return _ExplodingSession()


def test_ready_returns_503_when_db_down(
    app: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """Mock at the session-factory seam to reproduce realistic DB outage (factory
    succeeds, execute() fails)."""
    original = app.extensions.get("db_session_factory")
    app.extensions["db_session_factory"] = _ExplodingFactory()
    try:
        caplog.set_level("WARNING")
        with app.test_client() as client:
            response = client.get("/health/ready")
    finally:
        if original is not None:
            app.extensions["db_session_factory"] = original

    assert response.status_code == 503
    assert response.get_json() == {"status": "unavailable", "reason": "db"}
    assert "/health/ready: db unavailable" in caplog.text


def test_attack_data_indexes_present(db_session: Any) -> None:
    """Verify indexes exist after `alembic upgrade head`; `CREATE INDEX IF NOT
    EXISTS` silently skips typos, so we lock the contract here (including
    `ix_auth_attempts_worked_creds` for worked-credentials)."""
    rows = (
        db_session.execute(
            text(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname IN (
                      'ix_auth_attempts_session_id',
                      'ix_auth_attempts_worked_creds',
                      'ix_commands_session_id',
                      'ix_downloads_session_id'
                  )
                ORDER BY indexname
                """
            )
        )
        .scalars()
        .all()
    )
    assert rows == [
        "ix_auth_attempts_session_id",
        "ix_auth_attempts_worked_creds",
        "ix_commands_session_id",
        "ix_downloads_session_id",
    ]
