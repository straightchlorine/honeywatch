"""auth_attempts success partial index

Revision ID: c9e3d1f4b6a2
Revises: e7c4a1b9f2d6
Create Date: 2026-06-01 22:30:00.000000

The Credentials page filters auth attempts by cowrie outcome
(`WHERE success` for the "credentials that worked" leaderboard and the
accept-rate counter). Accepted attempts are a tiny fraction of the table -- a
*partial* index over just the `success = true` rows keeps that subset cheap to
scan as the table grows, without the write cost / bloat of indexing every
(overwhelmingly failed) row. Failed-only and full-table aggregates still seq
scan, which is correct for an all-rows GROUP BY.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c9e3d1f4b6a2"
down_revision: Union[str, Sequence[str], None] = "e7c4a1b9f2d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_auth_attempts_success_true"


def upgrade() -> None:
    # CONCURRENTLY avoids blocking ingestor writes; runs outside a transaction.
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX} "
            "ON auth_attempts (success) WHERE success"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
