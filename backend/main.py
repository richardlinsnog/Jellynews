

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).parent))

from api.rate_limit import limiter
from core.config import get_settings
from core.logging import get_logger, setup_logging
from core.security import SecurityHeadersMiddleware, build_csp_header


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    log = get_logger("lifespan")
    app_settings = get_settings()

    if not app_settings.APP_SECRET_KEY:
        log.critical("APP_SECRET_KEY is not set — refusing to start")
        sys.exit(1)

    if not app_settings.SECRETS_ENCRYPTION_KEY:
        log.warning(
            "SECRETS_ENCRYPTION_KEY is not set — secrets will be derived from APP_SECRET_KEY. "
            "Set a static key for production to avoid credential invalidation on restarts."
        )

    # Auto-apply Alembic migrations on startup (idempotent)
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(str(Path(__file__).parent / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(Path(__file__).parent / "alembic"))
        command.upgrade(alembic_cfg, "head")
        log.info("Database migrations up to date")
    except Exception as exc:
        log.error("Failed to apply migrations", error=str(exc))
        # Don't crash — allow app to start so user can see healthz failure

    log.info("JellyNews starting", app_env=app_settings.APP_ENV, port=app_settings.PORT)

    # Start background scheduler
    try:
        from jobs import start_scheduler, shutdown_scheduler
        start_scheduler()
    except Exception as exc:
        log.error("Failed to start scheduler", error=str(exc))

    yield

    # Shutdown scheduler gracefully
    try:
        shutdown_scheduler()
    except Exception:
        pass

    log.info("JellyNews shutting down")


app = FastAPI(
    title="JellyNews",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Rate limiting ──────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# ── Security headers ───────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── CORS ───────────────────────────────────────────────────────
app_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/healthz")
async def healthz():
    return JSONResponse(
        {"status": "ok", "version": "0.1.0"},
        headers={"Content-Security-Policy": build_csp_header()},
    )


from api.routes_audit import router as audit_router  # noqa: E402
from api.routes_auth import router as auth_router  # noqa: E402
from api.routes_channels import router as channels_router  # noqa: E402
from api.routes_custom_news import router as custom_news_router  # noqa: E402
from api.routes_jellyfin import router as jellyfin_router  # noqa: E402
from api.routes_logs import router as logs_router  # noqa: E402
from api.routes_newsletter import router as newsletter_router  # noqa: E402
from api.routes_setup import router as setup_router  # noqa: E402
from api.routes_subscribers import router as subscribers_router  # noqa: E402
from api.routes_subscribers import unsub_router  # noqa: E402
from api.routes_templates import router as templates_router  # noqa: E402

app.include_router(audit_router)
app.include_router(auth_router)
app.include_router(channels_router)
app.include_router(custom_news_router)
app.include_router(jellyfin_router)
app.include_router(logs_router)
app.include_router(newsletter_router)
app.include_router(setup_router)
app.include_router(subscribers_router)
app.include_router(templates_router)
app.include_router(unsub_router)

# ── i18n ─────────────────────────────────────────────────────────
from core.i18n import init_i18n  # noqa: E402
from core.i18n_middleware import I18nMiddleware  # noqa: E402

init_i18n()
app.add_middleware(I18nMiddleware)


# In production, serve the built Vue frontend as static files
import os as _os

static_dir = Path(__file__).parent / "static"
if static_dir.exists() and any(static_dir.iterdir()):
    # Mount /assets/ explicitly first so it takes priority
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets_static")

    @app.get("/{full_path:path}", tags=["spa-fallback"])
    async def spa_fallback(full_path: str):
        """Serve index.html for unmatched SPA routes (client-side routing)."""
        index_file = static_dir / "index.html"
        if index_file.exists():
            from fastapi.responses import FileResponse

            return FileResponse(str(index_file))
        raise HTTPException(status_code=404, detail="Not Found")

