

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_settings
from core.logging import get_logger, setup_logging


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


@app.get("/healthz")
async def healthz():
    return JSONResponse({"status": "ok", "version": "0.1.0"})


# In production, serve the built Vue frontend as static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists() and any(static_dir.iterdir()):
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

