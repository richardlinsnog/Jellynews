





import enum
from datetime import datetime

from models.base import Base
from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class SecretCategory(str, enum.Enum):
    SMTP = "smtp"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    NTFY = "ntfy"
    WEBHOOK = "webhook"
    JELLYFIN = "jellyfin"
    UNSUBSCRIBE = "unsubscribe"
    OTHER = "other"


class Secret(Base):
    __tablename__ = "secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[SecretCategory] = mapped_column(
        Enum(SecretCategory, name="secret_category", create_type=True),
        default=SecretCategory.OTHER,
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )





