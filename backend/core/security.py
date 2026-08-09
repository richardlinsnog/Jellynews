
"""Security middleware: CORS, CSP, and HTTP security headers."""

from __future__ import annotations

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security-related HTTP headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "0",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": (
                "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
                "magnetometer=(), microphone=(), payment=(), usb=()"
            ),
            "Content-Security-Policy": build_csp_header(),
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "Server": "JellyNews",
        }

        for header, value in headers.items():
            response.headers.setdefault(header, value)

        return response


def build_csp_header(report_uri: str | None = None) -> str:
    """Build Content-Security-Policy header value.

    Follows a defense-in-depth approach suitable for a self-hosted app.
    """
    policies = [
        "default-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: https://cdn.howonlee.me",
        "connect-src 'self'",
        "media-src 'self'",
        "object-src 'none'",
    ]

    if report_uri:
        policies.append(f"report-uri {report_uri}")

    return "; ".join(policies)
