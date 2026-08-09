



"""i18n middleware — inject Accept-Language parsed locale into request.state."""

from __future__ import annotations

from core.i18n import get_locale, init_i18n
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class I18nMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        lang_header = request.headers.get("Accept-Language", "en")
        request.state.locale = get_locale(lang_header)
        response = await call_next(request)
        return response



