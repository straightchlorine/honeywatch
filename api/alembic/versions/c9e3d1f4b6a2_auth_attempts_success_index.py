"""auth_attempts worked-credentials partial index

Revision ID: c9e3d1f4b6a2
Revises: e7c4a1b9f2d6
Create Date: 2026-06-01 22:30:00.000000

The Credentials page "credentials that worked" leaderboard runs
`SELECT username, password, count(*) FROM auth_attempts WHERE success
GROUP BY username, password ORDER BY count(*) DESC LIMIT N`
(StatsService.top_credentials(outcome="success")).

Accepted attempts are a tiny fraction of the table, so a *partial* index over
just the `success = true` rows keeps that subset cheap to scan as the table grows.

The index keys on `(username, password)` (not just `success`) so it covers the
GROUP BY.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c9e3d1f4b6a2"
down_revision: Union[str, Sequence[str], None] = "e7c4a1b9f2d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_auth_attempts_worked_creds"


def upgrade() -> None:
    # CONCURRENTLY avoids blocking ingestor writes; runs outside a transaction.
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX} "
            "ON auth_attempts (username, password) WHERE success"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
