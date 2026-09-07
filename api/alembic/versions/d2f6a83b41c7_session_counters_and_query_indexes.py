"""session counters, interest score and query indexes

Revision ID: d2f6a83b41c7
Revises: 35a3c30c5ef6
Create Date: 2026-09-07 13:40:00.000000

Backs the Sessions explorer: sorting by "interesting" and filtering by
has=commands,downloads,success,tcpip without a per-request aggregate scan.
The counter columns are maintained by the ingestor, one UPDATE per child-row
insert in the same transaction (ingestor/src/writer.py), and `interest` is
derived from them by the database.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2f6a83b41c7"
down_revision: Union[str, Sequence[str], None] = "35a3c30c5ef6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DOWNLOADS_SHA256_INDEX = "ix_downloads_sha256"


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("n_commands", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "sessions",
        sa.Column("n_downloads", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "sessions",
        sa.Column("n_tcpip", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "sessions",
        sa.Column("auth_success", sa.Boolean, nullable=False, server_default="false"),
    )

    # Backfill BEFORE the generated column exists, so `interest` materializes
    # on its own from the already-correct counters. At ~344k sessions these
    # single-statement backfills run in seconds; revisit batching only past
    # roughly 10M child rows.
    op.execute("""
        UPDATE sessions s SET n_commands = c.n
        FROM (SELECT session_id, COUNT(*) AS n FROM commands GROUP BY session_id) c
        WHERE c.session_id = s.id
    """)
    op.execute("""
        UPDATE sessions s SET n_downloads = d.n
        FROM (SELECT session_id, COUNT(*) AS n FROM downloads GROUP BY session_id) d
        WHERE d.session_id = s.id
    """)
    op.execute("""
        UPDATE sessions s SET n_tcpip = t.n
        FROM (SELECT session_id, COUNT(*) AS n FROM direct_tcpip_requests GROUP BY session_id) t
        WHERE t.session_id = s.id
    """)
    op.execute("""
        UPDATE sessions s SET auth_success = true
        WHERE EXISTS (SELECT 1 FROM auth_attempts a
                      WHERE a.session_id = s.id AND a.success)
    """)

    op.add_column(
        "sessions",
        sa.Column(
            "interest",
            sa.Integer,
            sa.Computed(
                "2*n_commands + 5*n_downloads + 2*n_tcpip + (auth_success::int)*3",
                persisted=True,
            ),
        ),
    )
    op.create_index(
        "ix_sessions_interest",
        "sessions",
        [sa.text("interest DESC"), sa.text("started_at DESC")],
    )

    # sessions_pkey is a btree under the database's non-C collation, which a
    # LIKE 'prefix%' predicate cannot use, so `GET /sessions?q=` degrades to a
    # sequential scan. varchar_pattern_ops orders by raw byte value, turning it
    # into an index range scan.
    op.create_index(
        "ix_sessions_id_pattern", "sessions", [sa.text("id varchar_pattern_ops")]
    )

    # Without this the specimen GROUP BY and the /sessions?sha256= EXISTS both
    # seq-scan downloads. Partial on NOT NULL: a failed fetch is stored for its
    # URL alone with sha256 NULL, and neither query can match one.
    # CONCURRENTLY avoids blocking writes from the ingestor.
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_DOWNLOADS_SHA256_INDEX} "
            "ON downloads (sha256) WHERE sha256 IS NOT NULL"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_DOWNLOADS_SHA256_INDEX}")
    op.drop_index("ix_sessions_id_pattern", table_name="sessions")
    op.drop_index("ix_sessions_interest", table_name="sessions")
    op.drop_column("sessions", "interest")
    op.drop_column("sessions", "auth_success")
    op.drop_column("sessions", "n_tcpip")
    op.drop_column("sessions", "n_downloads")
    op.drop_column("sessions", "n_commands")
