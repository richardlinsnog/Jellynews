
"""Pydantic schemas for the Template API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TemplateListItem(BaseModel):
    """Summary returned in the gallery listing."""

    template_id: str
    name: str
    author: str
    version: str
    supports_channels: list[str]
    preview_image: str | None = None
    variables_required: list[str] = []
    is_builtin: bool = False
    is_verified: bool = False
    is_active: bool = True


class TemplateDetail(TemplateListItem):
    """Full detail including rendered preview."""

    channel_files: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping channel → file stem (e.g. email → email.html.j2)",
    )


def _default_context() -> dict[str, Any]:
    return {
        "server_name": "Preview Server",
        "items_added": [
            {
                "Name": "Sample Movie",
                "ProductionYear": 2025,
                "Type": "Movie",
                "LibraryName": "Preview Library",
                "Overview": "This is a sample item for preview purposes.",
            }
        ],
        "custom_news": "",
        "generated_at": "2026-01-01T00:00:00",
    }


class TemplateRenderRequest(BaseModel):
    """Request body for the preview render endpoint."""

    channel: str = "email"
    context: dict[str, Any] = Field(
        default_factory=_default_context,
        description="Render context. Unknown keys are silently stripped by the sandbox.",
    )


class TemplateRenderResponse(BaseModel):
    """Result from the preview render endpoint."""

    template_id: str
    channel: str
    rendered: str


class TemplateImportResponse(BaseModel):
    template_id: str
    name: str
    version: str
    templates_count: int


class TemplateReloadResponse(BaseModel):
    message: str
    count: int

