
"""Interface and shared types for notification channel plugins."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class ConnectionStatus(enum.Enum):
    OK = "ok"
    ERROR = "error"


@dataclass
class ConnectionResult:
    status: ConnectionStatus
    message: str = ""
    latency_ms: float | None = None


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
    latency_ms: float | None = None


@dataclass
class RenderedContent:
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    body_markdown: str | None = None


class NotificationChannel(ABC):
    name: str = "base"
    config_keys: list[str] = []

    @abstractmethod
    async def validate_config(self, config: dict[str, Any]) -> bool: ...

    @abstractmethod
    async def send(self, config: dict[str, Any], content: RenderedContent) -> SendResult: ...

    @abstractmethod
    async def test_connection(self, config: dict[str, Any]) -> ConnectionResult: ...

