



from __future__ import annotations

import datetime

from core.logging import get_logger
from models.media_log import ItemType, MediaLog
from schemas.jellyfin import JellyfinItem, JellyfinItemType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

_ITEM_TYPE_MAP: dict[JellyfinItemType, ItemType] = {
    JellyfinItemType.MOVIE: ItemType.MOVIE,
    JellyfinItemType.SERIES: ItemType.SERIES,
    JellyfinItemType.SEASON: ItemType.SEASON,
    JellyfinItemType.EPISODE: ItemType.EPISODE,
    JellyfinItemType.AUDIO: ItemType.AUDIO,
}


async def find_new_items(
    session: AsyncSession,
    items: list[JellyfinItem],
) -> list[JellyfinItem]:
    """Filter out items already present in MediaLog (idempotency check).

    Returns only items whose ``jellyfin_item_id`` is not yet recorded.
    """
    if not items:
        return []

    item_ids = [item.id for item in items]
    stmt = select(MediaLog.jellyfin_item_id).where(
        MediaLog.jellyfin_item_id.in_(item_ids),
    )
    result = await session.execute(stmt)
    known_ids = {row[0] for row in result.fetchall()}

    new_items = [item for item in items if item.id not in known_ids]
    if known_ids:
        logger.debug(
            "idempotency_filter",
            total=len(items),
            skipped=len(known_ids),
            new=len(new_items),
        )
    return new_items


async def record_notified_items(
    session: AsyncSession,
    items: list[JellyfinItem],
) -> None:
    """Record items in MediaLog after successful notification."""
    now = datetime.datetime.now(datetime.UTC)
    for item in items:
        log_entry = MediaLog(
            jellyfin_item_id=item.id,
            item_name=item.name,
            item_type=_ITEM_TYPE_MAP.get(item.type, ItemType.MOVIE),
            library_name=item.library_name or "Unknown",
            production_year=item.production_year,
            jellyfin_date_created=item.date_created,
            first_seen_at=now,
            last_notified_at=now,
            notified=True,
        )
        session.add(log_entry)
    await session.flush()

