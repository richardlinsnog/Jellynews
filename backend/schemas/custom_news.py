"""Pydantic schemas for CustomNews API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CustomNewsCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body_html: str = Field(min_length=1)
    status: str = "draft"


class CustomNewsUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body_html: str | None = Field(default=None, min_length=1)
    status: str | None = None


class CustomNewsItem(BaseModel):
    id: int
    title: str
    body_html: str
    body_text: str | None = None
    author_id: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CustomNewsListResponse(BaseModel):
    items: list[CustomNewsItem]
    total: int
