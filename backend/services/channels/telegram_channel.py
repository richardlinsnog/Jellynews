

"""Telegram delivery channel — Bot API with auto-chunking for long messages."""

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

TELEGRAM_MAX_LENGTH = 4096


class TelegramChannel(NotificationChannel):
    name = "telegram"
    config_keys = ["bot_token", "chat_id"]

    async def validate_config(self, config: dict[str, Any]) -> bool:
        return bool(config.get("bot_token") and config.get("chat_id"))

    async def send(self, config: dict[str, Any], content: RenderedContent) -> SendResult:
        start = time.monotonic()
        try:
            text = content.body_markdown or content.body_text or ""
            chunks = self._chunk(text, TELEGRAM_MAX_LENGTH)
            last_id: str | None = None

            async with httpx.AsyncClient() as client:
                for chunk in chunks:
                    resp = await client.post(
                        f"https://api.telegram.org/bot{config['bot_token']}/sendMessage",
                        json={
                            "chat_id": config["chat_id"],
                            "text": chunk,
                            "parse_mode": "MarkdownV2",
                            "disable_web_page_preview": True,
                        },
                    )
                    data = resp.json()
                    if not data.get("ok"):
                        raise RuntimeError(
                            data.get("description", f"Telegram API error {resp.status_code}")
                        )
                    last_id = str(data["result"]["message_id"])

            elapsed = (time.monotonic() - start) * 1000
            return SendResult(success=True, message_id=last_id, latency_ms=round(elapsed, 2))
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return SendResult(success=False, error=str(exc), latency_ms=round(elapsed, 2))

    async def test_connection(self, config: dict[str, Any]) -> ConnectionResult:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.telegram.org/bot{config['bot_token']}/getMe",
                )
                data = resp.json()
                if not data.get("ok"):
                    raise RuntimeError(data.get("description", "Unknown error"))
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionResult(
                status=ConnectionStatus.OK,
                message=f"Connected as @{data['result']['username']}",
                latency_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionResult(
                status=ConnectionStatus.ERROR,
                message=str(exc),
                latency_ms=round(elapsed, 2),
            )

    @staticmethod
    def _chunk(text: str, size: int) -> list[str]:
        if len(text) <= size:
            return [text]
        chunks: list[str] = []
        for i in range(0, len(text), size):
            chunks.append(text[i : i + size])
        return chunks


