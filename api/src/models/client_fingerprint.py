from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.extensions import Base

if TYPE_CHECKING:
    from src.models.session import Session


class ClientFingerprint(Base):
    """A public-key offered during authentication (``cowrie.client.fingerprint``).

    Bots that spray a fixed SSH key across many targets are linked by their key
    fingerprint even when IP and username vary.

    Multiple rows per session are expected.
    """

    __tablename__ = "client_fingerprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(256), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(512), nullable=False)
    fingerprint_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped[Session] = relationship(back_populates="client_fingerprints")


__all__ = ["ClientFingerprint"]
