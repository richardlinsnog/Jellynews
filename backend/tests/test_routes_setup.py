

"""Tests for setup wizard routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestSetupStatus:
    @pytest.mark.asyncio
    async def test_status_requires_setup_initially(self, client: AsyncClient):
        resp = await client.get("/api/v1/setup/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["setup_required"] is True
        assert data["first_run_enabled"] is True

    @pytest.mark.asyncio
    async def test_status_after_setup(self, client: AsyncClient):
        # Run setup
        await client.post(
            "/api/v1/setup",
            json={"username": "admin", "password": "securepass123"},
        )

        # Check status
        resp = await client.get("/api/v1/setup/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["setup_required"] is False


class TestSetupWizard:
    @pytest.mark.asyncio
    async def test_setup_creates_admin(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/setup",
            json={"username": "admin", "password": "securepass123"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Setup completed successfully. Welcome to JellyNews!"
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_setup_twice_fails(self, client: AsyncClient):
        # First setup
        resp = await client.post(
            "/api/v1/setup",
            json={"username": "admin", "password": "securepass123"},
        )
        assert resp.status_code == 200

        # Second setup should fail
        resp = await client.post(
            "/api/v1/setup",
            json={"username": "admin2", "password": "securepass456"},
        )

        assert resp.status_code in (400, 403)
        assert "already" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_setup_validates_username(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/setup",
            json={"username": "ab", "password": "securepass123"},
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_setup_validates_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/setup",
            json={"username": "admin", "password": "short"},
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_setup_rate_limit(self, client: AsyncClient):
        """Setup rate limit (3/min) should trigger on 4th attempt."""
        for _ in range(3):
            resp = await client.post(
                "/api/v1/setup",
                json={"username": f"admin_{_}", "password": "securepass123"},
            )
            # First attempt succeeds, rest fail with "already completed"
            assert resp.status_code in (200, 403)

        # 4th attempt should be rate limited
        resp = await client.post(
            "/api/v1/setup",
            json={"username": "admin_x", "password": "securepass123"},
        )

        assert resp.status_code == 429

