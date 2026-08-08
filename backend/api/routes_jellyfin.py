




from __future__ import annotations

from api.deps import get_current_user
from api.rate_limit import limiter
from core.database import get_db
from core.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models.user import User
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
    _current_user: User = Depends(get_current_user),
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
    _current_user: User = Depends(get_current_user),
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
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[JellyfinItem]:
    """Get the latest items from Jellyfin."""
    svc = await _get_jellyfin_service(db)
    if not svc.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jellyfin is not configured.",
        )

    types: list[JellyfinItemType] | None = None
    if item_types:
        types = [JellyfinItemType(t) for t in item_types.split(",")]

    try:
        return await svc.get_latest_items(limit=limit, item_types=types)
    except JellyfinConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/libraries")
async def get_libraries(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[str]:
    """Get all library names from Jellyfin."""
    svc = await _get_jellyfin_service(db)
    if not svc.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jellyfin is not configured.",
        )

    try:
        return await svc.fetch_library_names()
    except JellyfinConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


