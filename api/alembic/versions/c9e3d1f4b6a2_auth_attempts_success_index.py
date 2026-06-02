"""auth_attempts worked-credentials partial index

Revision ID: c9e3d1f4b6a2
Revises: e7c4a1b9f2d6
Create Date: 2026-06-01 22:30:00.000000

The Credentials page "credentials that worked" leaderboard runs
`SELECT username, password, count(*) FROM auth_attempts WHERE success
GROUP BY username, password ORDER BY count(*) DESC LIMIT N`
(StatsService.top_credentials(outcome="success")). Accepted attempts are a tiny
fraction of the table, so a *partial* index over just the `success = true` rows
keeps that subset cheap to scan as the table grows -- without the write cost /
bloat of indexing every (overwhelmingly failed) row.

The index keys on `(username, password)` (not just `success`) so it covers the
GROUP BY: with the columns in the index Postgres can satisfy the whole worked
query with an index-only scan and pre-sorted GroupAggregate, instead of an
index scan that still has to heap-fetch every row for the grouping keys.
Verified via EXPLAIN on the dev DB (Index Only Scan once the table is large
enough for the planner to prefer it over a seq scan).

This is the ONLY query the index serves. It deliberately does NOT help:
  * the accept-rate counter (StatsService.auth_outcomes) -- that uses
    `count(*) FILTER (WHERE success)` over the *whole* table with no
    statement-level WHERE, so a partial index is inapplicable; and
  * the session "compromised" classifier -- that correlates on `session_id`,
    a different access path.
Failed-only and all-rows aggregates still seq scan, which is correct.
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
