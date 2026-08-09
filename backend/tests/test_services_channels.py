

"""Unit + integration tests for ChannelRegistry and /api/v1/channels endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from services.channel_registry import ChannelNotFoundError, ChannelRegistry

_CHANNEL_CONFIG = {
    "email": {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_user": "user@example.com",
        "smtp_password": "secret",
        "smtp_use_tls": "true",
        "from_address": "news@example.com",
        "to_address": "subscriber@example.com",
    },
    "telegram": {
        "bot_token": "123:abc",
        "chat_id": "-100",
    },
    "discord": {
        "webhook_url": "https://discord.com/api/webhooks/123/abc",
    },
    "webhook": {
        "webhook_url": "https://example.com/notify",
        "hmac_secret": "supersecret",
    },
}


def _fresh_registry() -> ChannelRegistry:
    ChannelRegistry._instance = None
    return ChannelRegistry.get()


# ── Registry unit tests ───────────────────────────────────────────────────


class TestChannelRegistry:
    def test_available_returns_four_builtin_types(self):
        reg = _fresh_registry()
        types = reg.available
        assert "email" in types
        assert "telegram" in types
        assert "discord" in types
        assert "webhook" in types

    def test_get_channel_returns_class(self):
        reg = _fresh_registry()
        cls = reg.get_channel("email")
        assert cls.name == "email"

    def test_get_channel_unknown_raises(self):
        reg = _fresh_registry()
        with pytest.raises(ChannelNotFoundError):
            reg.get_channel("nonexistent")

    def test_singleton_is_stable(self):
        a = ChannelRegistry.get()
        b = ChannelRegistry.get()
        assert a is b


class TestChannelPlugins:
    @pytest.mark.anyio
    async def test_email_validates_correct_config(self):
        from services.channels.email_channel import EmailChannel

        ch = EmailChannel()
        assert await ch.validate_config(_CHANNEL_CONFIG["email"]) is True

    @pytest.mark.anyio
    async def test_email_rejects_incomplete_config(self):
        from services.channels.email_channel import EmailChannel

        ch = EmailChannel()
        assert await ch.validate_config({"smtp_host": "x"}) is False

    @pytest.mark.anyio
    async def test_telegram_validates_config(self):
        from services.channels.telegram_channel import TelegramChannel

        ch = TelegramChannel()
        assert await ch.validate_config(_CHANNEL_CONFIG["telegram"]) is True
        assert await ch.validate_config({}) is False

    @pytest.mark.anyio
    async def test_discord_validates_config(self):
        from services.channels.discord_channel import DiscordChannel

        ch = DiscordChannel()
        assert await ch.validate_config(_CHANNEL_CONFIG["discord"]) is True
        assert await ch.validate_config({}) is False

    @pytest.mark.anyio
    async def test_webhook_validates_config(self):
        from services.channels.webhook_channel import WebhookChannel

        ch = WebhookChannel()
        assert await ch.validate_config({"webhook_url": "https://example.com"}) is True
        assert await ch.validate_config({}) is False


# ── API integration tests ──────────────────────────────────────────────────


class TestChannelTypesEndpoint:
    async def test_list_types_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/channels/types")
        assert resp.status_code == 401

    async def test_list_types_returns_four(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        resp = await client.get(
            "/api/v1/channels/types",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["available_types"]) == 4


class TestChannelCRUD:
    async def test_create_and_list_channel(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        create_resp = await client.post(
            "/api/v1/channels",
            json={
                "channel_type": "email",
                "label": "My SMTP",
                "config": _CHANNEL_CONFIG["email"],
            },
            headers=headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        created = create_resp.json()
        assert created["channel_type"] == "email"
        assert created["label"] == "My SMTP"
        assert created["active"] is True
        assert "available_config_keys" in created

        list_resp = await client.get(
            "/api/v1/channels",
            headers=headers,
        )
        assert list_resp.status_code == 200
        channels = list_resp.json()
        assert len(channels) == 1
        assert channels[0]["id"] == created["id"]

    async def test_get_channel_detail(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        created = await _create_channel(client, headers, "telegram")
        channel_id = created["id"]

        resp = await client.get(
            f"/api/v1/channels/{channel_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == channel_id
        assert detail["channel_type"] == "telegram"
        assert "bot_token" in detail["available_config_keys"]

    async def test_get_nonexistent_returns_404(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        resp = await client.get(
            "/api/v1/channels/9999",
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_update_channel(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        created = await _create_channel(client, headers, "email")
        channel_id = created["id"]

        resp = await client.patch(
            f"/api/v1/channels/{channel_id}",
            json={"label": "Updated Label", "active": False},
            headers=headers,
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["label"] == "Updated Label"
        assert updated["active"] is False

    async def test_delete_channel(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        created = await _create_channel(client, headers, "discord")
        channel_id = created["id"]

        resp = await client.delete(
            f"/api/v1/channels/{channel_id}",
            headers=headers,
        )
        assert resp.status_code == 204

        # Confirm gone
        resp = await client.get(
            f"/api/v1/channels/{channel_id}",
            headers=headers,
        )
        assert resp.status_code == 404


class TestChannelConnectionTest:
    async def test_test_endpoint_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/channels/1/test")
        assert resp.status_code == 401

    async def test_test_nonexistent_channel(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        resp = await client.post(
            "/api/v1/channels/9999/test",
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_test_connection_for_webhook(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        created = await _create_channel(client, headers, "webhook")
        resp = await client.post(
            f"/api/v1/channels/{created['id']}/test",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "error")
        assert "message" in data


# ── Helpers ────────────────────────────────────────────────────────────────


async def _get_auth_headers(client: AsyncClient) -> dict[str, str]:
    """Run setup wizard and return Authorization headers."""
    await client.post(
        "/api/v1/setup",
        json={"username": "admin", "password": "securepass123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "securepass123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_channel(
    client: AsyncClient, headers: dict[str, str], channel_type: str
) -> dict:
    config = _CHANNEL_CONFIG.get(channel_type, {"webhook_url": "https://example.com"})
    resp = await client.post(
        "/api/v1/channels",
        json={
            "channel_type": channel_type,
            "label": f"Test {channel_type}",
            "config": config,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()

