

"""Subscriber CRUD, CSV import, and public unsubscribe endpoint."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from api.deps import get_current_user
from api.rate_limit import limiter
from core.database import get_db
from core.logging import get_logger
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from models.subscriber import Subscriber
from schemas.subscriber import (
    SubscriberCreate,
    SubscriberImportResult,
    SubscriberItem,
    SubscriberListResponse,
)
from services.vault import get_vault
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/subscribers", tags=["subscribers"])
unsub_router = APIRouter(prefix="/api/v1", tags=["unsubscribe"])


def _to_item(s: Subscriber) -> SubscriberItem:
    return SubscriberItem.model_validate(s)


# ── CRUD ───────────────────────────────────────────────────────────────


@router.get("", response_model=SubscriberListResponse)
async def list_subscribers(
    only_active: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> SubscriberListResponse:
    stmt = select(Subscriber)
    count_stmt = select(func.count()).select_from(Subscriber)

    if only_active:
        stmt = stmt.where(Subscriber.active.is_(True))
        count_stmt = count_stmt.where(Subscriber.active.is_(True))

    stmt = stmt.order_by(Subscriber.created_at.desc())

    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(stmt.offset(skip).limit(limit))
    items = [_to_item(s) for s in result.scalars().all()]

    return SubscriberListResponse(
        items=items, total=total, page=(skip // limit) + 1, page_size=limit,
    )


@router.post("", response_model=SubscriberItem, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_subscriber(
    request: Request,
    body: SubscriberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> SubscriberItem:
    email = body.email.lower().strip()

    existing = await db.execute(
        select(Subscriber).where(Subscriber.email == email),
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Subscriber '{email}' already exists",
        )

    subscriber = Subscriber(email=email, active=True)
    db.add(subscriber)
    await db.commit()
    await db.refresh(subscriber)

    logger.info("subscriber_created", subscriber_id=subscriber.id, email=email)
    return _to_item(subscriber)


@router.delete("/{subscriber_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
@limiter.limit("20/minute")
async def delete_subscriber(
    subscriber_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> None:
    stmt = select(Subscriber).where(Subscriber.id == subscriber_id)
    result = await db.execute(stmt)
    subscriber = result.scalar_one_or_none()
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    await db.delete(subscriber)
    await db.commit()

    logger.info(
        "subscriber_deleted",
        subscriber_id=subscriber_id,
        email=subscriber.email,
    )


# ── CSV Import ──────────────────────────────────────────────────────────


@router.post("/import", response_model=SubscriberImportResult)
@limiter.limit("5/minute")
async def import_subscribers_csv(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> SubscriberImportResult:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are accepted",
        )

    try:
        content = await file.read()
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded",
        ) from None

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file appears to be empty",
        )

    email_col = None
    for name in reader.fieldnames:
        if name.strip().lower() in ("email", "e-mail", "mail"):
            email_col = name
            break

    if email_col is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain a column named 'email', 'e-mail', or 'mail'",
        )

    imported = 0
    skipped = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):
        raw = (row.get(email_col) or "").strip().lower()
        if not raw:
            errors.append(f"Row {row_num}: empty email")
            continue

        if "@" not in raw or len(raw) > 320:
            errors.append(f"Row {row_num}: invalid email '{raw[:60]}...'")
            continue

        existing = await db.execute(
            select(Subscriber).where(Subscriber.email == raw),
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue

        db.add(Subscriber(email=raw, active=True))
        imported += 1

    await db.commit()

    logger.info(
        "subscribers_imported",
        imported=imported,
        skipped=skipped,
        errors_count=len(errors),
        user_sub=current_user["sub"],
    )

    return SubscriberImportResult(
        imported=imported,
        skipped=skipped,
        errors=errors[:50],
    )


# ── Public Unsubscribe ──────────────────────────────────────────────────


@unsub_router.get("/unsubscribe/{token}")
@limiter.limit("10/minute")
async def unsubscribe(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    vault = get_vault()

    try:
        plain = vault.decrypt(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired unsubscribe link",
        ) from None

    if not plain.startswith("unsub:"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid unsubscribe token format",
        )

    parts = plain.split(":", 2)
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid unsubscribe token format",
        )

    try:
        subscriber_id = int(parts[1])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid unsubscribe token",
        ) from None

    stmt = select(Subscriber).where(
        Subscriber.id == subscriber_id,
        Subscriber.active.is_(True),
    )
    result = await db.execute(stmt)
    subscriber = result.scalar_one_or_none()

    if subscriber is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscriber not found or already unsubscribed",
        )

    subscriber.active = False
    subscriber.unsubscribed_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info("subscriber_unsubscribed", subscriber_id=subscriber_id, email=subscriber.email)

    return {"message": "You have been unsubscribed successfully", "email": subscriber.email}

