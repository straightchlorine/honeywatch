from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.extensions import Base

if TYPE_CHECKING:
    from src.models.session import Session


class SshClient(Base):
    """Per-session SSH client identity.

    One row per session, filled in by two separate cowrie events (`client.version`
    and `client.kex`); `first_seen` is stamped by whichever lands first, so columns
    from the other event may be null.
    """

    __tablename__ = "ssh_clients"

    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    client_version: Mapped[str | None] = mapped_column(String(256), nullable=True)
    hassh: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hassh_algorithms: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    kex_algorithms: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_algorithms: Mapped[str | None] = mapped_column(Text, nullable=True)
    encryption_algorithms: Mapped[str | None] = mapped_column(Text, nullable=True)
    mac_algorithms: Mapped[str | None] = mapped_column(Text, nullable=True)
    compression_algorithms: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped[Session] = relationship(back_populates="ssh_client", uselist=False)
