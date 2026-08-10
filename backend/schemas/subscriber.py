

"""Subscriber schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SubscriberCreate(BaseModel):
    destination_type: str = Field(default="email", description="email | telegram")
    destination: str = Field(..., min_length=1, max_length=320, description="Email address, chat_id, etc.")


class SubscriberUpdate(BaseModel):
    destination: str | None = Field(None, min_length=1, max_length=320)
    active: bool | None = None


class SubscriberItem(BaseModel):
    id: int
    destination_type: str = "email"
    destination: str
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

