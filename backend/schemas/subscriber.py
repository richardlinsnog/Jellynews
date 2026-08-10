

"""Subscriber schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SubscriberCreate(BaseModel):
    email: EmailStr = Field(..., description="Subscriber email address")


class SubscriberItem(BaseModel):
    id: int
    email: str
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

