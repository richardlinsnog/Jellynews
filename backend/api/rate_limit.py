



from __future__ import annotations

from core.config import settings
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
)

login_rate_limit = settings.RATE_LIMIT_LOGIN


def setup_rate_limit(requests: int, interval: str) -> str:
    return f"{requests}/{interval}"


