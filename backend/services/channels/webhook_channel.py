


"""Webhook delivery channel — signed JSON POST to arbitrary endpoints."""

from __future__ import annotations

import hashlib
import hmac
import json as json_module
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


class WebhookChannel(NotificationChannel):
    name = "webhook"
    config_keys = ["webhook_url", "hmac_secret"]

    async def validate_config(self, config: dict[str, Any]) -> bool:
        return bool(config.get("webhook_url"))

    async def send(self, config: dict[str, Any], content: RenderedContent) -> SendResult:
        start = time.monotonic()
        try:
            payload = {
                "subject": content.subject,
                "body_html": content.body_html,
                "body_text": content.body_text,
                "body_markdown": content.body_markdown,
            }
            body = json_module.dumps(payload, ensure_ascii=False)
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if config.get("hmac_secret"):
                sig = hmac.new(
                    config["hmac_secret"].encode(),
                    body.encode(),
                    hashlib.sha256,
                ).hexdigest()
                headers["X-JellyNews-Signature"] = f"sha256={sig}"

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    config["webhook_url"],
                    content=body,
                    headers=headers,
                )
                resp.raise_for_status()

            elapsed = (time.monotonic() - start) * 1000
            return SendResult(success=True, latency_ms=round(elapsed, 2))
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return SendResult(success=False, error=str(exc), latency_ms=round(elapsed, 2))

    async def test_connection(self, config: dict[str, Any]) -> ConnectionResult:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    config["webhook_url"],
                    json={"jellynews_test": True},
                    headers={"User-Agent": "JellyNews/1.0"},
                )
                resp.raise_for_status()
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionResult(
                status=ConnectionStatus.OK,
                message=f"Webhook responded {resp.status_code}",
                latency_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionResult(
                status=ConnectionStatus.ERROR,
                message=str(exc),
                latency_ms=round(elapsed, 2),
            )





