

from __future__ import annotations

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings


def _ensure_data_dir() -> None:
    db_path = settings.db_path
    data_dir = db_path.parent
    data_dir.mkdir(parents=True, exist_ok=True)


_ensure_data_dir()

# Use aiosqlite for async operations; add prefix only if missing
_database_url = settings.DATABASE_URL
if not _database_url.startswith("sqlite+aiosqlite"):
    _database_url = _database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

engine = create_async_engine(
    _database_url,
    poolclass=NullPool,
    connect_args={"check_same_thread": False},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all() -> None:
    """Create all tables — used by tests and first-run setup."""
    from models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


