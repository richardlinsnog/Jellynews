

"""Unit + integration tests for TemplateRegistry and the /api/v1/templates endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from services.template_registry import (
    TemplateNotFoundError,
    TemplateRegistry,
)

# ── Helpers ────────────────────────────────────────────────────────────

_SAMPLE_CONTEXT = {
    "server_name": "Test Server",
    "items_added": [
        {
            "Name": "Inception",
            "ProductionYear": 2010,
            "Type": "Movie",
            "LibraryName": "Movies",
            "Overview": "A mind-bending thriller.",
        }
    ],
    "custom_news": "Everything is fine.",
    "generated_at": "2026-08-08",
}


def _fresh_registry() -> TemplateRegistry:
    """Return a *new* registry singletons (reset internal state)."""
    TemplateRegistry._instance = None
    return TemplateRegistry.get()


# ── Registry unit tests ────────────────────────────────────────────────


class TestTemplateRegistryScan:
    """Boot-time scan and validation."""

    def test_scan_finds_three_builtin_packages(self):
        reg = _fresh_registry()
        ids = [t.template_id for t in reg.all]
        assert "minimal-light" in ids
        assert "cinema-dark" in ids
        assert "retro-vhs" in ids

    def test_all_builtins_are_verified(self):
        reg = _fresh_registry()
        for t in reg.all:
            assert t.is_builtin is True
            assert t.is_verified is True
            assert t.is_active is True

    def test_every_builtin_supports_email_and_telegram(self):
        reg = _fresh_registry()
        for t in reg.all:
            assert "email" in t.supports_channels
            assert "telegram" in t.supports_channels

    def test_every_builtin_has_html_and_txt_fallback(self):
        reg = _fresh_registry()
        for t in reg.all:
            assert t.channel_files.get("email") is not None
            assert t.channel_files.get("email-plaintext") is not None

    def test_lookup_returns_template(self):
        reg = _fresh_registry()
        t = reg.lookup("cinema-dark")
        assert t.name == "Cinema Dark"
        assert t.author == "JellyNews"

    def test_lookup_unknown_raises(self):
        reg = _fresh_registry()
        with pytest.raises(TemplateNotFoundError):
            reg.lookup("nonexistent")


class TestTemplateRegistryRender:
    """Rendering with safe variables."""

    def test_render_html_email(self):
        reg = _fresh_registry()
        output = reg.render("minimal-light", "email", _SAMPLE_CONTEXT)
        assert "Inception" in output
        assert "Test Server" in output
        assert "inception" in output.lower()
        assert "test server" in output.lower()

    def test_render_telegram_markdown(self):
        reg = _fresh_registry()
        output = reg.render("cinema-dark", "telegram", _SAMPLE_CONTEXT)
        assert "Inception" in output
        assert "Now Playing" in output

    def test_render_empty_items(self):
        reg = _fresh_registry()
        ctx = {
            "server_name": "Empty",
            "items_added": [],
            "generated_at": "2026-08-08",
        }
        output = reg.render("minimal-light", "email", ctx)
        assert "No new items" in output or "check back" in output.lower()

    def test_unknown_variable_is_stripped(self):
        """The sandbox silently drops keys not in the allowlist."""
        reg = _fresh_registry()
        ctx = {
            "server_name": "Safe",
            "items_added": [],
            "generated_at": "2026-08-08",
            "malicious_key": "{{ 7 * 7 }}",
        }
        # Should not raise — malicious_key is stripped
        output = reg.render("minimal-light", "email", ctx)
        assert "malicious_key" not in output
        assert "Safe" in output

    def test_nonexistent_channel_raises(self):
        reg = _fresh_registry()
        from services.template_registry import TemplateRenderError

        with pytest.raises(TemplateRenderError):
            reg.render("minimal-light", "carrier-pigeon", _SAMPLE_CONTEXT)


class TestTemplateRegistryReload:
    """Hot-reload behaviour."""

    def test_reload_returns_count(self):
        reg = _fresh_registry()
        count = reg.reload()
        assert count == 3

    def test_reload_picks_up_new_package(self, tmp_path: Path):
        """Write a temporary package, reload, and it appears."""
        # Override the templates root temporarily
        import services.template_registry as mod

        original_root = mod._TEMPLATES_ROOT
        try:
            mod._TEMPLATES_ROOT = tmp_path
            pkg = tmp_path / "extra"
            pkg.mkdir()
            (pkg / "manifest.json").write_text(json.dumps({
                "id": "extra",
                "name": "Extra",
                "author": "test",
                "version": "1.0",
                "supports_channels": ["email", "telegram"],
                "variables_required": ["server_name"],
                "is_builtin": False,
            }))
            (pkg / "email.html.j2").write_text("<p>{{ server_name }}</p>")
            (pkg / "telegram.md.j2").write_text("{{ server_name }}")

            reg = _fresh_registry()
            assert reg.reload() >= 1
            assert reg.lookup("extra").name == "Extra"
        finally:
            mod._TEMPLATES_ROOT = original_root


# ── Endpoint tests ─────────────────────────────────────────────────────


class TestTemplatesAPI:
    """Integration tests against /api/v1/templates/*"""

    @pytest.mark.asyncio
    async def test_list_templates_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/templates")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_templates_returns_gallery(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        resp = await client.get("/api/v1/templates", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 3
        assert "template_id" in data[0]
        assert "supports_channels" in data[0]

    @pytest.mark.asyncio
    async def test_get_single_template(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        resp = await client.get("/api/v1/templates/minimal-light", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["template_id"] == "minimal-light"
        assert data["name"] == "Minimal Light"
        assert "channel_files" in data
        assert "email.html.j2" in data["channel_files"].values()

    @pytest.mark.asyncio
    async def test_get_unknown_template_404(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        resp = await client.get("/api/v1/templates/nonexistent", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_render_preview(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        payload = {
            "channel": "email",
            "context": {
                "server_name": "API Test",
                "items_added": [
                    {
                        "Name": "The Matrix",
                        "ProductionYear": 1999,
                        "Type": "Movie",
                        "LibraryName": "Sci-Fi",
                    }
                ],
                "generated_at": "2026-08-08",
            },
        }
        resp = await client.post(
            "/api/v1/templates/cinema-dark/render",
            headers=headers,
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "The Matrix" in data["rendered"]
        assert data["channel"] == "email"

    @pytest.mark.asyncio
    async def test_render_unknown_template_400(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        resp = await client.post(
            "/api/v1/templates/nonexistent/render",
            headers=headers,
            json={"channel": "email", "context": {}},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_reload_endpoint(self, client: AsyncClient):
        headers = await _get_auth_headers(client)
        resp = await client.post("/api/v1/templates/reload", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 3
        assert data["message"] == "Templates reloaded"


# ── Helper ─────────────────────────────────────────────────────────────


async def _get_auth_headers(client: AsyncClient) -> dict[str, str]:
    """Run setup wizard and return Authorization headers."""
    # Use setup wizard to create an admin user
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


