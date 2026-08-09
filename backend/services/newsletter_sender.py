"""NewsletterSender — orchestrates the full newsletter delivery pipeline.

1. Fetch new items from Jellyfin
2. Filter via idempotency (MediaLog)
3. Render templates per active channel
4. Dispatch via ChannelRegistry
5. Record DeliveryLog and update MediaLog
"""

from __future__ import annotations

import json as _json
import time
from dataclasses import field

from core.logging import get_logger
from models.channel import Channel
from models.delivery_log import DeliveryLog
from models.secret import Secret
from models.subscriber import Subscriber
from pydantic.dataclasses import dataclass
from schemas.jellyfin import JellyfinItem
from services.channel_registry import ChannelRegistry
from services.channels.notification_channel import RenderedContent
from services.idempotency import find_new_items, record_notified_items
from services.jellyfin import JellyfinService
from services.template_registry import TemplateRegistry
from services.vault import SecretsVaultService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass
class DeliveryReport:
    """Summary of a newsletter send run."""

    total_items: int = 0
    new_items: int = 0
    channels_attempted: int = 0
    channels_succeeded: int = 0
    channels_failed: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


_CHANNELS_WITH_RENDER = {"email", "telegram", "discord", "ntfy"}


class NewsletterSender:
    """Stateless orchestrator — receives all dependencies via method params."""

    def __init__(self) -> None:
        self._registry = ChannelRegistry.get()
        self._templates = TemplateRegistry.get()

    async def send(
        self,
        db: AsyncSession,
        jellyfin: JellyfinService,
        vault: SecretsVaultService,
    ) -> DeliveryReport:
        """Run the full newsletter pipeline and return a report."""
        start = time.monotonic()
        report = DeliveryReport()

        if not jellyfin.is_configured:
            report.errors.append("Jellyfin is not configured")
            report.duration_ms = (time.monotonic() - start) * 1000
            return report

        # -- 1. Fetch & filter --
        try:
            items = await jellyfin.get_latest_items(limit=50)
        except Exception as exc:
            report.errors.append(f"Jellyfin fetch failed: {exc}")
            report.duration_ms = (time.monotonic() - start) * 1000
            return report

        report.total_items = len(items)
        if not items:
            report.duration_ms = (time.monotonic() - start) * 1000
            return report

        new_items = await find_new_items(db, items)
        report.new_items = len(new_items)
        if not new_items:
            report.duration_ms = (time.monotonic() - start) * 1000
            return report

        # -- 2. Load active channels --
        stmt = select(Channel).where(Channel.active == True)  # noqa: E712
        result = await db.execute(stmt)
        channels = list(result.scalars().all())

        if not channels:
            report.errors.append("No active channels configured")
            report.duration_ms = (time.monotonic() - start) * 1000
            return report

        report.channels_attempted = len(channels)

        # -- 3. Build context --
        context = self._build_context(new_items)

        # -- 4. Load subscriber addresses for mass-mailing channels --
        sub_stmt = select(Subscriber.email).where(Subscriber.active.is_(True))
        sub_result = await db.execute(sub_stmt)
        subscriber_emails = [row[0] for row in sub_result.fetchall()]

        # -- 5. Send to each channel --
        for channel in channels:
            log_entry = DeliveryLog(channel_id=channel.id, success=False)
            try:
                secret = await db.get(Secret, channel.config_ref)
                if not secret:
                    raise ValueError("Channel config not found")

                config = _json.loads(vault.decrypt(secret.encrypted_value))

                # Inject subscriber list into email channel if no explicit to_address
                if channel.channel_type == "email" and subscriber_emails:
                    config["_subscriber_emails"] = subscriber_emails

                if channel.channel_type in _CHANNELS_WITH_RENDER:
                    try:
                        rendered = self._templates.render(
                            channel.template_id or "minimal-light",
                            channel.channel_type,
                            context,
                        )
                    except Exception:
                        rendered = self._build_plain_body(context)
                else:
                    rendered = _json.dumps(context, ensure_ascii=False, default=str)

                content = RenderedContent(
                    subject=f"JellyNews - {len(new_items)} new items",
                    body_html=rendered if channel.channel_type == "email" else "",
                    body_text=rendered,
                    body_markdown=rendered if channel.channel_type != "email" else "",
                )

                result = await self._registry.send(channel.channel_type, config, content)

                log_entry.success = result.success
                log_entry.status_message = (
                    f"message_id={result.message_id}" if result.success else result.error
                )
                log_entry.payload_summary = {
                    "channel_type": channel.channel_type,
                    "item_count": len(new_items),
                    "latency_ms": result.latency_ms,
                }

                if result.success:
                    report.channels_succeeded += 1
                else:
                    report.channels_failed += 1
                    report.errors.append(f"[{channel.label}] {result.error}")

            except Exception as exc:
                report.channels_failed += 1
                log_entry.success = False
                log_entry.status_message = str(exc)[:500]
                report.errors.append(f"[{channel.label}] {exc}")

            db.add(log_entry)

        await db.commit()

        # -- 5. Mark items as notified --
        if report.channels_succeeded > 0:
            await record_notified_items(db, new_items)
            await db.commit()

        report.duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "newsletter_sent",
            new_items=report.new_items,
            succeeded=report.channels_succeeded,
            failed=report.channels_failed,
            duration_ms=report.duration_ms,
        )
        return report

    def _build_context(self, items: list[JellyfinItem]) -> dict:
        return {
            "server_name": "Jellyfin",
            "items_added": [
                {
                    "Name": item.name,
                    "ProductionYear": item.production_year,
                    "Type": item.type.value,
                    "LibraryName": item.library_name,
                }
                for item in items
            ],
            "custom_news": "",
            "generated_at": "",
        }

    @staticmethod
    def _build_plain_body(context: dict) -> str:
        items = context.get("items_added", [])
        if not items:
            return "No new items this time."
        lines = ["New additions to your library:", ""]
        for item in items:
            extra = f" ({item.get('ProductionYear')})" if item.get("ProductionYear") else ""
            lines.append(f"  - {item['Name']}{extra} ({item.get('Type', '')})")
        return "\n".join(lines)
