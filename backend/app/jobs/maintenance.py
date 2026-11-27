from app.services.maintenance import cleanup_media, update_ytdlp


async def cleanup_media_job() -> None:
    await cleanup_media()


async def update_ytdlp_job() -> None:
    await update_ytdlp()
