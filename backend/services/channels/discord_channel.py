


"""Discord delivery channel — native Discord webhook with embed support."""

from __future__ import annotations

import time
from typing import Any

import httpx
from services.channels.notification_channel import (
    ConnectionResult,
    ConnectionStatus,
    NotificationChannel,
    RenderedContent,
    SendResult,
)

DISCORD_MAX_CONTENT = 2000
DISCORD_MAX_EMBED_DESC = 4096


class DiscordChannel(NotificationChannel):
    name = "discord"
    config_keys = ["webhook_url"]

    async def validate_config(self, config: dict[str, Any]) -> bool:
        return bool(config.get("webhook_url"))

    async def send(self, config: dict[str, Any], content: RenderedContent) -> SendResult:
        start = time.monotonic()
        try:
            text = content.body_markdown or content.body_text or ""
            payload: dict[str, Any] = {
                "username": "JellyNews",
            }

            if len(text) <= DISCORD_MAX_CONTENT:
                payload["content"] = text
            else:
                payload["content"] = text[:DISCORD_MAX_CONTENT]
                if content.body_html:
                    payload["embeds"] = [
                        {
                            "title": "Newsletter",
                            "description": text[:DISCORD_MAX_EMBED_DESC],
                            "color": 0x9B59B6,
                        }
                    ]

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    config["webhook_url"] + "?wait=true",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            elapsed = (time.monotonic() - start) * 1000
            return SendResult(
                success=True,
                message_id=str(data.get("id", "")),
                latency_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return SendResult(success=False, error=str(exc), latency_ms=round(elapsed, 2))

    async def test_connection(self, config: dict[str, Any]) -> ConnectionResult:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(config["webhook_url"])
                data = resp.json()
                name = data.get("name", "unknown")
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionResult(
                status=ConnectionStatus.OK,
                message=f"Webhook '{name}' is valid",
                latency_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionResult(
                status=ConnectionStatus.ERROR,
                message=str(exc),
                latency_ms=round(elapsed, 2),
            )



