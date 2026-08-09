

"""ChannelRegistry — pluggable delivery channel catalogue.

Mirrors the TemplateRegistry pattern:
- Singleton loaded at import time
- Each channel type is a class implementing NotificationChannel
- Adding a new channel = drop a file in services/channels/ + register
"""

from __future__ import annotations

from core.logging import get_logger
from services.channels.discord_channel import DiscordChannel
from services.channels.email_channel import EmailChannel
from services.channels.notification_channel import (
    ConnectionResult,
    NotificationChannel,
    RenderedContent,
    SendResult,
)
from services.channels.telegram_channel import TelegramChannel
from services.channels.webhook_channel import WebhookChannel

logger = get_logger(__name__)

_BUILTIN_CHANNELS: dict[str, type[NotificationChannel]] = {
    "email": EmailChannel,
    "telegram": TelegramChannel,
    "discord": DiscordChannel,
    "webhook": WebhookChannel,
}


class ChannelRegistry:
    """Thread-safe singleton catalogue of delivery channel types."""

    _instance: ChannelRegistry | None = None

    def __init__(self) -> None:
        self._channels: dict[str, type[NotificationChannel]] = dict(_BUILTIN_CHANNELS)

    @classmethod
    def get(cls) -> ChannelRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset(cls) -> None:
        """Test helper — wipe singleton so a fresh registry is built."""
        cls._instance = None

    @property
    def available(self) -> list[str]:
        """Return sorted list of registered channel type names."""
        return sorted(self._channels.keys())

    def get_channel(self, name: str) -> type[NotificationChannel]:
        """Look up a channel class by name (e.g. 'email')."""
        try:
            return self._channels[name]
        except KeyError:
            raise ChannelNotFoundError(f"Unknown channel type: {name}")

    async def send(
        self,
        channel_type: str,
        config: dict,
        content: RenderedContent,
    ) -> SendResult:
        """Resolve plugin and dispatch send."""
        plugin_cls = self.get_channel(channel_type)
        plugin = plugin_cls()
        return await plugin.send(config, content)

    async def test_connection(
        self,
        channel_type: str,
        config: dict,
    ) -> ConnectionResult:
        """Resolve plugin and test connectivity."""
        plugin_cls = self.get_channel(channel_type)
        plugin = plugin_cls()
        return await plugin.test_connection(config)


class ChannelNotFoundError(Exception):
    """Raised when a channel type is not registered."""



