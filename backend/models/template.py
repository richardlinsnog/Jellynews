


"""Template model — metadata for newsletter templates stored on disk."""

from __future__ import annotations

from datetime import datetime

from models.base import Base
from sqlalchemy import Boolean, DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    supports_channels: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    preview_image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    variables_required: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

