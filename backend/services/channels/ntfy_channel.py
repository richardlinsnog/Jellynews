
"""ntfy delivery channel — self-hosted or ntfy.sh push notifications."""

from __future__ import annotations

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

_NTFY_MAX_LENGTH = 4096


class NtfyChannel(NotificationChannel):
    name = "ntfy"
    config_keys = ["ntfy_url", "ntfy_topic", "ntfy_token"]

    async def validate_config(self, config: dict[str, Any]) -> bool:
        return bool(config.get("ntfy_url") and config.get("ntfy_topic"))

    async def send(self, config: dict[str, Any], content: RenderedContent) -> SendResult:
        start = time.monotonic()
        base_url = config["ntfy_url"].rstrip("/")
        topic = config["ntfy_topic"]
        token = config.get("ntfy_token", "")

        headers = {
            "Content-Type": "text/markdown",
            "Title": content.subject or "JellyNews Update",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        body = content.body or content.html or ""
        if len(body) > _NTFY_MAX_LENGTH:
            body = body[:_NTFY_MAX_LENGTH - 100] + "\n\n… (truncated)"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{base_url}/{topic}",
                    content=body.encode("utf-8"),
                    headers=headers,
                )
                elapsed = (time.monotonic() - start) * 1000
                if resp.status_code < 300:
                    return SendResult(
                        success=True,
                        message_id=resp.headers.get("X-Message-ID"),
                        latency_ms=elapsed,
                    )
                return SendResult(
                    success=False,
                    error=f"ntfy returned {resp.status_code}: {resp.text[:200]}",
                    latency_ms=elapsed,
                )
        except httpx.RequestError as exc:
            elapsed = (time.monotonic() - start) * 1000
            return SendResult(success=False, error=str(exc), latency_ms=elapsed)

    async def test_connection(self, config: dict[str, Any]) -> ConnectionResult:
        start = time.monotonic()
        base_url = config["ntfy_url"].rstrip("/")
        topic = config["ntfy_topic"]
        token = config.get("ntfy_token", "")

        headers = {"Content-Type": "text/plain"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{base_url}/{topic}",
                    content="🔔 JellyNews connection test",
                    headers=headers,
                )
                elapsed = (time.monotonic() - start) * 1000
                if resp.status_code < 300:
                    return ConnectionResult(
                        status=ConnectionStatus.OK,
                        message=f"ntfy connected — topic '{topic}'",
                        latency_ms=elapsed,
                    )
                return ConnectionResult(
                    status=ConnectionStatus.ERROR,
                    message=f"ntfy returned {resp.status_code}: {resp.text[:200]}",
                    latency_ms=elapsed,
                )
        except httpx.RequestError as exc:
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionResult(
                status=ConnectionStatus.ERROR,
                message=str(exc),
                latency_ms=elapsed,
            )

