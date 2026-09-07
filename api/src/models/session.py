from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Computed, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.extensions import Base

if TYPE_CHECKING:
    from src.models.auth_attempt import AuthAttempt
    from src.models.client_fingerprint import ClientFingerprint
    from src.models.command import Command
    from src.models.direct_tcpip import DirectTcpipRequest
    from src.models.download import Download
    from src.models.ssh_client import SshClient


class Session(Base):
    """A single cowrie SSH/Telnet session and its aggregated child events."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    src_ip: Mapped[str] = mapped_column(INET, nullable=False)
    src_port: Mapped[int] = mapped_column(Integer, nullable=False)
    dst_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    dst_port: Mapped[int] = mapped_column(Integer, default=22)
    protocol: Mapped[str] = mapped_column(String(16), default="ssh")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sensor: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Maintained by the ingestor (one UPDATE per child-row insert, same
    # transaction - see ingestor/src/writer.py) so the Sessions explorer can
    # sort/filter without a per-request aggregate scan. `interest` is a
    # Postgres GENERATED ALWAYS column; never assign it from Python.
    n_commands: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_tcpip: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auth_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interest: Mapped[int] = mapped_column(
        Integer,
        Computed(
            "2*n_commands + 5*n_downloads + 2*n_tcpip + (auth_success::int)*3",
            persisted=True,
        ),
    )

    auth_attempts: Mapped[list[AuthAttempt]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    commands: Mapped[list[Command]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    downloads: Mapped[list[Download]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    ssh_client: Mapped[SshClient | None] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )
    client_fingerprints: Mapped[list[ClientFingerprint]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    direct_tcpip_requests: Mapped[list[DirectTcpipRequest]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
