from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.extensions import Base


class SshClient(Base):
    """Per-session SSH client identity.

    Populated from cowrie's ``cowrie.client.version`` (the client banner) and
    ``cowrie.client.kex`` (the HASSH fingerprint + offered algorithms). One row
    per session; the two events arrive separately and each upserts its columns.
    The HASSH is the highest-value signal for clustering bot families that
    otherwise rotate IPs and usernames.
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


__all__ = ["SshClient"]
