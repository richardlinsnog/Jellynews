

"""Email delivery channel — SMTP with multipart/alternative support."""

from __future__ import annotations

import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiosmtplib
from services.channels.notification_channel import (
    ConnectionResult,
    ConnectionStatus,
    NotificationChannel,
    RenderedContent,
    SendResult,
)


class EmailChannel(NotificationChannel):
    name = "email"
    config_keys = [
        "smtp_host",
        "smtp_port",
        "smtp_user",
        "smtp_password",
        "smtp_use_tls",
        "from_address",
        "to_address",
    ]

    async def validate_config(self, config: dict[str, Any]) -> bool:
        required = ["smtp_host", "smtp_port", "from_address", "to_address"]
        for key in required:
            if key not in config or not config[key]:
                return False
        return True

    async def send(self, config: dict[str, Any], content: RenderedContent) -> SendResult:
        start = time.monotonic()
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = config["from_address"]
            msg["To"] = config["to_address"]
            msg["Subject"] = content.subject or "Newsletter"

            if content.body_text:
                msg.attach(MIMEText(content.body_text, "plain", "utf-8"))
            if content.body_html:
                msg.attach(MIMEText(content.body_html, "html", "utf-8"))

            use_tls = str(config.get("smtp_use_tls", "true")).lower() == "true"

            await aiosmtplib.send(
                msg,
                hostname=config["smtp_host"],
                port=int(config["smtp_port"]),
                username=config.get("smtp_user"),
                password=config.get("smtp_password"),
                use_tls=use_tls,
            )
            elapsed = (time.monotonic() - start) * 1000
            return SendResult(success=True, latency_ms=round(elapsed, 2))
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return SendResult(success=False, error=str(exc), latency_ms=round(elapsed, 2))

    async def test_connection(self, config: dict[str, Any]) -> ConnectionResult:
        start = time.monotonic()
        try:
            use_tls = str(config.get("smtp_use_tls", "true")).lower() == "true"
            async with aiosmtplib.SMTP(
                hostname=config["smtp_host"],
                port=int(config["smtp_port"]),
                use_tls=use_tls,
            ) as smtp:
                if config.get("smtp_user") and config.get("smtp_password"):
                    await smtp.login(config["smtp_user"], config["smtp_password"])
                await smtp.noop()
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionResult(
                status=ConnectionStatus.OK,
                message="SMTP connection successful",
                latency_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionResult(
                status=ConnectionStatus.ERROR,
                message=str(exc),
                latency_ms=round(elapsed, 2),
            )


