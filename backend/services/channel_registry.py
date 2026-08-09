

"""ChannelRegistry — pluggable delivery channel catalogue with retry.

Mirrors the TemplateRegistry pattern:
- Singleton loaded at import time
- Each channel type is a class implementing NotificationChannel
- Adding a new channel = drop a file in services/channels/ + register
- All send() calls benefit from exponential backoff (3 retries, jitter)
"""

from __future__ import annotations

import asyncio
import random

from core.logging import get_logger
from services.channels.discord_channel import DiscordChannel
from services.channels.email_channel import EmailChannel
from services.channels.notification_channel import (
    ConnectionResult,
    NotificationChannel,
    RenderedContent,
    SendResult,
)
from services.channels.ntfy_channel import NtfyChannel
from services.channels.telegram_channel import TelegramChannel
from services.channels.webhook_channel import WebhookChannel

logger = get_logger(__name__)

_BUILTIN_CHANNELS: dict[str, type[NotificationChannel]] = {
    "email": EmailChannel,
    "telegram": TelegramChannel,
    "discord": DiscordChannel,
    "ntfy": NtfyChannel,
    "webhook": WebhookChannel,
}

# Exponential backoff settings
_MAX_RETRIES = 3
_BASE_DELAY_SECONDS = 1.0
_MAX_JITTER_SECONDS = 0.5

# HTTP status codes that should NOT be retried (client errors, not transient)
_NON_RETRYABLE_SUBSTRINGS = ("401", "403", "404", "409", "422", "invalid api token")


def _is_retryable_error(error: str) -> bool:
    """Return False for errors that will never succeed on retry (auth, 404, etc)."""
    if not error:
        return True
    error_lower = error.lower()
    for non_retryable in _NON_RETRYABLE_SUBSTRINGS:
        if non_retryable in error_lower:
            return False
    return True


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
        """Resolve plugin and dispatch send with exponential backoff.

        Retries up to 3 times on transient failures (connection errors,
        timeouts). Non-retryable errors (auth, 404, etc.) fail immediately.
        """
        plugin_cls = self.get_channel(channel_type)
        plugin = plugin_cls()

        last_result: SendResult | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            result = await plugin.send(config, content)
            if result.success:
                if attempt > 1:
                    logger.info(
                        "channel_retry_succeeded",
                        channel=channel_type,
                        attempt=attempt,
                    )
                return result

            last_result = result
            if not _is_retryable_error(result.error or ""):
                logger.warning(
                    "channel_non_retryable_error",
                    channel=channel_type,
                    error=result.error,
                )
                return result

            if attempt < _MAX_RETRIES:
                delay = _BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                jitter = random.uniform(0, _MAX_JITTER_SECONDS)
                total_delay = delay + jitter
                logger.warning(
                    "channel_retry",
                    channel=channel_type,
                    attempt=attempt,
                    delay=round(total_delay, 2),
                    error=result.error,
                )
                await asyncio.sleep(total_delay)

        return last_result  # type: ignore[return-value]

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



