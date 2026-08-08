
"""Shared test fixtures for JellyNews backend tests."""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import models.app_settings  # noqa: F401 — ensure table registration
import models.media_log  # noqa: F401
import models.secret  # noqa: F401
import models.template  # noqa: F401
import models.user  # noqa: F401
from models.base import Base


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Session-scoped unique test database URL."""
    db_id = uuid.uuid4().hex[:8]
    db_path = Path(__file__).parent.parent / "data" / f"test_{db_id}.db"
    return f"sqlite+aiosqlite:///{db_path.absolute()}"


@pytest_asyncio.fixture(scope="session")
async def session_engine(test_db_url: str):
    """Session-scoped async engine, shared across all tests."""
    engine = create_async_engine(test_db_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()
    # Clean up test database file
    db_path = test_db_url.replace("sqlite+aiosqlite:///", "")
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest_asyncio.fixture
async def db(session_engine) -> AsyncGenerator[AsyncSession, None]:
    """Per-test database session with automatic rollback + cleanup."""
    async_session = async_sessionmaker(session_engine, expire_on_commit=False)

    # Truncate all tables before each test
    async with session_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def app(db):
    """Create FastAPI app with overridden dependencies for testing."""
    os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-for-tests-only")
    os.environ.setdefault("APP_ENV", "testing")
    os.environ.setdefault("FIRST_RUN_SETUP", "true")

    from api.rate_limit import limiter
    from main import app

    # Override get_db dependency
    async def override_get_db():
        yield db

    from core.database import get_db

    app.dependency_overrides[get_db] = override_get_db

    # Reset rate limiter storage before each test
    if hasattr(limiter, "_storage"):
        limiter._storage.reset()

    yield app

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTPX test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _reset_template_registry():
    """Reset TemplateRegistry singleton between tests."""
    from services.template_registry import TemplateRegistry

    TemplateRegistry._instance = None
    yield
    TemplateRegistry._instance = None


@pytest.fixture(autouse=True)
def _restore_templates_root():
    """Restore the templates root in case any test monkeypatched it."""
    import services.template_registry as mod

    before = mod._TEMPLATES_ROOT
    yield
    mod._TEMPLATES_ROOT = before
