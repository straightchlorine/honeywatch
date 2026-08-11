"""attack data indexes

Revision ID: 48be1097dd9b
Revises: a1b2c3d4e5f6
Create Date: 2026-05-27 19:57:28.471777

"""

from typing import Sequence, Union

from alembic import op

revision: str = "48be1097dd9b"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Indexes for selectinload (WHERE IN on each dashboard load) and Postgres
# cascade-delete; Postgres doesn't auto-index FK columns.

_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_auth_attempts_session_id", "auth_attempts", "session_id"),
    ("ix_commands_session_id", "commands", "session_id"),
    ("ix_downloads_session_id", "downloads", "session_id"),
)


def upgrade() -> None:
    # CONCURRENTLY avoids blocking writes from the ingestor.
    # Ran outside a transaction, thus one autocommit_block per index.
    for index_name, table, column in _INDEXES:
        with op.get_context().autocommit_block():
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} "
                f"ON {table} ({column})"
            )


def downgrade() -> None:
    for index_name, _table, _column in _INDEXES:
        with op.get_context().autocommit_block():
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")
