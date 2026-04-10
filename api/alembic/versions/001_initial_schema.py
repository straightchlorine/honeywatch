"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("src_ip", postgresql.INET(), nullable=False),
        sa.Column("src_port", sa.Integer(), nullable=False),
        sa.Column("dst_ip", postgresql.INET(), nullable=True),
        sa.Column("dst_port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("protocol", sa.String(), nullable=False, server_default="ssh"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sensor", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sessions_src_ip", "sessions", ["src_ip"])
    op.create_index("idx_sessions_started_at", "sessions", ["started_at"])

    op.create_table(
        "auth_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password", sa.String(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_auth_attempts_session", "auth_attempts", ["session_id"])
    op.create_index("idx_auth_attempts_timestamp", "auth_attempts", ["timestamp"])
    op.create_index("idx_auth_attempts_username", "auth_attempts", ["username"])

    op.create_table(
        "commands",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("input", sa.String(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_commands_session", "commands", ["session_id"])

    op.create_table(
        "downloads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("outfile", sa.String(), nullable=True),
        sa.Column("sha256", sa.String(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_downloads_session", "downloads", ["session_id"])
    op.create_index("idx_downloads_sha256", "downloads", ["sha256"])

    op.create_table(
        "geo_locations",
        sa.Column("ip", postgresql.INET(), nullable=False),
        sa.Column("country_code", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("asn", sa.Integer(), nullable=True),
        sa.Column("as_org", sa.String(), nullable=True),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("ip"),
    )


def downgrade() -> None:
    op.drop_table("geo_locations")
    op.drop_table("downloads")
    op.drop_table("commands")
    op.drop_table("auth_attempts")
    op.drop_table("sessions")
