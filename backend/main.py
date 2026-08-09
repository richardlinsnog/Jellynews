

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

    log.info("JellyNews starting", app_env=app_settings.APP_ENV, port=app_settings.PORT)
    yield
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


from api.routes_auth import router as auth_router  # noqa: E402
from api.routes_channels import router as channels_router  # noqa: E402
from api.routes_jellyfin import router as jellyfin_router  # noqa: E402
from api.routes_newsletter import router as newsletter_router  # noqa: E402
from api.routes_setup import router as setup_router  # noqa: E402
from api.routes_templates import router as templates_router  # noqa: E402

app.include_router(auth_router)
app.include_router(channels_router)
app.include_router(jellyfin_router)
app.include_router(newsletter_router)
app.include_router(setup_router)
app.include_router(templates_router)

# In production, serve the built Vue frontend as static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists() and any(static_dir.iterdir()):
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

