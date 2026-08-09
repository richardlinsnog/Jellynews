
"""DeliveryLog model — records newsletter delivery attempts per channel."""

from __future__ import annotations

from datetime import datetime

from models.base import Base
from sqlalchemy import JSON, Boolean, DateTime, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class DeliveryLog(Base):
    __tablename__ = "delivery_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

