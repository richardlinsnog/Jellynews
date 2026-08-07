
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.rate_limit import limiter
from core.config import settings
from core.database import get_db
from core.logging import get_logger
from models.user import UserRole
from services.auth import get_auth_service
from services.vault import get_vault

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/setup", tags=["setup"])


class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=150, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8, max_length=128)
    jellyfin_url: str = Field(default="", max_length=512)
    jellyfin_api_key: str = Field(default="", max_length=256)


class SetupResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str


@router.post("", response_model=SetupResponse)
@limiter.limit("3/minute")
async def setup_wizard(
    request: Request,
    body: SetupRequest,
    db: AsyncSession = Depends(get_db),
) -> SetupResponse:
    if not settings.FIRST_RUN_SETUP:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup wizard is disabled. Set FIRST_RUN_SETUP=true to enable.",
        )

    auth = get_auth_service()

    if await auth.user_exists(db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup already completed. An admin user already exists.",
        )

    # Prevent surrogate characters in password
    if any(0xD800 <= ord(c) <= 0xDFFF for c in body.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password contains invalid surrogate characters",
        )

    user = await auth.create_user(
        db=db,
        username=body.username,
        password=body.password,
        role=UserRole.OWNER,
    )
    await db.commit()

    # Store Jellyfin config if provided
    if body.jellyfin_url or body.jellyfin_api_key:
        from models.app_settings import AppSettings

        if body.jellyfin_url:
            db.add(AppSettings(key="jellyfin_url", value=body.jellyfin_url))
        if body.jellyfin_api_key:
            encrypted_key = get_vault().encrypt(body.jellyfin_api_key)
            db.add(AppSettings(key="jellyfin_api_key", value=encrypted_key))

        await db.commit()

    access_token = auth.create_access_token(user.id, user.username, user.role.value)
    refresh_token = auth.create_refresh_token(user.id)

    logger.info("setup_completed", username=user.username)

    return SetupResponse(
        message="Setup completed successfully. Welcome to JellyNews!",
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
        refresh_token=refresh_token,
    )


@router.get("/status")
async def setup_status(db: AsyncSession = Depends(get_db)) -> dict:
    auth = get_auth_service()
    return {
        "setup_required": not await auth.user_exists(db),
        "first_run_enabled": settings.FIRST_RUN_SETUP,
    }



