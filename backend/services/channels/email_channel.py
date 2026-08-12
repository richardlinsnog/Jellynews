

"""Email delivery channel — SMTP with premailer CSS inlining, List-Unsubscribe,
multipart/alternative support, and inline CID image embedding."""

from __future__ import annotations

import time
import uuid
from email.mime.image import MIMEImage
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
        required = ["smtp_host", "smtp_port", "from_address"]
        for key in required:
            if key not in config or not config[key]:
                return False
        return True

    async def send(self, config: dict[str, Any], content: RenderedContent) -> SendResult:
        start = time.monotonic()
        try:
            has_images = bool(content.inline_images)

            if has_images:
                msg = MIMEMultipart("related")
                alt_part = MIMEMultipart("alternative")
                msg.attach(alt_part)
            else:
                msg = MIMEMultipart("alternative")
                alt_part = msg

            msg["From"] = config["from_address"]

            # Use to_address only when there are no subscriber emails to deliver to.
            # When subscribers are present (e.g. tag-filtered), use from_address as
            # the envelope To so that to_address does not receive an unintended copy.
            to_addr = config.get("to_address", "").strip()
            subscriber_emails = config.pop("_subscriber_emails", None)
            if subscriber_emails:
                msg["Bcc"] = ", ".join(subscriber_emails)
                to_addr = config["from_address"]
            msg["To"] = to_addr or config["from_address"]
            msg["Subject"] = content.subject or "Newsletter"
            msg["Message-ID"] = f"<{uuid.uuid4().hex[:16]}.jellynews@localhost>"

            # RFC 2369 / RFC 8058 List-Unsubscribe header
            unsubscribe_url = _unsubscribe_url(config)
            msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

            if content.body_text:
                alt_part.attach(MIMEText(content.body_text, "plain", "utf-8"))
            if content.body_html:
                try:
                    # Protect cid: URLs from premailer (it breaks them as relative URLs)
                    safe_html = content.body_html.replace("cid:", "X-CID-TOKEN:")
                    inlined_html = transform(safe_html)
                    inlined_html = inlined_html.replace("X-CID-TOKEN:", "cid:")
                except Exception:
                    inlined_html = content.body_html
                alt_part.attach(MIMEText(inlined_html, "html", "utf-8"))

            # Attach inline images for CID references
            if has_images:
                for img in content.inline_images or []:
                    mime_img = MIMEImage(img["content"], _subtype=img.get("subtype", "jpeg"))  # type: ignore[arg-type]
                    mime_img.add_header("Content-ID", f"<{img['content_id']}>")
                    mime_img.add_header("Content-Disposition", "inline", filename=img.get("filename", "image.jpg"))
                    mime_img.add_header("X-Attachment-Id", str(img["content_id"]))
                    msg.attach(mime_img)

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


