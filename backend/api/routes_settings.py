
"""Server settings — Jellyfin configuration (editable post-setup) and branding logo."""

from pathlib import Path
from typing import Optional

from api.deps import get_current_user
from api.rate_limit import limiter
from core.database import get_db
from core.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from models.app_settings import AppSettings
from pydantic import BaseModel, Field
from services.vault import get_vault
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# Logo storage path (persisted via Docker volume)
LOGO_PATH = Path("/app/data/logo.png")
LOGO_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


class JellyfinSettingsResponse(BaseModel):
    jellyfin_url: str = ""
    jellyfin_api_key_configured: bool = False


class JellyfinSettingsUpdate(BaseModel):
    jellyfin_url: str = Field(default="", max_length=512)
    jellyfin_api_key: str = Field(default="", max_length=256)


class LogoStatusResponse(BaseModel):
    has_logo: bool = False


def _get_logo_bytes() -> Optional[bytes]:
    """Read logo from disk, returning None if absent."""
    try:
        return LOGO_PATH.read_bytes()
    except (FileNotFoundError, OSError):
        return None


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

    # Fetch existing entries to preserve values when field is empty
    existing_stmt = select(AppSettings).where(
        AppSettings.key.in_(["jellyfin_url", "jellyfin_api_key"]),
    )
    existing_result = await db.execute(existing_stmt)
    existing = {r.key: r.value for r in existing_result.scalars().all()}

    new_url = body.jellyfin_url or existing.get("jellyfin_url", "")
    new_api_key = body.jellyfin_api_key or existing.get("jellyfin_api_key", "")

    # Delete existing entries
    await db.execute(
        delete(AppSettings).where(
            AppSettings.key.in_(["jellyfin_url", "jellyfin_api_key"]),
        ),
    )

    if new_url:
        db.add(AppSettings(key="jellyfin_url", value=new_url))
    if new_api_key:
        db.add(AppSettings(key="jellyfin_api_key", value=new_api_key))

    await db.commit()

    logger.info("jellyfin_settings_updated")

    return JellyfinSettingsResponse(
        jellyfin_url=body.jellyfin_url,
        jellyfin_api_key_configured=bool(body.jellyfin_api_key),
    )


# ── Branding logo ──────────────────────────────────────────────────────


@router.get("/logo/status", response_model=LogoStatusResponse)
@limiter.limit("30/minute")
async def logo_status(
    request: Request,
    _user: dict = Depends(get_current_user),
) -> LogoStatusResponse:
    return LogoStatusResponse(has_logo=LOGO_PATH.exists())


@router.get("/logo")
@limiter.limit("30/minute")
async def get_logo(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Serve the uploaded branding logo (or 404 if none)."""
    if not LOGO_PATH.exists():
        raise HTTPException(status_code=404, detail="No logo uploaded")
    return FileResponse(str(LOGO_PATH), media_type="image/png")


@router.post("/logo", status_code=status.HTTP_201_CREATED, response_model=None)
@limiter.limit("10/minute")
async def upload_logo(
    request: Request,
    file: UploadFile,
    _user: dict = Depends(get_current_user),
):
    """Upload a new branding logo (PNG, max 2 MB)."""
    content = await file.read()
    if len(content) > LOGO_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Logo must be under 2 MB")
    if file.content_type and file.content_type not in ("image/png", "image/jpeg"):
        raise HTTPException(status_code=415, detail="Only PNG and JPEG images are supported (SVG does not render in email clients)")
    LOGO_PATH.write_bytes(content)
    logger.info("logo_uploaded", size=len(content))
    return {"has_logo": True, "size": len(content)}


@router.delete("/logo", status_code=status.HTTP_200_OK, response_model=None)
@limiter.limit("10/minute")
async def delete_logo(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Remove the branding logo."""
    try:
        LOGO_PATH.unlink(missing_ok=True)
        logger.info("logo_deleted")
        return {"has_logo": False}
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete logo: {exc}")
