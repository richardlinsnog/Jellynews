"""CustomNews CRUD endpoints with nh3 sanitization."""

from __future__ import annotations

from api.deps import get_current_user
from api.rate_limit import limiter
from core.database import get_db
from core.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from models.custom_news import CustomNews
from models.user import User
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


def sanitize_html(html: str) -> str:
    """Sanitize HTML using nh3 with allowed tags/attrs for newsletter content."""
    import nh3

    return nh3.clean(
        html,
        tags={
            "h1", "h2", "h3", "h4", "h5", "h6",
            "p", "br", "hr",
            "strong", "em", "b", "i", "u", "s", "sub", "sup",
            "a", "img",
            "ul", "ol", "li",
            "blockquote", "pre", "code",
            "table", "thead", "tbody", "tr", "th", "td",
            "div", "span",
        },
        attributes={
            "a": {"href", "title", "rel", "target"},
            "img": {"src", "alt", "width", "height"},
            "*": {"class", "style"},
        },
    )


def html_to_text(html: str) -> str:
    """Extract plain text from sanitized HTML for non-HTML channels."""
    import re

    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _to_item(n: CustomNews) -> CustomNewsItem:
    return CustomNewsItem.model_validate(n)


@router.get("", response_model=CustomNewsListResponse)
async def list_news(
    published_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> CustomNewsListResponse:
    stmt = select(CustomNews)
    if published_only:
        stmt = stmt.where(CustomNews.published.is_(True))
    stmt = stmt.order_by(CustomNews.created_at.desc())

    count_stmt = select(func.count()).select_from(CustomNews)
    if published_only:
        count_stmt = count_stmt.where(CustomNews.published.is_(True))
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
    body: CustomNewsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CustomNewsItem:
    body_html = sanitize_html(body.body_html)
    body_text = html_to_text(body_html)

    news = CustomNews(
        title=body.title.strip(),
        body_html=body_html,
        body_text=body_text,
        author_id=current_user.id,
        published=body.published,
    )
    db.add(news)
    await db.commit()
    await db.refresh(news)

    logger.info("custom_news_created", news_id=news.id, author_id=current_user.id)
    return _to_item(news)


@router.patch("/{news_id}", response_model=CustomNewsItem)
@limiter.limit("30/minute")
async def update_news(
    news_id: int,
    body: CustomNewsUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CustomNewsItem:
    stmt = select(CustomNews).where(CustomNews.id == news_id)
    result = await db.execute(stmt)
    news = result.scalar_one_or_none()
    if news is None:
        raise HTTPException(status_code=404, detail="News item not found")

    if body.title is not None:
        news.title = body.title.strip()
    if body.body_html is not None:
        news.body_html = sanitize_html(body.body_html)
        news.body_text = html_to_text(news.body_html)
    if body.published is not None:
        news.published = body.published

    await db.commit()
    await db.refresh(news)

    logger.info("custom_news_updated", news_id=news.id, author_id=current_user.id)
    return _to_item(news)


@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
@limiter.limit("20/minute")
async def delete_news(
    news_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    stmt = select(CustomNews).where(CustomNews.id == news_id)
    result = await db.execute(stmt)
    news = result.scalar_one_or_none()
    if news is None:
        raise HTTPException(status_code=404, detail="News item not found")

    await db.delete(news)
    await db.commit()

    logger.info("custom_news_deleted", news_id=news_id, author_id=current_user.id)
