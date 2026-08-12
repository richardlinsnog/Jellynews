"""NewsletterSender — orchestrates the full newsletter delivery pipeline.

1. Fetch new items from Jellyfin
2. Filter via idempotency (MediaLog)
3. Render templates per active channel
4. Dispatch via ChannelRegistry
5. Record DeliveryLog and update MediaLog
"""

from __future__ import annotations

import datetime
import json as _json
import time
from dataclasses import field

from core.logging import get_logger
from models.channel import Channel
from models.custom_news import CustomNews, NewsStatus
from models.delivery_log import DeliveryLog
from models.secret import Secret
from models.subscriber import Subscriber
from markupsafe import Markup
from pydantic.dataclasses import dataclass
from schemas.jellyfin import JellyfinItem, JellyfinItemType
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
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        library_names: list[str] | None = None,
        subscriber_tags: list[str] | None = None,
        force: bool = False,
        public_url: str = "",
    ) -> DeliveryReport:
        """Run the full newsletter pipeline and return a report."""
        start = time.monotonic()
        report = DeliveryReport()

        if not jellyfin.is_configured:
            report.errors.append("Jellyfin is not configured")
            report.duration_ms = (time.monotonic() - start) * 1000
            return report

        # -- 1. Fetch & filter --
        item_type_filter: list[JellyfinItemType] | None = None
        if library_names:
            libs = await jellyfin.get_libraries()
            item_type_filter = jellyfin.library_types_to_item_types(libs, library_names)

        try:
            if date_from:
                items = await jellyfin.get_items_since(date_from, item_types=item_type_filter)
                items = [i for i in items if i.effective_date and i.effective_date >= date_from]
                if date_to:
                    items = [i for i in items if i.effective_date <= date_to]
            else:
                items = await jellyfin.get_latest_items(limit=50, item_types=item_type_filter)
        except Exception as exc:
            report.errors.append(f"Jellyfin fetch failed: {exc}")
            report.duration_ms = (time.monotonic() - start) * 1000
            return report

        report.total_items = len(items)
        if not items:
            report.duration_ms = (time.monotonic() - start) * 1000
            return report

        if force:
            new_items = items
        else:
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

        # -- 3. Build context (with dynamic server name) --
        context = await self._build_context(db, jellyfin, new_items)

        # -- 4. Load subscriber destinations per type (optional tag filter) --
        sub_stmt = select(Subscriber).where(
            Subscriber.active.is_(True),
            Subscriber.email.isnot(None),
        )
        sub_result = await db.execute(sub_stmt)
        all_subscribers = list(sub_result.scalars().all())

        if subscriber_tags:
            tag_set = {t.strip().lower() for t in subscriber_tags}
            subscribers = [
                s for s in all_subscribers
                if s.tags and tag_set & {t.strip().lower() for t in s.tags.split(",")}
            ]
            logger.info(
                "tag_filter_applied",
                requested=subscriber_tags,
                total_subscribers=len(all_subscribers),
                matched=len(subscribers),
            )
        else:
            subscribers = all_subscribers

        subscriber_emails = [s.email for s in subscribers if s.email]
        subscriber_telegram_ids = [s.telegram_chat_id for s in subscribers if s.telegram_chat_id]

        # -- 5. Send to each channel --
        for channel in channels:
            log_entry = DeliveryLog(channel_id=channel.id, success=False)
            try:
                secret = await db.get(Secret, channel.config_ref)
                if not secret:
                    raise ValueError("Channel config not found")

                config = _json.loads(vault.decrypt(secret.encrypted_value))

                # Inject subscriber destinations for relevant channels
                if channel.channel_type == "email" and subscriber_emails:
                    config["_subscriber_emails"] = subscriber_emails
                if channel.channel_type == "telegram" and subscriber_telegram_ids:
                    config["_subscriber_telegram_ids"] = subscriber_telegram_ids

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
                    inline_images=self._inline_images if channel.channel_type == "email" else None,
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
            # Mark scheduled custom news as sent
            if getattr(self, "_scheduled_news_ids", None):
                for nid in self._scheduled_news_ids:
                    news = await db.get(CustomNews, nid)
                    if news and news.status == NewsStatus.SCHEDULED:
                        news.status = NewsStatus.SENT
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

    async def _build_context(self, db: AsyncSession, jellyfin: JellyfinService, items: list[JellyfinItem]) -> dict:
        import hashlib

        server_name = "Jellyfin"
        server_url = ""
        try:
            from models.app_settings import AppSettings

            stmt = select(AppSettings).where(AppSettings.key.in_(["server_name", "jellyfin_url"]))
            result = await db.execute(stmt)
            for row in result.scalars().all():
                if row.key == "server_name" and row.value:
                    server_name = row.value
                elif row.key == "jellyfin_url" and row.value:
                    server_url = row.value.rstrip("/")
        except Exception:
            pass

        # Collect inline images: content_id → (bytes, content_type)
        inline_images: dict[str, tuple[bytes, str]] = {}

        async def _fetch_and_cid(item: JellyfinItem) -> str:
            """Fetch item image via Jellyfin API and return a cid: reference."""
            if not item.id:
                return ""
            tag = item.image_tags.get("Primary", "") if item.image_tags else ""
            try:
                content, content_type = await jellyfin.fetch_image(item.id, tag)
            except Exception:
                return ""
            cid_hash = hashlib.sha256(f"{item.id}:{tag}".encode()).hexdigest()[:16]
            cid = f"item_{cid_hash}"
            subtype = content_type.split("/")[-1] if "/" in content_type else "jpeg"
            inline_images[cid] = (content, subtype)
            return f"cid:{cid}"

        def _image_cid(item: JellyfinItem) -> str:
            """Look up existing CID for cached fetch."""
            if not item.id:
                return ""
            tag = item.image_tags.get("Primary", "") if item.image_tags else ""
            cid_hash = hashlib.sha256(f"{item.id}:{tag}".encode()).hexdigest()[:16]
            cid = f"item_{cid_hash}"
            return f"cid:{cid}" if cid in inline_images else ""

        # Fetch images (async sequential — avoids overwhelming Jellyfin)
        for item in items:
            if item.id and item.image_tags:
                await _fetch_and_cid(item)

        # Fetch Jellyfin branding logo (fallback) / prefer custom uploaded logo
        server_logo_cid = ""
        try:
            from pathlib import Path as _Path

            custom_logo = _Path("/app/data/logo.png")
            if custom_logo.exists():
                logo_bytes = custom_logo.read_bytes()
                logo_subtype = "png"
            else:
                logo_bytes, logo_type = await jellyfin.fetch_branding_logo()
                logo_subtype = logo_type.split("/")[-1] if "/" in logo_type else "png"
            inline_images["server_logo"] = (logo_bytes, logo_subtype)
            server_logo_cid = "cid:server_logo"
        except Exception:
            pass

        # Build inline image list for RenderedContent
        inline_image_list = [
            {"content_id": cid, "content": data[0], "subtype": data[1], "filename": f"{cid}.{data[1]}"}
            for cid, data in inline_images.items()
        ]

        self._inline_images = inline_image_list

        # Group items by type for template
        items_by_type: dict[str, list[dict]] = {}
        for item in items:
            type_name = item.type.value
            items_by_type.setdefault(type_name, []).append(
                {
                    "Name": item.name,
                    "ProductionYear": item.production_year,
                    "Type": item.type.value,
                    "LibraryName": item.library_name or "",
                    "Overview": item.overview or "",
                    "ImageUrl": _image_cid(item),
                }
            )

        # Fetch scheduled custom news articles (mark as sent after delivery)
        custom_news_html = ""
        try:
            news_stmt = select(CustomNews).where(
                CustomNews.status == NewsStatus.SCHEDULED,
            ).order_by(CustomNews.created_at.asc())
            news_result = await db.execute(news_stmt)
            scheduled_news = list(news_result.scalars().all())
            if scheduled_news:
                parts = []
                for n in scheduled_news:
                    parts.append(f'<h3 style="margin:0 0 4px;font-size:15px;">{n.title}</h3>{n.body_html}')
                custom_news_html = "<hr style='margin:16px 0;border:none;border-top:1px solid #e0e0e0;'>" + "<hr style='margin:12px 0;border:none;border-top:1px solid #eee;'>".join(parts)
            self._scheduled_news_ids = [n.id for n in scheduled_news]
        except Exception:
            self._scheduled_news_ids = []

        return {
            "server_name": server_name,
            "server_url": server_url,
            "server_logo_cid": server_logo_cid,
            "items_added": [
                {
                    "Name": item.name,
                    "ProductionYear": item.production_year,
                    "Type": item.type.value,
                    "LibraryName": item.library_name or "",
                    "Overview": item.overview or "",
                    "ImageUrl": _image_cid(item),
                }
                for item in items
            ],
            "items_by_type": items_by_type,
            "total_types": len(items_by_type),
            "custom_news": Markup(custom_news_html),
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
