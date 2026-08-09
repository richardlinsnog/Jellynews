

"""Pydantic schemas for the Channel API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChannelListItem(BaseModel):
    """Summary returned in the channel listing."""

    id: int
    channel_type: str
    label: str
    active: bool
    template_id: str | None = None
    language: str = "en"
    created_at: datetime | None = None


class ChannelDetail(ChannelListItem):
    """Full detail including config keys available (values NEVER exposed)."""

    available_config_keys: list[str] = Field(
        default_factory=list,
        description="Config keys this channel type requires (values redacted)",
    )
    updated_at: datetime | None = None


class ChannelCreateRequest(BaseModel):
    """Payload to create a new channel instance."""

    channel_type: str
    label: str
    config: dict[str, Any] = Field(
        ...,
        description="Map of config key → plaintext value (stored encrypted)",
    )
    active: bool = True
    template_id: str | None = None
    language: str = "en"


class ChannelUpdateRequest(BaseModel):
    """Payload to update an existing channel instance."""

    label: str | None = None
    config: dict[str, Any] | None = None
    active: bool | None = None
    template_id: str | None = None
    language: str | None = None


class ChannelTestResponse(BaseModel):
    """Result of a channel connection test."""

    status: str
    message: str
    latency_ms: float | None = None


class ChannelListResponse(BaseModel):
    """Wrapper for the channel types endpoint."""

    available_types: list[str]


