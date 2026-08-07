


from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import get_logger
from models.user import User, UserRole

logger = get_logger(__name__)

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

JWT_ALGORITHM = "HS256"


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        return ph.hash(password)

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        try:
            ph.verify(password_hash, password)
            if ph.check_needs_rehash(password_hash):
                logger.info("password_needs_rehash")
            return True
        except (VerificationError, InvalidHashError):
            return False

    @staticmethod
    def _secret() -> str:
        return settings.APP_SECRET_KEY

    def create_access_token(
        self,
        user_id: int,
        username: str,
        role: str,
        expires_minutes: int | None = None,
    ) -> str:
        if expires_minutes is None:
            expires_minutes = settings.JWT_EXPIRATION_MINUTES
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "iat": now,
            "exp": now + timedelta(minutes=expires_minutes),
            "type": "access",
        }
        return jwt.encode(payload, self._secret(), algorithm=JWT_ALGORITHM)

    def create_refresh_token(self, user_id: int) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(days=settings.JWT_REFRESH_EXPIRATION_DAYS),
            "type": "refresh",
        }
        return jwt.encode(payload, self._secret(), algorithm=JWT_ALGORITHM)

    def decode_token(self, token: str) -> dict:
        return jwt.decode(token, self._secret(), algorithms=[JWT_ALGORITHM])

    async def authenticate(
        self, db: AsyncSession, username: str, password: str
    ) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None or not self.verify_password(password, user.password_hash):
            return None
        return user

    async def create_user(
        self,
        db: AsyncSession,
        username: str,
        password: str,
        role: UserRole = UserRole.EDITOR,
    ) -> User:
        user = User(
            username=username,
            password_hash=self.hash_password(password),
            role=role,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    async def user_exists(self, db: AsyncSession) -> bool:
        stmt = select(User).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None


def get_auth_service() -> AuthService:
    return AuthService()


