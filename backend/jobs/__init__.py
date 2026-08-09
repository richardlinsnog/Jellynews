"""APScheduler jobs — automated newsletter dispatch with SQLite advisory lock."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from core.config import get_settings
from core.logging import get_logger

logger = get_logger("scheduler")

scheduler = AsyncIOScheduler(timezone=get_settings().TZ)


def _db_path() -> Path:
    return get_settings().db_path


def _acquire_scheduler_lock(lock_name: str = "newsletter_send") -> bool:
    """Try to acquire an advisory lock using SQLite's built-in locking.

    Uses a dedicated lock table — WAL mode allows concurrent readers
    while the lock-holder performs writes.
    """
    db_path = _db_path()
    try:
        conn = sqlite3.connect(str(db_path), timeout=1)
        conn.execute("CREATE TABLE IF NOT EXISTS _scheduler_lock (name TEXT PRIMARY KEY, acquired_at REAL)")
        conn.execute("INSERT OR IGNORE INTO _scheduler_lock (name, acquired_at) VALUES (?, ?)", (lock_name, time.time()))
        conn.commit()
        conn.close()
        # If we inserted the row, we own the lock
        return True
    except sqlite3.OperationalError:
        return False


def _release_scheduler_lock(lock_name: str = "newsletter_send") -> None:
    db_path = _db_path()
    try:
        conn = sqlite3.connect(str(db_path), timeout=1)
        conn.execute("DELETE FROM _scheduler_lock WHERE name = ?", (lock_name,))
        conn.commit()
        conn.close()
    except Exception:
        pass


async def _send_newsletter_job() -> None:
    """The actual job: fetch new items and send to all active channels."""
    if not _acquire_scheduler_lock():
        logger.debug("scheduler_lock_not_acquired")
        return

    try:
        from core.database import async_session_factory
        from services.jellyfin import JellyfinService
        from services.newsletter_sender import NewsletterSender
        from services.vault import get_vault
        from api.routes_jellyfin import _get_jellyfin_service

        async with async_session_factory() as session:
            try:
                jellyfin = await _get_jellyfin_service(session)
                if not jellyfin.is_configured:
                    logger.debug("scheduler_skip_no_jellyfin")
                    return
                sender = NewsletterSender()
                vault = get_vault()
                report = await sender.send(session, jellyfin, vault)
                logger.info("scheduled_newsletter_sent", **report.__dict__)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except Exception:
        logger.exception("scheduler_job_failed")
    finally:
        _release_scheduler_lock()


def _build_cron_trigger() -> CronTrigger:
    """Read cron expression from AppSettings (sync fallback) or use default (daily 8 AM)."""
    cron_expr = None
    try:
        db_path = _db_path()
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = 'cron_expression'"
        ).fetchone()
        conn.close()
        if row:
            cron_expr = row[0]
    except Exception:
        pass

    cron_expr = cron_expr or "0 8 * * *"
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        cron_expr = "0 8 * * *"

    return CronTrigger.from_crontab(cron_expr, timezone=get_settings().TZ)


def start_scheduler() -> None:
    """Register jobs and start the scheduler. Called from lifespan startup."""
    trigger = _build_cron_trigger()
    scheduler.add_job(
        _send_newsletter_job,
        trigger=trigger,
        id="newsletter_send",
        name="Send newsletter to all active channels",
        replace_existing=True,
        max_instances=1,
    )
    # Log cleanup job — runs weekly, keeps 90 days
    scheduler.add_job(
        _cleanup_old_logs,
        trigger=CronTrigger(day_of_week="sun", hour=3, timezone=get_settings().TZ),
        id="cleanup_logs",
        name="Clean up old DeliveryLog and MediaLog entries",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("scheduler_started", num_jobs=len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    """Gracefully stop the scheduler. Called from lifespan shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("scheduler_stopped")


async def _cleanup_old_logs(retention_days: int = 90) -> None:
    """Expurge old DeliveryLog and MediaLog entries beyond retention."""
    from datetime import UTC, datetime, timedelta

    from core.database import async_session_factory
    from models.delivery_log import DeliveryLog
    from models.media_log import MediaLog
    from sqlalchemy import delete

    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    try:
        async with async_session_factory() as session:
            result_dl = await session.execute(
                delete(DeliveryLog).where(DeliveryLog.created_at < cutoff)
            )
            result_ml = await session.execute(
                delete(MediaLog).where(MediaLog.last_notified_at < cutoff)
            )
            await session.commit()
            logger.info(
                "log_cleanup_complete",
                delivery_logs_deleted=result_dl.rowcount,
                media_logs_deleted=result_ml.rowcount,
            )
    except Exception:
        logger.exception("log_cleanup_failed")
