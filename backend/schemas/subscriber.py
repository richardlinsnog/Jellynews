

"""Subscriber schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SubscriberCreate(BaseModel):
    name: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=320)
    phone: str | None = Field(None, max_length=60)
    telegram_chat_id: str | None = Field(None, max_length=120)
    tags: str | None = Field(None, max_length=500, description="Comma-separated tags")


class SubscriberUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=320)
    phone: str | None = Field(None, max_length=60)
    telegram_chat_id: str | None = Field(None, max_length=120)
    tags: str | None = Field(None, max_length=500, description="Comma-separated tags")
    active: bool | None = None


class SubscriberItem(BaseModel):
    id: int
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    telegram_chat_id: str | None = None
    tags: str | None = None
    active: bool
    unsubscribed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class SubscriberListResponse(BaseModel):
    items: list[SubscriberItem]
    total: int
    page: int
    page_size: int


class SubscriberImportResult(BaseModel):
    imported: int
    skipped: int = 0
    errors: list[str] = []

