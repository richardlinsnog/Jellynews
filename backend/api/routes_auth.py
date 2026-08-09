


from typing import Self

from api.deps import get_current_user
from api.rate_limit import limiter, login_rate_limit
from core.audit import audit_log
from core.database import get_db
from core.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from services.auth import get_auth_service
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=150, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def reject_surrogate_chars(self) -> Self:
        if any(0xD800 <= ord(c) <= 0xDFFF for c in self.password):
            raise ValueError("password contains invalid surrogate characters")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def reject_surrogate_chars(self) -> Self:
        if any(0xD800 <= ord(c) <= 0xDFFF for c in self.new_password):
            raise ValueError("new_password contains invalid surrogate characters")
        return self


@router.post("/login", response_model=TokenResponse)
@limiter.limit(login_rate_limit)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    auth = get_auth_service()
    user = await auth.authenticate(db, body.username, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    from core.config import settings

    access_token = auth.create_access_token(
        user.id, user.username, user.role.value, user.token_version,
    )
    refresh_token = auth.create_refresh_token(user.id, user.token_version)

    client_ip = request.client.host if request.client else "unknown"
    audit_log(
        db,
        user_id=user.id,
        action="auth.login",
        ip_address=client_ip,
        details={"client_ip": client_ip},
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    auth = get_auth_service()
    try:
        payload = auth.decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = int(payload["sub"])
    token_version = payload.get("ver", 0)

    from models.user import User
    from sqlalchemy import select

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # If token_version was bumped (password change), reject old refresh tokens
    if token_version != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked — please log in again",
        )

    from core.config import settings

    access_token = auth.create_access_token(
        user.id, user.username, user.role.value, user.token_version,
    )
    new_refresh_token = auth.create_refresh_token(user.id, user.token_version)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
        refresh_token=new_refresh_token,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change the current user's password and invalidate all existing tokens."""
    auth = get_auth_service()

    from models.user import User
    from sqlalchemy import select

    stmt = select(User).where(User.id == int(current_user["sub"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not auth.verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current password is incorrect",
        )

    user.password_hash = auth.hash_password(body.new_password)
    user.token_version = user.token_version + 1  # invalidate all existing tokens
    await db.commit()

    client_ip = request.client.host if request.client else "unknown"
    audit_log(
        db,
        user_id=user.id,
        action="auth.password_changed",
        ip_address=client_ip,
        details={"client_ip": client_ip},
    )

    logger.info("password_changed", user_id=user.id)



