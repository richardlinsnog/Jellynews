





"""TemplateRegistry — Sandboxed Jinja2 template loader, validator and renderer.

Follows spec §3: disk-based templates with manifest.json, sandboxed environment,
allowlist context. The registry scans the templates/ directory at boot and
keeps an in-memory index for fast lookup.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.logging import get_logger
from jinja2.sandbox import SandboxedEnvironment

log = get_logger("template_registry")

# ═══════════════════════════════════════════════════════════════════
# Domain objects
# ═══════════════════════════════════════════════════════════════════

# Maps logical channel name → primary template file extension.
# The plain-text fallback for email (email.txt.j2) is resolved internally.
_CHANNEL_TO_EXTENSION: dict[str, str] = {
    "email": ".html.j2",
    "telegram": ".md.j2",
    "discord": ".md.j2",
    "ntfy": ".md.j2",
}

# Variables that are safe for *all* templates — the Master Allowlist (spec §3.3).
_SAFE_GLOBALS: set[str] = {
    "items_added",
    "custom_news",
    "server_name",
    "server_url",
    "generated_at",
}

_TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"

# ═══════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════


class TemplateError(Exception):
    """Base error for template operations."""


class TemplateNotFoundError(TemplateError):
    """Template id not found in registry."""


class TemplateRenderError(TemplateError):
    """Unexpected error during rendering."""


class TemplateValidationError(TemplateError):
    """Manifest is malformed or missing required fields."""


# ═══════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════


def _slugify(name: str) -> str:
    """Derive a safe template id from its display name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


# ═══════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════


@dataclass
class TemplateInfo:
    """In-memory representation of a loaded template package."""

    template_id: str
    name: str
    author: str
    version: str
    supports_channels: list[str]
    variables_required: list[str] = field(default_factory=list)
    preview_image: str | None = None
    is_builtin: bool = False
    is_verified: bool = True
    is_active: bool = True

    # Derived at scan time — mapping channel → absolute file path
    channel_files: dict[str, Path] = field(default_factory=dict)


class TemplateRegistry:
    """Singleton registry that scans, holds and renders template packages."""

    _instance: TemplateRegistry | None = None

    def __init__(self) -> None:
        self._templates: dict[str, TemplateInfo] = {}
        self._jinja_cache: dict[str, SandboxedEnvironment] = {}
        self._scanned = False

    # ── Singleton access ────────────────────────────────────────

    @classmethod
    def get(cls) -> TemplateRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Public API ──────────────────────────────────────────────

    @property
    def all(self) -> list[TemplateInfo]:
        self._ensure_scanned()
        return list(self._templates.values())

    def lookup(self, template_id: str) -> TemplateInfo:
        """Return a single template by id."""
        self._ensure_scanned()
        try:
            return self._templates[template_id]
        except KeyError:
            raise TemplateNotFoundError(f"Template '{template_id}' not found")

    def render(
        self,
        template_id: str,
        channel: str,
        context: dict[str, Any],
    ) -> str:
        """Render a template for a specific channel with the given context.

        Args:
            template_id: Which template package to use.
            channel: Destination channel (``email``, ``telegram``, …).
            context: Dict whose keys must be a subset of the allowlist.

        Returns:
            Rendered string.

        Raises:
            TemplateNotFoundError: Unknown template id.
            TemplateRenderError: Channel not supported or render failure.
        """
        self._ensure_scanned()
        info = self._templates.get(template_id)
        if info is None:
            raise TemplateNotFoundError(f"Template '{template_id}' not found")

        file_path = info.channel_files.get(channel)
        if file_path is None:
            raise TemplateRenderError(
                f"Channel '{channel}' not available in template '{template_id}'",
            )

        # Sanitize context — strip any keys not in the explicit allowlist,
        # then fill in safe defaults.
        sanitized: dict[str, Any] = {}
        for key, value in context.items():
            if key in _SAFE_GLOBALS:
                sanitized[key] = value

        # Always inject defaults for any missing safe variables.
        for safe_key in _SAFE_GLOBALS:
            sanitized.setdefault(safe_key, "")

        env = self._get_or_create_env(info)

        try:
            source = file_path.read_text(encoding="utf-8")
            tmpl = env.from_string(source)
            return tmpl.render(**sanitized)
        except Exception as exc:
            raise TemplateRenderError(
                f"Render failed for '{template_id}/{channel}': {exc}",
            ) from exc

    def reload(self) -> int:
        """Force re-scan of the templates directory (e.g. after import)."""
        self._templates.clear()
        self._jinja_cache.clear()
        self._scanned = False
        self._ensure_scanned()
        return len(self._templates)

    # ── Internal ────────────────────────────────────────────────

    def _ensure_scanned(self) -> None:
        if self._scanned:
            return

        self._scanned = True
        if not _TEMPLATES_ROOT.exists():
            log.info("templates directory not found, skipping scan", path=str(_TEMPLATES_ROOT))
            return

        for package_dir in sorted(_TEMPLATES_ROOT.iterdir()):
            if not package_dir.is_dir():
                continue
            try:
                info = self._load_package(package_dir)
                self._templates[info.template_id] = info
                log.info("template loaded", id=info.template_id, version=info.version)
            except TemplateError as exc:
                log.warning(
                    "skipping invalid template package",
                    path=str(package_dir),
                    error=str(exc),
                )

    def _load_package(self, package_dir: Path) -> TemplateInfo:
        manifest_path = package_dir / "manifest.json"
        if not manifest_path.exists():
            raise TemplateValidationError(f"manifest.json missing in {package_dir}")

        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TemplateValidationError(f"Invalid JSON in {manifest_path}: {exc}") from exc

        required_str = {"id", "name", "author", "version"}
        for key in required_str:
            if key not in raw or not isinstance(raw[key], str) or not raw[key].strip():
                raise TemplateValidationError(f"Missing or empty '{key}' in {manifest_path}")

        channels_raw = raw.get("supports_channels", [])
        if not isinstance(channels_raw, list) or not channels_raw:
            msg = f"supports_channels must be a non-empty list in {manifest_path}"
            raise TemplateValidationError(msg)

        variables = raw.get("variables_required", [])
        if not isinstance(variables, list):
            raise TemplateValidationError(f"variables_required must be a list in {manifest_path}")

        channel_files: dict[str, Path] = {}
        for ch in channels_raw:
            ext = _CHANNEL_TO_EXTENSION.get(ch)
            if ext is None:
                # Unrecognised channel — skip silently
                continue
            candidate = package_dir / f"{ch}{ext}"
            if candidate.exists():
                channel_files[ch] = candidate

        # Plain-text fallback for email (email.txt.j2)
        txt_candidate = package_dir / "email.txt.j2"
        if "email" in channel_files and txt_candidate.exists():
            channel_files["email-plaintext"] = txt_candidate

        if not channel_files:
            raise TemplateValidationError(
                f"No channel template files found for {manifest_path}",
            )

        # Unverified flag for community templates (spec §3.3)
        settings = get_settings()
        is_builtin = raw.get("is_builtin", False)
        is_verified = is_builtin or not settings.ALLOW_UNVERIFIED_TEMPLATES

        return TemplateInfo(
            template_id=raw["id"],
            name=raw["name"],
            author=raw["author"],
            version=raw["version"],
            supports_channels=list(channel_files.keys()),
            variables_required=variables,
            preview_image=raw.get("preview_image"),
            is_builtin=is_builtin,
            is_verified=is_verified,
            is_active=True,
            channel_files=channel_files,
        )

    def _get_or_create_env(self, info: TemplateInfo) -> SandboxedEnvironment:
        """Return a cached sandboxed Jinja2 env for *this* template package."""
        env_key = f"{info.template_id}@{info.version}"
        if env_key not in self._jinja_cache:
            env = SandboxedEnvironment(
                autoescape=True,
                enable_async=False,
            )
            # Register safe globals — these are the *only* top-level names
            # available inside templates.
            for name in _SAFE_GLOBALS:
                env.globals[name] = ""
            self._jinja_cache[env_key] = env
        return self._jinja_cache[env_key]


