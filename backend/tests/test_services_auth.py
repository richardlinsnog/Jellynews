


"""Tests for AuthService: password hashing, token creation, and verification."""

from __future__ import annotations

import os

import pytest
from models.user import UserRole
from services.auth import AuthService
from sqlalchemy.ext.asyncio import AsyncSession


class TestPasswordHashing:
    def test_hash_and_verify(self):
        auth = AuthService()
        password = "my-strong-password-123"
        hashed = auth.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$argon2id$")
        assert auth.verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        auth = AuthService()
        hashed = auth.hash_password("correct-password")

        assert auth.verify_password("wrong-password", hashed) is False

    def test_hash_is_deterministic_per_call(self):
        """Each hash call produces a different salt, so output differs."""
        auth = AuthService()

        hash1 = auth.hash_password("same-password")
        hash2 = auth.hash_password("same-password")

        assert hash1 != hash2  # Different salts
        assert auth.verify_password("same-password", hash1)
        assert auth.verify_password("same-password", hash2)


class TestTokenCreation:
    @pytest.fixture(autouse=True)
    def _set_secret(self):
        os.environ["APP_SECRET_KEY"] = "test-secret-for-tokens"

    def test_create_access_token(self):
        auth = AuthService()
        token = auth.create_access_token(1, "testuser", "owner", expires_minutes=30)

        assert token is not None
        assert token.count(".") == 2
        assert isinstance(token, str)

    def test_access_token_payload(self):
        auth = AuthService()
        token = auth.create_access_token(42, "alice", "editor", expires_minutes=15)

        payload = auth.decode_token(token)
        assert payload["sub"] == "42"
        assert payload["username"] == "alice"
        assert payload["role"] == "editor"
        assert payload["type"] == "access"

    def test_refresh_token_payload(self):
        auth = AuthService()
        token = auth.create_refresh_token(7)

        payload = auth.decode_token(token)
        assert payload["sub"] == "7"
        assert payload["type"] == "refresh"

    def test_decode_invalid_token(self):
        auth = AuthService()

        with pytest.raises(Exception):
            auth.decode_token("not.a.valid.jwt")


class TestUserOperations:
    @pytest.mark.asyncio
    async def test_create_user(self, db: AsyncSession):
        auth = AuthService()
        user = await auth.create_user(db, "editor1", "pass123", role=UserRole.EDITOR)

        assert user.id is not None
        assert user.username == "editor1"
        assert user.role == UserRole.EDITOR
        assert user.password_hash.startswith("$argon2id$")

    @pytest.mark.asyncio
    async def test_user_exists(self, db: AsyncSession):
        auth = AuthService()

        # No users initially
        assert await auth.user_exists(db) is False

        # Create a user
        await auth.create_user(db, "owner", "pass123", role=UserRole.OWNER)

        # Now it exists
        assert await auth.user_exists(db) is True

    @pytest.mark.asyncio
    async def test_authenticate(self, db: AsyncSession):
        auth = AuthService()
        await auth.create_user(db, "admin", "the-real-password")

        # Correct password
        user = await auth.authenticate(db, "admin", "the-real-password")
        assert user is not None
        assert user.username == "admin"

        # Wrong password
        user = await auth.authenticate(db, "admin", "wrong")
        assert user is None

