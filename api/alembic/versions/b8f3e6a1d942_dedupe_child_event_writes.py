"""dedupe child event writes on (session_id, timestamp)

Revision ID: b8f3e6a1d942
Revises: d2f6a83b41c7
Create Date: 2026-09-11 12:00:00.000000

Retry (ingestor/src/reliability.py) assumes write_event is idempotent and
retries on any psycopg.Error, but only sessions/ssh_clients/geo_locations
actually are (ON CONFLICT/upsert). If a write commits but the client sees
an error anyway (an ambiguous outcome - e.g. the connection drops between
COMMIT and the ack), Retry re-inserts the identical event into these five
tables, which had no unique constraint to catch it.

(session_id, timestamp) is safe as the dedupe key: cowrie timestamps carry
microsecond precision, stored losslessly in TIMESTAMPTZ, and a retried
write passes the exact same event object twice - identical timestamp both
times. ingestor/src/writer.py now adds ON CONFLICT (session_id, timestamp)
DO NOTHING on each of these tables' INSERT.

CONCURRENTLY avoids blocking the ingestor's writes.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b8f3e6a1d942"
down_revision: Union[str, Sequence[str], None] = "d2f6a83b41c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = {
    "ux_auth_attempts_session_id_timestamp": "auth_attempts",
    "ux_commands_session_id_timestamp": "commands",
    "ux_downloads_session_id_timestamp": "downloads",
    "ux_client_fingerprints_session_id_timestamp": "client_fingerprints",
    "ux_direct_tcpip_requests_session_id_timestamp": "direct_tcpip_requests",
}


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for name, table in _INDEXES.items():
            op.execute(
                f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {name} "
                f"ON {table} (session_id, timestamp)"
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name in _INDEXES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
