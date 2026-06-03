"""geo_locations country/asn partial index

Revision ID: f4a9c2e1b8d7
Revises: c9e3d1f4b6a2
Create Date: 2026-06-03 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "f4a9c2e1b8d7"
down_revision: Union[str, Sequence[str], None] = "c9e3d1f4b6a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The Countries detail panel's ASN breakdown runs

# `WHERE asn IS NOT NULL [AND country_code = :code] GROUP BY asn, as_org`.

# It's scoped to one origin and polled while a country is selected. A partial
# composite index on (country_code, asn) supports both the country scope and
# the GROUP BY without scanning every geo row;
_INDEX_NAME = "ix_geo_locations_country_asn"


def upgrade() -> None:
    # CONCURRENTLY avoids blocking writes from the ingestor
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME} "
            "ON geo_locations (country_code, asn) WHERE asn IS NOT NULL"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
