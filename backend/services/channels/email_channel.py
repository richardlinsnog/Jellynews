

"""Email delivery channel — SMTP with premailer CSS inlining, List-Unsubscribe,
and multipart/alternative support."""

from __future__ import annotations

import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiosmtplib
from premailer import transform
from services.channels.notification_channel import (
    ConnectionResult,
    ConnectionStatus,
    NotificationChannel,
    RenderedContent,
    SendResult,
)

_UNSUBSCRIBE_EMAIL_PLACEHOLDER = "unsubscribe@localhost"


def _unsubscribe_url(config: dict[str, Any]) -> str:
    return config.get(
        "unsubscribe_url",
        f"mailto:{_UNSUBSCRIBE_EMAIL_PLACEHOLDER}",
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
        "unsubscribe_url",
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

            # RFC 2369 / RFC 8058 List-Unsubscribe header
            unsubscribe_url = _unsubscribe_url(config)
            msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

            # Inject subscriber list via BCC for mass-mailing
            subscriber_emails = config.pop("_subscriber_emails", None)
            if subscriber_emails:
                msg["Bcc"] = ", ".join(subscriber_emails)

            if content.body_text:
                msg.attach(MIMEText(content.body_text, "plain", "utf-8"))
            if content.body_html:
                # Inline CSS for email client compatibility
                try:
                    inlined_html = transform(content.body_html)
                except Exception:
                    inlined_html = content.body_html
                msg.attach(MIMEText(inlined_html, "html", "utf-8"))

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
            recipient_count = len(subscriber_emails) if subscriber_emails else 1
            return SendResult(
                success=True,
                latency_ms=round(elapsed, 2),
                message_id=f"sent_to={recipient_count}",
            )
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


