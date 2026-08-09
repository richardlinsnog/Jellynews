


"""AuditLog read endpoints — admin only."""

from __future__ import annotations

from api.deps import get_current_user, get_db
from api.rate_limit import limiter
from core.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from models.audit_log import AuditLog
from models.user import UserRole
from schemas.audit_log import AuditLogItem, AuditLogListResponse
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


def _require_admin(payload: dict = Depends(get_current_user)) -> dict:
    role = payload.get("role", "")
    if role not in (UserRole.OWNER.value, "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner role required",
        )
    return payload


def _to_item(a: AuditLog) -> AuditLogItem:
    return AuditLogItem.model_validate(a)


@router.get("", response_model=AuditLogListResponse)
@limiter.limit("30/minute")
async def list_audit_logs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(_require_admin),
) -> AuditLogListResponse:
    base = select(AuditLog)

    if action:
        base = base.where(AuditLog.action == action)
    if resource_type:
        base = base.where(AuditLog.resource_type == resource_type)

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    items_q = (
        base.order_by(desc(AuditLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(items_q)).scalars().all()

    return AuditLogListResponse(
        items=[_to_item(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


