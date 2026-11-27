import asyncio

from app.services.maintenance import backup_db, cleanup_media, update_ytdlp


async def cleanup_media_job() -> None:
    await cleanup_media()


async def update_ytdlp_job() -> None:
    await update_ytdlp()


async def backup_db_job() -> None:
    await asyncio.to_thread(backup_db)
