

"""Subscriber CRUD, CSV import, bulk delete, Jellyfin sync, and public unsubscribe endpoint."""
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
    SubscriberUpdate,
)
from services.vault import get_vault
from sqlalchemy import func, select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/subscribers", tags=["subscribers"])
unsub_router = APIRouter(prefix="/api/v1", tags=["unsubscribe"])


def _to_item(s: Subscriber) -> SubscriberItem:
    return SubscriberItem.model_validate(s)


def _clean_tags(raw: str | None) -> str | None:
    """Normalise comma-separated tags: trim, lower-case, deduplicate."""
    if not raw or not raw.strip():
        return None
    seen: set[str] = set()
    cleaned: list[str] = []
    for tag in raw.split(","):
        t = tag.strip().lower()
        if t and t not in seen:
            seen.add(t)
            cleaned.append(t)
    return ", ".join(cleaned) if cleaned else None


# ── CRUD ───────────────────────────────────────────────────────────────


@router.get("/tags", response_model=list[str])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[str]:
    """Return all unique tags across all subscribers."""
    stmt = select(Subscriber.tags).where(Subscriber.tags.isnot(None), Subscriber.tags != "")
    result = await db.execute(stmt)
    all_tags: set[str] = set()
    for row in result.scalars().all():
        for tag in row.split(","):
            t = tag.strip().lower()
            if t:
                all_tags.add(t)
    return sorted(all_tags)


@router.get("", response_model=SubscriberListResponse)
async def list_subscribers(
    only_active: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
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
    email_val = body.email.strip().lower() if body.email else None

    subscriber = Subscriber(
        name=body.name,
        email=email_val,
        phone=body.phone,
        telegram_chat_id=body.telegram_chat_id,
        tags=_clean_tags(body.tags),
        active=True,
    )
    db.add(subscriber)
    await db.commit()
    await db.refresh(subscriber)

    logger.info("subscriber_created", subscriber_id=subscriber.id, email=email_val)
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

    logger.info("subscriber_deleted", subscriber_id=subscriber_id)


@router.patch("/{subscriber_id}", response_model=SubscriberItem)
@limiter.limit("30/minute")
async def update_subscriber(
    subscriber_id: int,
    body: SubscriberUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> SubscriberItem:
    stmt = select(Subscriber).where(Subscriber.id == subscriber_id)
    result = await db.execute(stmt)
    subscriber = result.scalar_one_or_none()
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    if body.name is not None:
        subscriber.name = body.name
    if body.email is not None:
        subscriber.email = body.email.strip().lower() or None
    if body.phone is not None:
        subscriber.phone = body.phone or None
    if body.telegram_chat_id is not None:
        subscriber.telegram_chat_id = body.telegram_chat_id or None
    if body.tags is not None:
        subscriber.tags = _clean_tags(body.tags)

    if body.active is not None:
        subscriber.active = body.active
        if body.active:
            subscriber.unsubscribed_at = None
        elif subscriber.unsubscribed_at is None:
            subscriber.unsubscribed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(subscriber)

    logger.info("subscriber_updated", subscriber_id=subscriber_id)
    return _to_item(subscriber)


# ── Bulk Delete ────────────────────────────────────────────────────────


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def bulk_delete_subscribers(
    request: Request,
    ids: list[int],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not ids:
        raise HTTPException(status_code=400, detail="No subscriber IDs provided")

    stmt = delete(Subscriber).where(Subscriber.id.in_(ids))
    result = await db.execute(stmt)
    await db.commit()

    deleted = result.rowcount
    logger.info(
        "subscribers_bulk_deleted",
        count=deleted,
        requested=len(ids),
        user_sub=current_user["sub"],
    )
    return {"deleted": deleted, "requested": len(ids)}


# ── Bulk Activate / Deactivate ────────────────────────────────────────


@router.post("/bulk-activate", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def bulk_activate_subscribers(
    request: Request,
    ids: list[int],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not ids:
        raise HTTPException(status_code=400, detail="No subscriber IDs provided")

    stmt = (
        update(Subscriber)
        .where(Subscriber.id.in_(ids))
        .values(active=True, unsubscribed_at=None)
    )
    result = await db.execute(stmt)
    await db.commit()

    updated = result.rowcount
    logger.info(
        "subscribers_bulk_activated",
        count=updated,
        requested=len(ids),
        user_sub=current_user["sub"],
    )
    return {"updated": updated, "requested": len(ids)}


@router.post("/bulk-deactivate", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def bulk_deactivate_subscribers(
    request: Request,
    ids: list[int],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not ids:
        raise HTTPException(status_code=400, detail="No subscriber IDs provided")

    now = datetime.now(timezone.utc)
    stmt = (
        update(Subscriber)
        .where(Subscriber.id.in_(ids))
        .values(active=False, unsubscribed_at=now)
    )
    result = await db.execute(stmt)
    await db.commit()

    updated = result.rowcount
    logger.info(
        "subscribers_bulk_deactivated",
        count=updated,
        requested=len(ids),
        user_sub=current_user["sub"],
    )
    return {"updated": updated, "requested": len(ids)}


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

    # Detect columns
    destination_col = None
    name_col = None
    phone_col = None
    telegram_col = None
    tags_col = None
    for field_name in reader.fieldnames:
        name_lower = field_name.strip().lower()
        if name_lower in ("email", "e-mail", "mail", "destination"):
            destination_col = field_name
        elif name_lower in ("name", "nome"):
            name_col = field_name
        elif name_lower in ("phone", "telefone", "tel"):
            phone_col = field_name
        elif name_lower in ("telegram", "telegram_chat_id", "chat_id"):
            telegram_col = field_name
        elif name_lower in ("tags", "tag", "groups", "group"):
            tags_col = field_name

    if destination_col is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain a column named 'email', 'e-mail', 'mail', or 'destination'",
        )

    imported = 0
    skipped = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):
        raw_dest = (row.get(destination_col) or "").strip().lower()
        if not raw_dest:
            errors.append(f"Row {row_num}: empty email")
            continue

        if len(raw_dest) > 320:
            errors.append(f"Row {row_num}: value too long '{raw_dest[:60]}...'")
            continue

        sub_name = (row.get(name_col) or "").strip()[:255] if name_col else None
        sub_phone = (row.get(phone_col) or "").strip()[:60] if phone_col else None
        sub_telegram = (row.get(telegram_col) or "").strip()[:120] if telegram_col else None
        sub_tags = _clean_tags((row.get(tags_col) or "").strip()) if tags_col else None

        db.add(Subscriber(
            name=sub_name or None,
            email=raw_dest,
            phone=sub_phone,
            telegram_chat_id=sub_telegram,
            tags=sub_tags,
            active=True,
        ))
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

    logger.info("subscriber_unsubscribed", subscriber_id=subscriber_id)
    return {"message": "You have been unsubscribed successfully"}

