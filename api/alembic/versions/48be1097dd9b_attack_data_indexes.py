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


# Each index backs a specific query path under api/src/services/:
#
#   ix_auth_attempts_session_id   - selectinload of auth_attempts when a
#                                   session detail is fetched, plus FK
#                                   cascade-delete lookup.
#   ix_auth_attempts_username     - top_usernames GROUP BY username.
#   ix_auth_attempts_password     - top_passwords GROUP BY password.
#   ix_commands_session_id        - selectinload of commands per session.
#   ix_downloads_session_id       - selectinload of downloads per session.
#   ix_geo_locations_country_code - top_countries GROUP BY country_code
#                                   after sessions LEFT JOIN geo_locations.

_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_auth_attempts_session_id", "auth_attempts", "session_id"),
    ("ix_auth_attempts_username", "auth_attempts", "username"),
    ("ix_auth_attempts_password", "auth_attempts", "password"),
    ("ix_commands_session_id", "commands", "session_id"),
    ("ix_downloads_session_id", "downloads", "session_id"),
    ("ix_geo_locations_country_code", "geo_locations", "country_code"),
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
