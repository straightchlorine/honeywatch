"""top credentials default index

Revision ID: 35a3c30c5ef6
Revises: 1c8b46000780
Create Date: 2026-08-09 16:40:55.313783

The Credentials page's default view (stats.credentials.top_credentials with
by="pair", metric="attempts", outcome="any") runs `SELECT username, password,
count(*) FROM auth_attempts GROUP BY username, password ORDER BY count(*) DESC
LIMIT N` with no filter, so it hash-aggregates the whole table.

ix_auth_attempts_worked_creds (c9e3d1f4b6a2) only covers the `success` subset,
and ix_auth_attempts_username / ix_auth_attempts_password (1c8b46000780) are
single-column. A plain composite on (username, password) lets this query scan
the index instead of the table.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "35a3c30c5ef6"
down_revision: Union[str, Sequence[str], None] = "1c8b46000780"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_auth_attempts_username_password"


def upgrade() -> None:
    # CONCURRENTLY avoids blocking ingestor writes; runs outside a transaction.
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX} "
            "ON auth_attempts (username, password)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
