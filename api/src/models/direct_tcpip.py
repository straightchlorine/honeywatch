from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.extensions import Base

if TYPE_CHECKING:
    from src.models.session import Session


class DirectTcpipRequest(Base):
    """An attempted port-forward through the honeypot (`cowrie.direct-tcpip.request`).
    Attacker trying to use it as a relay; the egress sidecar blocks the forward,
    this just records the intent.

    `dst_ip` may be a hostname, so it's text rather than INET.
    """

    __tablename__ = "direct_tcpip_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    dst_ip: Mapped[str] = mapped_column(String(256), nullable=False)
    dst_port: Mapped[int] = mapped_column(Integer, nullable=False)
    src_ip: Mapped[str | None] = mapped_column(String(256), nullable=True)
    src_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped[Session] = relationship(back_populates="direct_tcpip_requests")
