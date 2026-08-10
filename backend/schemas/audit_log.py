


"""Pydantic schemas for AuditLog."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditLogItem(BaseModel):
    id: int
    user_id: int | None
    action: str
    resource_type: str | None
    resource_id: str | None
    details: dict | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem]
    total: int
    page: int
    page_size: int

