from app.services.buffer_sync import buffer_refill, buffer_sync


async def buffer_refill_job() -> None:
    await buffer_refill()


async def buffer_sync_job() -> None:
    await buffer_sync()
