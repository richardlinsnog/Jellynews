"""Newsletter dispatch — manual trigger endpoint."""

from api.deps import get_current_user, get_db
from api.rate_limit import limiter
from core.logging import get_logger
from fastapi import APIRouter, Depends, HTTPException, Request, status
from services.newsletter_sender import DeliveryReport, NewsletterSender
from services.vault import SecretsVaultService, get_vault
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/newsletter", tags=["newsletter"])


@router.post("/send", response_model=DeliveryReport)
@limiter.limit("3/minute")
async def send_newsletter(
    request: Request,
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

    sender = NewsletterSender()
    report = await sender.send(db, jellyfin, vault)
    return report
