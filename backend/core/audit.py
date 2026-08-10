

"""Centralized audit-log helper.

All audit entries are written synchronously within the same DB session used by the
current request — we rely on the caller's commit to persist them.  This keeps the
design simple and avoids stale-session / fire-and-forget issues.
"""

from __future__ import annotations

from typing import Any

from core.logging import get_logger
from models.audit_log import AuditLog
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


def audit_log(
    db: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Add an audit entry to *db*.  The caller is responsible for committing."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    logger.debug(
        "audit_recorded",
        action=action,
        user_id=user_id,
        resource=f"{resource_type}/{resource_id}",
    )

