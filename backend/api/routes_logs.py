"""Delivery logs read-only endpoint."""

from __future__ import annotations

from api.deps import get_current_user
from core.database import get_db
from fastapi import APIRouter, Depends, Query
from models.delivery_log import DeliveryLog
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/logs", tags=["delivery-logs"])


class DeliveryLogItem(BaseModel):
    id: int
    channel_id: int
    success: bool
    status_message: str | None = None
    payload_summary: dict | None = None
    created_at: str

    model_config = {"from_attributes": True}


class DeliveryLogListResponse(BaseModel):
    items: list[DeliveryLogItem]
    total: int


@router.get("", response_model=DeliveryLogListResponse)
async def list_logs(
    channel_id: int | None = Query(None),
    success: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
) -> DeliveryLogListResponse:
    stmt = select(DeliveryLog)
    count_stmt = select(func.count()).select_from(DeliveryLog)

    if channel_id is not None:
        stmt = stmt.where(DeliveryLog.channel_id == channel_id)
        count_stmt = count_stmt.where(DeliveryLog.channel_id == channel_id)
    if success is not None:
        stmt = stmt.where(DeliveryLog.success == success)
        count_stmt = count_stmt.where(DeliveryLog.success == success)

    stmt = stmt.order_by(DeliveryLog.created_at.desc())

    total = (await db.execute(count_stmt)).scalar() or 0

    result = await db.execute(stmt.offset(skip).limit(limit))
    items = [
        DeliveryLogItem(
            id=log.id,
            channel_id=log.channel_id,
            success=log.success,
            status_message=log.status_message,
            payload_summary=log.payload_summary,
            created_at=log.created_at.isoformat() if log.created_at else "",
        )
        for log in result.scalars().all()
    ]

    return DeliveryLogListResponse(items=items, total=total)
