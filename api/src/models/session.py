from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.extensions import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    src_ip: Mapped[str] = mapped_column(String, nullable=False)
    src_port: Mapped[int] = mapped_column(Integer, nullable=False)
    dst_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    dst_port: Mapped[int] = mapped_column(Integer, default=22)
    protocol: Mapped[str] = mapped_column(String, default="ssh")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sensor: Mapped[str | None] = mapped_column(String, nullable=True)

    auth_attempts: Mapped[list["AuthAttempt"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    commands: Mapped[list["Command"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    downloads: Mapped[list["Download"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


from src.models.auth_attempt import AuthAttempt  # noqa: E402
from src.models.command import Command  # noqa: E402
from src.models.download import Download  # noqa: E402

__all__ = ["Session", "AuthAttempt", "Command", "Download"]
