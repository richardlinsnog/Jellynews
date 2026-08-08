

"""Unit tests for idempotency service using MediaLog model."""

from __future__ import annotations

import datetime

import pytest
from models.media_log import ItemType, MediaLog
from schemas.jellyfin import JellyfinItem, JellyfinItemType
from services.idempotency import find_new_items, record_notified_items
from sqlalchemy import select


def _make_item(
    item_id: str = "abc123",
    name: str = "Test Item",
    item_type: JellyfinItemType = JellyfinItemType.MOVIE,
    date_created: datetime.datetime | None = None,
) -> JellyfinItem:
    return JellyfinItem(
        **{
            "Id": item_id,
            "Name": name,
            "Type": item_type,
            "ProductionYear": 2024,
            "DateCreated": date_created or datetime.datetime(
                2024, 1, 15, tzinfo=datetime.UTC,
            ),
        },
    )


# ---------------------------------------------------------------------------
# find_new_items
# ---------------------------------------------------------------------------


class TestFindNewItems:
    @pytest.mark.asyncio
    async def test_all_new_when_media_log_empty(self, db) -> None:
        items = [_make_item("i1"), _make_item("i2")]
        result = await find_new_items(db, items)
        assert len(result) == 2
        assert {i.id for i in result} == {"i1", "i2"}

    @pytest.mark.asyncio
    async def test_filters_out_known_items(self, db) -> None:
        now = datetime.datetime.now(datetime.UTC)
        db.add(
            MediaLog(
                jellyfin_item_id="i1",
                item_name="Already Seen",
                item_type=ItemType.MOVIE,
                library_name="Movies",
                jellyfin_date_created=now,
                first_seen_at=now,
                last_notified_at=now,
                notified=True,
            ),
        )
        await db.commit()

        items = [_make_item("i1"), _make_item("i2")]
        result = await find_new_items(db, items)
        assert len(result) == 1
        assert result[0].id == "i2"

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self, db) -> None:
        result = await find_new_items(db, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_all_known_returns_empty(self, db) -> None:
        now = datetime.datetime.now(datetime.UTC)
        db.add(
            MediaLog(
                jellyfin_item_id="i1",
                item_name="Seen A",
                item_type=ItemType.SERIES,
                library_name="TV",
                jellyfin_date_created=now,
                first_seen_at=now,
                last_notified_at=now,
                notified=True,
            ),
        )
        await db.commit()

        items = [_make_item("i1", item_type=JellyfinItemType.SERIES)]
        result = await find_new_items(db, items)
        assert result == []


# ---------------------------------------------------------------------------
# record_notified_items
# ---------------------------------------------------------------------------


class TestRecordNotifiedItems:
    @pytest.mark.asyncio
    async def test_records_items_in_media_log(self, db) -> None:
        item = _make_item("new-item", "New Movie", JellyfinItemType.MOVIE)
        await record_notified_items(db, [item])
        await db.commit()

        stmt = select(MediaLog).where(MediaLog.jellyfin_item_id == "new-item")
        result = await db.execute(stmt)
        log = result.scalar_one()
        assert log.item_name == "New Movie"
        assert log.item_type == ItemType.MOVIE
        assert log.notified is True
        assert log.first_seen_at is not None
        assert log.last_notified_at is not None

    @pytest.mark.asyncio
    async def test_maps_all_item_types_correctly(self, db) -> None:
        """Verify the type mapping covers all JellyfinItemType variants."""
        from services.idempotency import _ITEM_TYPE_MAP

        for jf_type in JellyfinItemType:
            assert jf_type in _ITEM_TYPE_MAP, f"Missing mapping for {jf_type}"
            assert isinstance(_ITEM_TYPE_MAP[jf_type], ItemType)

    @pytest.mark.asyncio
    async def test_records_multiple_items(self, db) -> None:
        items = [
            _make_item("a", "Movie A", JellyfinItemType.MOVIE),
            _make_item("b", "Series B", JellyfinItemType.SERIES),
            _make_item("c", "Episode C", JellyfinItemType.EPISODE),
        ]
        await record_notified_items(db, items)
        await db.commit()

        stmt = select(MediaLog).where(
            MediaLog.jellyfin_item_id.in_(["a", "b", "c"]),
        )
        result = await db.execute(stmt)
        logs = list(result.scalars().all())
        assert len(logs) == 3


# ---------------------------------------------------------------------------
# Idempotency end-to-end (find → record → re-find)
# ---------------------------------------------------------------------------


class TestIdempotencyEndToEnd:
    @pytest.mark.asyncio
    async def test_find_record_then_refind_returns_empty(self, db) -> None:
        items = [_make_item("idem-1"), _make_item("idem-2")]

        # First pass: all new
        new1 = await find_new_items(db, items)
        assert len(new1) == 2

        # Record them
        await record_notified_items(db, new1)
        await db.commit()

        # Second pass: all known
        new2 = await find_new_items(db, items)
        assert len(new2) == 0

    @pytest.mark.asyncio
    async def test_partial_overlap(self, db) -> None:
        first_batch = [_make_item("x1"), _make_item("x2")]
        await record_notified_items(db, first_batch)
        await db.commit()

        second_batch = [_make_item("x1"), _make_item("x3")]
        new_items = await find_new_items(db, second_batch)
        assert len(new_items) == 1
        assert new_items[0].id == "x3"

