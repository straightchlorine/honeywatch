"""country and src_ip indexes

Revision ID: d3f7a2b9c1e5
Revises: b8f2c1d4e7a9
Create Date: 2026-06-01 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "d3f7a2b9c1e5"
down_revision: Union[str, Sequence[str], None] = "b8f2c1d4e7a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Both columns drive the new country filter / scope added with the sessions
# browser + activity analytics:
#   - geo_locations.country_code: filtered on every country-scoped sessions and
#     stats query (`WHERE country_code = :code`).
#   - sessions.src_ip: keyed by the geo outer-join on every page and every
#     country-scoped stat (`GeoLocation.ip == Session.src_ip`); also backs
#     COUNT(DISTINCT src_ip). Postgres does not auto-index either column.

_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_geo_locations_country_code", "geo_locations", "country_code"),
    ("ix_sessions_src_ip", "sessions", "src_ip"),
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
