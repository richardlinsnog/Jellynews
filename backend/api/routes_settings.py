
"""Server settings — Jellyfin configuration (editable post-setup)."""

from __future__ import annotations

from api.deps import get_current_user
from api.rate_limit import limiter
from core.database import get_db
from core.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models.app_settings import AppSettings
from pydantic import BaseModel, Field
from services.vault import get_vault
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class JellyfinSettingsResponse(BaseModel):
    jellyfin_url: str = ""
    jellyfin_api_key_configured: bool = False


class JellyfinSettingsUpdate(BaseModel):
    jellyfin_url: str = Field(default="", max_length=512)
    jellyfin_api_key: str = Field(default="", max_length=256)


@router.get("/jellyfin", response_model=JellyfinSettingsResponse)
@limiter.limit("30/minute")
async def get_jellyfin_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> JellyfinSettingsResponse:
    """Return current Jellyfin server config (API key masked)."""
    stmt = select(AppSettings).where(
        AppSettings.key.in_(["jellyfin_url", "jellyfin_api_key"]),
    )
    result = await db.execute(stmt)
    rows = {r.key: r.value for r in result.scalars().all()}

    return JellyfinSettingsResponse(
        jellyfin_url=rows.get("jellyfin_url", ""),
        jellyfin_api_key_configured="jellyfin_api_key" in rows,
    )


@router.put("/jellyfin", response_model=JellyfinSettingsResponse)
@limiter.limit("10/minute")
async def update_jellyfin_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> JellyfinSettingsResponse:
    """Update Jellyfin server URL and/or API key."""
    # Parse body manually to avoid BaseHTTPMiddleware body consumption issues
    data = await request.json()
    body = JellyfinSettingsUpdate(**data)
    vault = get_vault()

    # Delete existing entries
    await db.execute(
        delete(AppSettings).where(
            AppSettings.key.in_(["jellyfin_url", "jellyfin_api_key"]),
        ),
    )

    if body.jellyfin_url:
        db.add(AppSettings(key="jellyfin_url", value=body.jellyfin_url))
    if body.jellyfin_api_key:
        encrypted_key = vault.encrypt(body.jellyfin_api_key)
        db.add(AppSettings(key="jellyfin_api_key", value=encrypted_key))

    await db.commit()

    logger.info("jellyfin_settings_updated")

    return JellyfinSettingsResponse(
        jellyfin_url=body.jellyfin_url,
        jellyfin_api_key_configured=bool(body.jellyfin_api_key),
    )
