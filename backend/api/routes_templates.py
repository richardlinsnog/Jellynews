

"""Template gallery — browse, preview, import, and reload templates."""

import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from api.deps import get_current_user
from api.rate_limit import limiter
from core.logging import get_logger
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from schemas.template import (
    TemplateDetail,
    TemplateImportResponse,
    TemplateListItem,
    TemplateReloadResponse,
    TemplateRenderRequest,
    TemplateRenderResponse,
)
from services.template_registry import TemplateRegistry

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])

_TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"

_MANIFEST_REQUIRED_FIELDS = {"id", "name", "author", "version"}
_MAX_ZIP_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _registry() -> TemplateRegistry:
    return TemplateRegistry.get()


def _validate_template_dir(dir_path: Path) -> dict:
    """Extract and validate manifest.json from a template directory. Raises on failure."""
    manifest_path = dir_path / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"manifest.json not found in uploaded template",
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="manifest.json is not valid JSON",
        )

    for field in _MANIFEST_REQUIRED_FIELDS:
        if field not in manifest or not manifest[field]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"manifest.json missing required field: {field}",
            )

    if not isinstance(manifest.get("supports_channels"), list) or not manifest["supports_channels"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="manifest.json must include a non-empty supports_channels list",
        )

    return manifest


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


# ── Import ─────────────────────────────────────────────────────────────


@router.post("/import", response_model=TemplateImportResponse)
@limiter.limit("10/minute")
async def import_template(
    request: Request,
    file: UploadFile = File(...),
    _user: dict = Depends(get_current_user),
) -> TemplateImportResponse:
    """Import a template package from a .zip file.

    The zip must contain a top-level directory with manifest.json
    and channel template files. Invalid archives are rejected with
    a 400 error and the templates directory is left untouched.
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .zip files are accepted",
        )

    contents = await file.read()
    if len(contents) > _MAX_ZIP_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Zip file exceeds {_MAX_ZIP_SIZE_BYTES // (1024*1024)} MB limit",
        )

    try:
        zip_file = zipfile.ZipFile(io.BytesIO(contents))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted zip file",
        )

    # Find the top-level directory inside the zip
    top_dirs: set[str] = set()
    for name in zip_file.namelist():
        # Reject dangerous paths
        if name.startswith("/") or ".." in Path(name).parts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid path in zip: {name}",
            )
        parts = Path(name).parts
        if parts:
            top_dirs.add(parts[0])

    if len(top_dirs) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zip must contain exactly one top-level directory",
        )

    template_name = top_dirs.pop()

    # Extract to a temp location and validate
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_file.extractall(tmpdir)
        extracted_dir = Path(tmpdir) / template_name

        if not extracted_dir.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Expected directory '{template_name}' not found in zip",
            )

        manifest = _validate_template_dir(extracted_dir)

        # Ensure templates root exists
        _TEMPLATES_ROOT.mkdir(parents=True, exist_ok=True)

        dest_dir = _TEMPLATES_ROOT / template_name
        if dest_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Template '{template_name}' already exists. Delete it first before re-importing.",
            )

        shutil.copytree(extracted_dir, dest_dir)

    # Reload registry so the new template is available immediately
    reg = _registry()
    count = reg.reload()

    logger.info("template_imported", template_id=manifest["id"], version=manifest["version"])

    return TemplateImportResponse(
        template_id=manifest["id"],
        name=manifest["name"],
        version=manifest["version"],
        templates_count=count,
    )


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


