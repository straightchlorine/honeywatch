"""ssh client + direct-tcpip capture

Revision ID: e7c4a1b9f2d6
Revises: d3f7a2b9c1e5
Create Date: 2026-06-01 21:00:00.000000

Adds three tables for cowrie events the ingestor already parses but previously
dropped before Postgres:

  - ssh_clients          : per-session client banner + HASSH + offered algos
                           (cowrie.client.version / cowrie.client.kex)
  - client_fingerprints  : public keys offered at auth (cowrie.client.fingerprint)
  - direct_tcpip_requests: attempted port-forwards / relay intent
                           (cowrie.direct-tcpip.request)

All three FK sessions.id ON DELETE CASCADE, matching the existing child tables.
Purely additive: no existing table is touched.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7c4a1b9f2d6"
down_revision: Union[str, Sequence[str], None] = "d3f7a2b9c1e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ssh_clients",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("client_version", sa.String(length=256), nullable=True),
        sa.Column("hassh", sa.String(length=64), nullable=True),
        sa.Column("hassh_algorithms", sa.String(length=1024), nullable=True),
        sa.Column("kex_algorithms", sa.Text(), nullable=True),
        sa.Column("key_algorithms", sa.Text(), nullable=True),
        sa.Column("encryption_algorithms", sa.Text(), nullable=True),
        sa.Column("mac_algorithms", sa.Text(), nullable=True),
        sa.Column("compression_algorithms", sa.Text(), nullable=True),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_ssh_clients_hassh", "ssh_clients", ["hassh"])

    op.create_table(
        "client_fingerprints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=256), nullable=True),
        sa.Column("fingerprint", sa.String(length=512), nullable=False),
        sa.Column("fingerprint_type", sa.String(length=64), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_client_fingerprints_session_id", "client_fingerprints", ["session_id"]
    )
    op.create_index(
        "ix_client_fingerprints_fingerprint", "client_fingerprints", ["fingerprint"]
    )

    op.create_table(
        "direct_tcpip_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("dst_ip", sa.String(length=256), nullable=False),
        sa.Column("dst_port", sa.Integer(), nullable=False),
        sa.Column("src_ip", sa.String(length=256), nullable=True),
        sa.Column("src_port", sa.Integer(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_direct_tcpip_requests_session_id", "direct_tcpip_requests", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_direct_tcpip_requests_session_id", "direct_tcpip_requests")
    op.drop_table("direct_tcpip_requests")
    op.drop_index("ix_client_fingerprints_fingerprint", "client_fingerprints")
    op.drop_index("ix_client_fingerprints_session_id", "client_fingerprints")
    op.drop_table("client_fingerprints")
    op.drop_index("ix_ssh_clients_hassh", "ssh_clients")
    op.drop_table("ssh_clients")
