

"""Template gallery — browse, preview, and reload templates."""

from api.deps import get_current_user
from api.rate_limit import limiter
from core.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, Request, status
from schemas.template import (
    TemplateDetail,
    TemplateListItem,
    TemplateReloadResponse,
    TemplateRenderRequest,
    TemplateRenderResponse,
)
from services.template_registry import TemplateRegistry

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


def _registry() -> TemplateRegistry:
    return TemplateRegistry.get()


# ── Gallery ────────────────────────────────────────────────────────────


@router.get("", response_model=list[TemplateListItem])
@limiter.limit("60/minute")
async def list_templates(
    request: Request,
    _user: dict = Depends(get_current_user),
) -> list[TemplateListItem]:
    """Return every template registered on disk."""
    reg = _registry()
    return [
        TemplateListItem(
            template_id=t.template_id,
            name=t.name,
            author=t.author,
            version=t.version,
            supports_channels=t.supports_channels,
            preview_image=t.preview_image,
            variables_required=t.variables_required,
            is_builtin=t.is_builtin,
            is_verified=t.is_verified,
            is_active=t.is_active,
        )
        for t in reg.all
    ]


# ── Detail ─────────────────────────────────────────────────────────────


@router.get("/{template_id}", response_model=TemplateDetail)
@limiter.limit("60/minute")
async def get_template(
    request: Request,
    template_id: str,
    _user: dict = Depends(get_current_user),
) -> TemplateDetail:
    """Return full detail for a single template."""
    reg = _registry()
    try:
        t = reg.lookup(template_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    return TemplateDetail(
        template_id=t.template_id,
        name=t.name,
        author=t.author,
        version=t.version,
        supports_channels=t.supports_channels,
        preview_image=t.preview_image,
        variables_required=t.variables_required,
        is_builtin=t.is_builtin,
        is_verified=t.is_verified,
        is_active=t.is_active,
        channel_files={
            ch: path.name for ch, path in t.channel_files.items()
        },
    )


# ── Preview render ─────────────────────────────────────────────────────


@router.post("/{template_id}/render", response_model=TemplateRenderResponse)
@limiter.limit("30/minute")
async def render_template(
    request: Request,
    template_id: str,
    payload: TemplateRenderRequest,
    _user: dict = Depends(get_current_user),
) -> TemplateRenderResponse:
    """Render a preview with the supplied context."""
    reg = _registry()
    try:
        rendered = reg.render(template_id, payload.channel, payload.context)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return TemplateRenderResponse(
        template_id=template_id,
        channel=payload.channel,
        rendered=rendered,
    )


# ── Reload ─────────────────────────────────────────────────────────────


@router.post("/reload", response_model=TemplateReloadResponse)
@limiter.limit("10/minute")
async def reload_templates(
    request: Request,
    _user: dict = Depends(get_current_user),
) -> TemplateReloadResponse:
    """Force re-scan of the templates directory."""
    reg = _registry()
    count = reg.reload()
    return TemplateReloadResponse(message="Templates reloaded", count=count)


