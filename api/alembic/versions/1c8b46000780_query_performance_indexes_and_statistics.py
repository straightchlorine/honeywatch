"""query performance indexes and statistics

Revision ID: 1c8b46000780
Revises: f4a9c2e1b8d7
Create Date: 2026-07-24 14:28:59.015259

"""

from typing import Sequence, Union

from alembic import op

revision: str = "1c8b46000780"
down_revision: Union[str, Sequence[str], None] = "f4a9c2e1b8d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Index-only scans for COUNT(DISTINCT); expression index forces length-based filtering.
_INDEXES = (
    ("ix_auth_attempts_username", "ON auth_attempts (username)"),
    ("ix_auth_attempts_password", "ON auth_attempts (password)"),
    ("ix_auth_attempts_pw_len", "ON auth_attempts (char_length(password), password)"),
)

# ndistinct hint corrects cardinality estimate for dow/hour; forces hash aggregate.
_STATISTICS = (
    (
        "st_sessions_dow_hour",
        "(ndistinct) ON (extract(dow FROM started_at)), "
        "(extract(hour FROM started_at)) FROM sessions",
    ),
    ("st_sessions_hour_trunc", "ON (date_trunc('hour', started_at)) FROM sessions"),
    ("st_sessions_day_trunc", "ON (date_trunc('day', started_at)) FROM sessions"),
    ("st_sessions_month_trunc", "ON (date_trunc('month', started_at)) FROM sessions"),
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for name, definition in _INDEXES:
            op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} {definition}")
    for name, definition in _STATISTICS:
        op.execute(f"CREATE STATISTICS IF NOT EXISTS {name} {definition}")
    op.execute("ANALYZE sessions")


def downgrade() -> None:
    for name, _ in _STATISTICS:
        op.execute(f"DROP STATISTICS IF EXISTS {name}")
    with op.get_context().autocommit_block():
        for name, _ in _INDEXES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
