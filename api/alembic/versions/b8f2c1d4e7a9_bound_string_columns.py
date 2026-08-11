"""bound string columns to defend against attacker payload bloat

Revision ID: b8f2c1d4e7a9
Revises: 48be1097dd9b
Create Date: 2026-05-28 11:00:00.000000

Caps attacker-controlled string columns at the DB layer so any code path
that bypasses `ingestor/src/sanitize.truncate` still cannot insert unbounded
values. `USING substring(...)` truncates in place on populated tables.

The truncation is one-way: `downgrade()` restores the original column widths
but not the characters discarded by `upgrade()`, so this migration is not
data-reversible.
"""

import logging
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "b8f2c1d4e7a9"
down_revision: Union[str, Sequence[str], None] = "48be1097dd9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.runtime.migration")


_BOUNDS: tuple[tuple[str, str, int], ...] = (
    ("sessions", "id", 64),
    ("sessions", "protocol", 16),
    ("sessions", "sensor", 64),
    ("auth_attempts", "session_id", 64),
    ("auth_attempts", "username", 256),
    ("auth_attempts", "password", 256),
    ("commands", "session_id", 64),
    ("commands", "input", 8192),
    ("downloads", "session_id", 64),
    ("downloads", "url", 2048),
    ("downloads", "outfile", 512),
    ("downloads", "sha256", 64),
    ("geo_locations", "country_code", 2),
    ("geo_locations", "country", 128),
    ("geo_locations", "city", 128),
    ("geo_locations", "as_org", 256),
)


def upgrade() -> None:
    conn = op.get_bind()
    # Fail fast in prod instead of stalling indefinitely under write load.
    conn.execute(text("SET lock_timeout = '5s'"))
    conn.execute(text("SET statement_timeout = '10min'"))

    for table, column, length in _BOUNDS:
        n = conn.execute(
            text(f'SELECT count(*) FROM {table} WHERE length("{column}") > :n'),
            {"n": length},
        ).scalar()
        if n:
            log.info(
                "%s.%s: %d rows exceed %d chars and will be truncated",
                table,
                column,
                n,
                length,
            )
        op.execute(
            f'ALTER TABLE {table} ALTER COLUMN "{column}" '
            f"TYPE VARCHAR({length}) "
            f'USING substring("{column}" FROM 1 FOR {length})'
        )


def downgrade() -> None:
    for table, column, _ in _BOUNDS:
        op.execute(
            f'ALTER TABLE {table} ALTER COLUMN "{column}" TYPE VARCHAR'
        )
