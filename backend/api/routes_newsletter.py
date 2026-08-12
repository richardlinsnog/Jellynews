"""Newsletter dispatch — manual trigger endpoint."""

import datetime

from api.deps import get_current_user, get_db
from api.rate_limit import limiter
from core.logging import get_logger
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel
from services.newsletter_sender import DeliveryReport, NewsletterSender
from services.vault import SecretsVaultService, get_vault
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/newsletter", tags=["newsletter"])


class NewsletterSendRequest(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    library_names: list[str] | None = None
    subscriber_tags: list[str] | None = None
    force: bool = False


@router.post("/send", response_model=DeliveryReport)
@limiter.limit("3/minute")
async def send_newsletter(
    request: Request,
    body: NewsletterSendRequest = Body(default_factory=NewsletterSendRequest),
    db: AsyncSession = Depends(get_db),
    vault: SecretsVaultService = Depends(get_vault),
    _user: dict = Depends(get_current_user),
) -> DeliveryReport:
    """Manually trigger a newsletter send to all active channels."""
    from api.routes_jellyfin import _get_jellyfin_service

    jellyfin = await _get_jellyfin_service(db)
    if not jellyfin.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jellyfin is not configured. Run the setup wizard first.",
        )

    date_from_dt = datetime.datetime.fromisoformat(body.date_from).replace(tzinfo=datetime.timezone.utc) if body.date_from else None
    date_to_dt = datetime.datetime.fromisoformat(body.date_to).replace(tzinfo=datetime.timezone.utc) if body.date_to else None

    sender = NewsletterSender()
    public_url = str(request.base_url).rstrip("/")
    try:
        report = await sender.send(
            db, jellyfin, vault,
            date_from=date_from_dt,
            date_to=date_to_dt,
            library_names=body.library_names,
            subscriber_tags=body.subscriber_tags,
            force=body.force,
            public_url=public_url,
        )
    except Exception as exc:
        logger.exception("send_newsletter_failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return report
