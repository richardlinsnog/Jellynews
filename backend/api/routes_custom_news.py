"""CustomNews CRUD endpoints with nh3 sanitization and status workflow."""

from api.deps import get_current_user
from api.rate_limit import limiter
from core.audit import audit_log
from core.database import get_db
from core.logging import get_logger
from core.sanitize import html_to_text, sanitize_html

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from models.custom_news import CustomNews, NewsStatus
from schemas.custom_news import (
    CustomNewsCreate,
    CustomNewsItem,
    CustomNewsListResponse,
    CustomNewsUpdate,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/news", tags=["custom-news"])

_CLIENT_IP = lambda r: r.client.host if r.client else "unknown"

_VALID_STATUSES = {s.value for s in NewsStatus}


def _to_item(n: CustomNews) -> CustomNewsItem:
    return CustomNewsItem.model_validate(n)


@router.get("", response_model=CustomNewsListResponse)
async def list_news(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> CustomNewsListResponse:
    stmt = select(CustomNews)
    count_stmt = select(func.count()).select_from(CustomNews)

    if status_filter and status_filter in _VALID_STATUSES:
        stmt = stmt.where(CustomNews.status == status_filter)
        count_stmt = count_stmt.where(CustomNews.status == status_filter)

    stmt = stmt.order_by(CustomNews.created_at.desc())

    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(stmt.offset(skip).limit(limit))
    items = [_to_item(n) for n in result.scalars().all()]

    return CustomNewsListResponse(items=items, total=total)


@router.get("/{news_id}", response_model=CustomNewsItem)
async def get_news(
    news_id: int,
    db: AsyncSession = Depends(get_db),
) -> CustomNewsItem:
    stmt = select(CustomNews).where(CustomNews.id == news_id)
    result = await db.execute(stmt)
    news = result.scalar_one_or_none()
    if news is None:
        raise HTTPException(status_code=404, detail="News item not found")
    return _to_item(news)


@router.post("", response_model=CustomNewsItem, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_news(
    request: Request,
    payload: CustomNewsCreate = Body(),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> CustomNewsItem:
    body_html = sanitize_html(payload.body_html)
    body_text = html_to_text(body_html)

    news_status = payload.status if payload.status in _VALID_STATUSES else NewsStatus.DRAFT

    author_id = int(current_user["sub"])
    news = CustomNews(
        title=payload.title.strip(),
        body_html=body_html,
        body_text=body_text,
        author_id=author_id,
        status=news_status,
    )
    db.add(news)
    await db.commit()
    await db.refresh(news)

    audit_log(
        db,
        user_id=author_id,
        action="custom_news.create",
        resource_type="custom_news",
        resource_id=str(news.id),
        ip_address=_CLIENT_IP(request),
    )

    logger.info("custom_news_created", news_id=news.id, author_id=author_id)
    return _to_item(news)


@router.patch("/{news_id}", response_model=CustomNewsItem)
@limiter.limit("30/minute")
async def update_news(
    news_id: int,
    payload: Annotated[CustomNewsUpdate, Body()],
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> CustomNewsItem:
    stmt = select(CustomNews).where(CustomNews.id == news_id)
    result = await db.execute(stmt)
    news = result.scalar_one_or_none()
    if news is None:
        raise HTTPException(status_code=404, detail="News item not found")

    if payload.title is not None:
        news.title = payload.title.strip()
    if payload.body_html is not None:
        news.body_html = sanitize_html(payload.body_html)
        news.body_text = html_to_text(news.body_html)
    if payload.status is not None:
        if payload.status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {payload.status}. Use one of: {_VALID_STATUSES}",
            )
        news.status = payload.status

    await db.commit()
    await db.refresh(news)

    audit_log(
        db,
        user_id=int(current_user["sub"]),
        action="custom_news.update",
        resource_type="custom_news",
        resource_id=str(news.id),
        ip_address=_CLIENT_IP(request),
    )

    logger.info("custom_news_updated", news_id=news.id, user_sub=current_user["sub"])
    return _to_item(news)


@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
@limiter.limit("20/minute")
async def delete_news(
    news_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> None:
    stmt = select(CustomNews).where(CustomNews.id == news_id)
    result = await db.execute(stmt)
    news = result.scalar_one_or_none()
    if news is None:
        raise HTTPException(status_code=404, detail="News item not found")

    await db.delete(news)
    await db.commit()

    audit_log(
        db,
        user_id=int(current_user["sub"]),
        action="custom_news.delete",
        resource_type="custom_news",
        resource_id=str(news_id),
        ip_address=_CLIENT_IP(request),
    )

    logger.info("custom_news_deleted", news_id=news_id, user_sub=current_user["sub"])
