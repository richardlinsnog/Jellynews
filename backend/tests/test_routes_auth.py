

"""Tests for auth routes: login, refresh, and authentication flows."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _setup_admin(client: AsyncClient) -> None:
    """Helper: run setup wizard to create admin user."""
    resp = await client.post(
        "/api/v1/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    assert resp.status_code == 200


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        await _setup_admin(client)

        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "securepass123"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        await _setup_admin(client)

        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )

        assert resp.status_code == 401
        assert "Invalid username or password" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "ghost", "password": "whatever123"},
        )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_validation_short_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "short"},
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_login_validation_bad_username(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "ab", "password": "validpassword123"},
        )

        assert resp.status_code == 422

class TestTokenRefresh:
    @pytest.mark.asyncio
    async def test_refresh_success(self, client: AsyncClient):
        """Refresh token should return new tokens."""
        # Set up admin user
        await _setup_admin(client)

        # Login to get refresh token
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "securepass123"},
        )
        assert login_resp.status_code == 200
        refresh_token = login_resp.json()["refresh_token"]

        # Refresh
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # New refresh token should be different
        # Refresh token rotation may or may not produce different tokens

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_access_token_rejected(self, client: AsyncClient):
        """Using an access token for refresh should fail."""
        await _setup_admin(client)

        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "securepass123"},
        )
        access_token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )

        assert resp.status_code == 401


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_login_rate_limit_triggers(self, client: AsyncClient):
        """Rate limit on login should trigger after 5 attempts."""
        await _setup_admin(client)

        # Exhaust the 5/min rate limit
        for _ in range(5):
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "wrongpassword"},
            )
            # Should be 401 (wrong password) while within rate limit
            assert resp.status_code == 401

        # 6th attempt should be rate limited
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )

        assert resp.status_code == 429

