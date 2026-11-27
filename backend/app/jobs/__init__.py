from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.jobs.buffer import buffer_refill_job, buffer_sync_job
from app.jobs.maintenance import cleanup_media_job, update_ytdlp_job
from app.jobs.notifications import daily_summary_job, send_notifications_job
from app.jobs.process_media import process_media_job
from app.jobs.publish_ig import publish_ig_due_job
from app.jobs.refresh_ig_tokens import refresh_ig_tokens_job

PROCESS_MEDIA = "process_media"
REFRESH_IG_TOKENS = "refresh_ig_tokens"
PUBLISH_IG_DUE = "publish_ig_due"


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_job(
        process_media_job,
        "interval",
        seconds=30,
        id=PROCESS_MEDIA,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(UTC),
    )
    scheduler.add_job(
        publish_ig_due_job,
        "interval",
        seconds=60,
        id=PUBLISH_IG_DUE,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(UTC),
    )
    scheduler.add_job(
        refresh_ig_tokens_job,
        "interval",
        hours=24,
        id=REFRESH_IG_TOKENS,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(UTC),
    )
    for func, job_id, seconds in (
        (buffer_refill_job, "buffer_refill", 120),
        (buffer_sync_job, "buffer_sync", 300),
        (send_notifications_job, "send_notifications", 15),
        (cleanup_media_job, "cleanup_media", 3600),
    ):
        scheduler.add_job(
            func,
            "interval",
            seconds=seconds,
            id=job_id,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(UTC),
        )
    # 23:59 WIB, after the owner's last slot (23:30).
    scheduler.add_job(
        daily_summary_job,
        "cron",
        hour=23,
        minute=59,
        timezone="Asia/Jakarta",
        id="daily_summary",
        max_instances=1,
        coalesce=True,
    )
    # 04:00 WIB: no posting slots then.
    scheduler.add_job(
        update_ytdlp_job,
        "cron",
        hour=4,
        minute=0,
        timezone="Asia/Jakarta",
        id="update_ytdlp",
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def kick(scheduler: AsyncIOScheduler | None, job_id: str) -> None:
    """Run a job now instead of waiting for its next interval (no-op when disabled)."""
    if scheduler is not None:
        scheduler.modify_job(job_id, next_run_time=datetime.now(UTC))
