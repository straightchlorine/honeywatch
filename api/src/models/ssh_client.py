from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.extensions import Base

if TYPE_CHECKING:
    from src.models.session import Session


class SshClientProfile(Base):
    """One distinct SSH client handshake (hassh and the algorithm lists).

    Hundreds of values cover millions of sessions, so sessions point here
    instead of each carrying its own 1.2 kB copy. `digest` is
    md5(row(<the seven columns>)::text), computed by Postgres in the ingestor's
    upsert and in the migration that created this table.
    """

    __tablename__ = "ssh_client_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    digest: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    hassh: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hassh_algorithms: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    kex_algorithms: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_algorithms: Mapped[str | None] = mapped_column(Text, nullable=True)
    encryption_algorithms: Mapped[str | None] = mapped_column(Text, nullable=True)
    mac_algorithms: Mapped[str | None] = mapped_column(Text, nullable=True)
    compression_algorithms: Mapped[str | None] = mapped_column(Text, nullable=True)


class SshClient(Base):
    """Per-session SSH client identity, populated from separate cowrie events."""

    __tablename__ = "ssh_clients"

    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    client_version: Mapped[str | None] = mapped_column(String(256), nullable=True)
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("ssh_client_profiles.id"), nullable=True
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped[Session] = relationship(back_populates="ssh_client", uselist=False)
