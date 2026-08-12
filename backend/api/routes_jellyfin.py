




from __future__ import annotations

import datetime

from api.deps import get_current_user
from api.rate_limit import limiter
from core.database import get_db
from core.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from schemas.jellyfin import JellyfinItem, JellyfinItemType
from services.jellyfin import JellyfinAuthError, JellyfinConnectionError, JellyfinService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/jellyfin", tags=["jellyfin"])


async def _get_jellyfin_service(db: AsyncSession) -> JellyfinService:
    """Build a JellyfinService from stored secrets."""
    from models.app_settings import AppSettings

    # In v1 we store jellyfin config in AppSettings (encrypted API key)
    # during the setup wizard. Later this moves to the Secrets table.
    base_url: str | None = None
    api_key: str | None = None

    # TODO: migrate to Secrets table in Week 4
    from services.vault import get_vault

    vault = get_vault()

    stmt = select(AppSettings).where(
        AppSettings.key.in_(["jellyfin_url", "jellyfin_api_key"]),
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    for row in rows:
        if row.key == "jellyfin_url":
            base_url = row.value
        elif row.key == "jellyfin_api_key":
            try:
                api_key = vault.decrypt(row.value)
            except Exception:
                api_key = row.value  # fallback for unencrypted legacy data

    return JellyfinService(base_url=base_url, api_key=api_key)


@router.get("/health")
async def jellyfin_health(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
) -> dict:
    """Check connectivity to the configured Jellyfin server."""
    svc = await _get_jellyfin_service(db)
    if not svc.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jellyfin is not configured. Run the setup wizard first.",
        )

    try:
        info = await svc.get_server_info()
        # Persist server name for templates and UI
        from models.app_settings import AppSettings
        from sqlalchemy import select as _sel

        existing = await db.execute(
            _sel(AppSettings).where(AppSettings.key == "server_name"),
        )
        row = existing.scalar_one_or_none()
        if row:
            row.value = info.name
        else:
            db.add(AppSettings(key="server_name", value=info.name))
        await db.commit()

        return {
            "connected": True,
            "server_name": info.name,
            "version": info.version,
        }
    except JellyfinConnectionError as exc:
        return {"connected": False, "error": str(exc)}
    except JellyfinAuthError as exc:
        return {"connected": False, "error": str(exc)}


@router.post("/test-connection")
@limiter.limit("3/minute")
async def test_jellyfin_connection(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
) -> dict:
    """Test the Jellyfin connection and return server info if successful."""
    svc = await _get_jellyfin_service(db)
    if not svc.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jellyfin is not configured.",
        )

    try:
        info = await svc.get_server_info()
        return {
            "success": True,
            "server_name": info.name,
            "version": info.version,
            "server_id": info.id,
        }
    except JellyfinConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Connection failed: {exc}",
        ) from exc
    except JellyfinAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {exc}",
        ) from exc


@router.get("/items/latest", response_model=list[JellyfinItem])
async def get_latest_items(
    limit: int = 20,
    item_types: str | None = None,
    since: str | None = Query(None, description="ISO date filter (e.g. 2024-01-15)"),
    until: str | None = Query(None, description="ISO date upper bound"),
    library_names: str | None = Query(None, description="Comma-separated library names to filter"),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
) -> list[JellyfinItem]:
    """Get the latest items from Jellyfin, optionally filtered by date range and libraries."""
    svc = await _get_jellyfin_service(db)
    if not svc.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jellyfin is not configured.",
        )

    try:
        # Resolve library names → item type filter
        item_type_filter: list[JellyfinItemType] | None = None
        if library_names:
            libs = await svc.get_libraries()
            names_list = library_names.split(",")
            item_type_filter = svc.library_types_to_item_types(libs, names_list)

        if since:
            since_dt = datetime.datetime.fromisoformat(since).replace(tzinfo=datetime.timezone.utc)
            until_dt = datetime.datetime.fromisoformat(until).replace(tzinfo=datetime.timezone.utc) if until else None
            items = await svc.get_items_since(since_dt, item_types=item_type_filter)
            items = [i for i in items if i.effective_date and i.effective_date >= since_dt]
            if until_dt:
                items = [i for i in items if i.effective_date <= until_dt]
            return items[:limit]

        if item_types and not item_type_filter:
            item_type_filter = [JellyfinItemType(t) for t in item_types.split(",")]

        return await svc.get_latest_items(limit=limit, item_types=item_type_filter)
    except JellyfinConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/image/{item_id:path}")
async def proxy_image(
    item_id: str,
    tag: str = "",
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Proxy a Jellyfin image through JellyNews so email clients can load it."""
    svc = await _get_jellyfin_service(db)
    if not svc.is_configured:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    try:
        content, content_type = await svc.fetch_image(item_id, tag)
    except HTTPException:
        raise
    except JellyfinConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except Exception as exc:
        logger.exception("proxy_image_failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return Response(content=content, media_type=content_type)


@router.get("/libraries")
async def get_libraries(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
) -> list[dict]:
    """Get all libraries (id + name) from Jellyfin."""
    svc = await _get_jellyfin_service(db)
    if not svc.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jellyfin is not configured.",
        )

    try:
        return await svc.get_libraries()
    except JellyfinConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/users/import")
async def import_jellyfin_users(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
) -> dict:
    """Import Jellyfin users as subscribers (deduplicated by name)."""
    from models.subscriber import Subscriber

    svc = await _get_jellyfin_service(db)
    if not svc.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jellyfin is not configured.",
        )

    try:
        users = await svc.fetch_users()
    except (JellyfinConnectionError, JellyfinAuthError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    imported = 0
    skipped = 0

    for user in users:
        stmt = select(Subscriber).where(Subscriber.name == user.name)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        db.add(
            Subscriber(
                name=user.name or None,
                active=True,
            ),
        )
        imported += 1

    await db.commit()

    return {
        "imported": imported,
        "skipped": skipped,
        "total": len(users),
    }


@router.post("/users/sync")
async def sync_jellyfin_users(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
) -> dict:
    """Sync Jellyfin users: create new ones, skip existing by name."""
    from models.subscriber import Subscriber

    svc = await _get_jellyfin_service(db)
    if not svc.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jellyfin is not configured.",
        )

    try:
        users = await svc.fetch_users()
    except (JellyfinConnectionError, JellyfinAuthError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    imported = 0
    skipped = 0

    for user in users:
        stmt = select(Subscriber).where(Subscriber.name == user.name)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            skipped += 1
        else:
            db.add(
                Subscriber(
                    name=user.name or None,
                    active=True,
                ),
            )
            imported += 1

    await db.commit()

    return {
        "imported": imported,
        "updated": 0,
        "skipped": skipped,
        "total": len(users),
    }



