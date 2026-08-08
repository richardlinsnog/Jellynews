






import enum
from datetime import datetime

from models.base import Base
from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column


class ItemType(str, enum.Enum):
    MOVIE = "Movie"
    SERIES = "Series"
    AUDIO = "Audio"
    SEASON = "Season"
    EPISODE = "Episode"


class MediaLog(Base):
    __tablename__ = "media_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jellyfin_item_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    item_name: Mapped[str] = mapped_column(String(500), nullable=False)
    item_type: Mapped[ItemType] = mapped_column(
        Enum(ItemType, name="item_type", create_type=True),
        nullable=False,
    )
    library_name: Mapped[str] = mapped_column(String(255), nullable=False)
    production_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jellyfin_date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_notified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)






