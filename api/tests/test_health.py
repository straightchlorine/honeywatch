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
    """`/health/ready` round-trips a SELECT 1 to the test database."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ready"


class _ExplodingSession:
    """Stand-in for an SQLAlchemy Session whose connection is unreachable.

    A real Postgres outage manifests when the route calls `db.execute(...)`
    (pool tries to acquire a connection and the driver raises
    `OperationalError`). Patching `get_session_factory` itself does not
    reproduce that path -- `get_session_factory` only raises on an
    uninitialised Flask app, never on a DB outage.
    """

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
    """A failing DB session yields 503 with a reason and emits a warning.

    Swaps the app-level session factory (the same seam used by the `client`
    fixture in conftest) so the route exercises the realistic failure path:
    factory call returns, context manager enters, `execute` raises.
    """
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
    """The migrations' indexes survive an `alembic upgrade head` run.

    `CREATE INDEX [CONCURRENTLY] IF NOT EXISTS` silently skips a duplicate name,
    so a typo in the migration would not raise. Lock the contract here.

    Includes `ix_auth_attempts_worked_creds`, the partial
    `(username, password) WHERE success` index that backs the worked-credentials
    leaderboard (stats.credentials.top_credentials(outcome="success")).
    """
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
