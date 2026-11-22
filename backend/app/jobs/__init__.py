from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.jobs.process_media import process_media_job

PROCESS_MEDIA = "process_media"


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
    return scheduler


def kick(scheduler: AsyncIOScheduler | None, job_id: str) -> None:
    """Run a job now instead of waiting for its next interval (no-op when disabled)."""
    if scheduler is not None:
        scheduler.modify_job(job_id, next_run_time=datetime.now(UTC))
