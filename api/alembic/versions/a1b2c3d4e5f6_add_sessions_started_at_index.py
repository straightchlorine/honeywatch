"""add index on sessions.started_at

Revision ID: a1b2c3d4e5f6
Revises: c5a96dd61fe7
Create Date: 2026-05-27 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c5a96dd61fe7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Stats endpoints filter and group by sessions.started_at (activity buckets,
# trend, heatmap). Without this index queries degrade into sequential scans
# once the table grows.

INDEX_NAME = "ix_sessions_started_at"
TABLE = "sessions"
COLUMN = "started_at"


def upgrade() -> None:
    # CONCURRENTLY avoids blocking writes from the ingestor on prod. Must run
    # outside a transaction, hence autocommit_block.
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            f"ON {TABLE} ({COLUMN})"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
