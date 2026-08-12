
"""Subscriber model: newsletter recipients with per-channel destinations.

Each subscriber has optional destination fields (email, phone, telegram_chat_id).
A filled field means that channel is enabled for this subscriber.
Subscribers with no filled fields receive no newsletters.

Tags are stored as a comma-separated string for simple grouping (e.g. "testing,kids").
"""

from __future__ import annotations

from datetime import datetime, timezone

from models.base import Base
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, default=None, index=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True, default=None)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(120), nullable=True, default=None)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
    )
