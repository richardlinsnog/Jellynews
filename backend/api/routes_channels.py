

"""Channel management — CRUD, list types, and test connectivity."""

import json

from api.deps import get_current_user, get_db
from api.rate_limit import limiter
from core.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models.channel import Channel
from models.secret import Secret
from schemas.channel import (
    ChannelCreateRequest,
    ChannelDetail,
    ChannelListItem,
    ChannelListResponse,
    ChannelTestResponse,
    ChannelUpdateRequest,
)
from services.channel_registry import ChannelNotFoundError, ChannelRegistry
from services.vault import SecretsVaultService, get_vault
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/channels", tags=["channels"])


def _registry() -> ChannelRegistry:
    return ChannelRegistry.get()


@router.get("/types", response_model=ChannelListResponse)
@limiter.limit("60/minute")
async def list_channel_types(
    request: Request,
    _user: dict = Depends(get_current_user),
) -> ChannelListResponse:
    """Return all registered channel type names."""
    return ChannelListResponse(available_types=_registry().available)


@router.get("/types/{channel_type}")
@limiter.limit("60/minute")
async def get_channel_type_info(
    request: Request,
    channel_type: str,
    _user: dict = Depends(get_current_user),
) -> dict:
    """Return config keys and metadata for a channel type."""
    ch_cls = _registry().get_channel(channel_type)
    return {
        "channel_type": ch_cls.name,
        "config_keys": ch_cls.config_keys,
    }


# ── CRUD ───────────────────────────────────────────────────────────────


@router.get("", response_model=list[ChannelListItem])
@limiter.limit("60/minute")
async def list_channels(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[ChannelListItem]:
    """Return all configured channel instances."""
    result = await db.execute(select(Channel).order_by(Channel.id))
    rows = result.scalars().all()
    return [
        ChannelListItem(
            id=r.id,
            channel_type=r.channel_type,
            label=r.label,
            active=r.active,
            template_id=r.template_id,
            language=r.language,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/{channel_id}", response_model=ChannelDetail)
@limiter.limit("60/minute")
async def get_channel(
    request: Request,
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> ChannelDetail:
    """Return detail for a single channel instance."""
    row = await db.get(Channel, channel_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    try:
        ch_cls = _registry().get_channel(row.channel_type)
        available_keys = ch_cls.config_keys
    except ChannelNotFoundError:
        available_keys = []

    return ChannelDetail(
        id=row.id,
        channel_type=row.channel_type,
        label=row.label,
        active=row.active,
        template_id=row.template_id,
        language=row.language,
        created_at=row.created_at,
        updated_at=row.updated_at,
        available_config_keys=available_keys,
    )


@router.post("", response_model=ChannelDetail, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_channel(
    request: Request,
    payload: ChannelCreateRequest,
    db: AsyncSession = Depends(get_db),
    vault: SecretsVaultService = Depends(get_vault),
    _user: dict = Depends(get_current_user),
) -> ChannelDetail:
    """Create a new channel instance (config values encrypted)."""
    # Validate channel type exists
    _registry().get_channel(payload.channel_type)

    encrypted = vault.encrypt(json.dumps(payload.config, ensure_ascii=False))
    secret = Secret(category=payload.channel_type, key="config", encrypted_value=encrypted)
    db.add(secret)
    await db.flush()

    row = Channel(
        channel_type=payload.channel_type,
        label=payload.label,
        config_ref=secret.id,
        active=payload.active,
        template_id=payload.template_id,
        language=payload.language,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    ch_cls = _registry().get_channel(row.channel_type)
    return ChannelDetail(
        id=row.id,
        channel_type=row.channel_type,
        label=row.label,
        active=row.active,
        template_id=row.template_id,
        language=row.language,
        created_at=row.created_at,
        updated_at=row.updated_at,
        available_config_keys=ch_cls.config_keys,
    )


@router.patch("/{channel_id}", response_model=ChannelDetail)
@limiter.limit("30/minute")
async def update_channel(
    request: Request,
    channel_id: int,
    payload: ChannelUpdateRequest,
    db: AsyncSession = Depends(get_db),
    vault: SecretsVaultService = Depends(get_vault),
    _user: dict = Depends(get_current_user),
) -> ChannelDetail:
    """Update an existing channel instance."""
    row = await db.get(Channel, channel_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    if payload.label is not None:
        row.label = payload.label
    if payload.active is not None:
        row.active = payload.active
    if payload.template_id is not None:
        row.template_id = payload.template_id
    if payload.language is not None:
        row.language = payload.language

    if payload.config is not None:
        old_secret = await db.get(Secret, row.config_ref)
        if old_secret:
            encrypted = vault.encrypt(json.dumps(payload.config, ensure_ascii=False))
            old_secret.encrypted_value = encrypted

    await db.commit()
    await db.refresh(row)

    try:
        ch_cls = _registry().get_channel(row.channel_type)
        available_keys = ch_cls.config_keys
    except ChannelNotFoundError:
        available_keys = []

    return ChannelDetail(
        id=row.id,
        channel_type=row.channel_type,
        label=row.label,
        active=row.active,
        template_id=row.template_id,
        language=row.language,
        created_at=row.created_at,
        updated_at=row.updated_at,
        available_config_keys=available_keys,
    )


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_channel(
    request: Request,
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> None:
    """Delete a channel instance and its associated secret."""
    row = await db.get(Channel, channel_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    secret = await db.get(Secret, row.config_ref)
    if secret:
        await db.delete(secret)

    await db.delete(row)
    await db.commit()


# ── Connection test ────────────────────────────────────────────────────


@router.post("/{channel_id}/test", response_model=ChannelTestResponse)
@limiter.limit("10/minute")
async def test_channel_connection(
    request: Request,
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    vault: SecretsVaultService = Depends(get_vault),
    _user: dict = Depends(get_current_user),
) -> ChannelTestResponse:
    """Test connectivity for a configured channel."""
    row = await db.get(Channel, channel_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    secret = await db.get(Secret, row.config_ref)
    if not secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Config not found")

    try:
        config = json.loads(vault.decrypt(secret.encrypted_value))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt channel config",
        )

    result = await _registry().test_connection(row.channel_type, config)
    return ChannelTestResponse(
        status=result.status.value,
        message=result.message,
        latency_ms=result.latency_ms,
    )

