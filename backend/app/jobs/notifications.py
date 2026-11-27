from app.services.notifications import queue_daily_summary, send_pending


async def send_notifications_job() -> None:
    await send_pending()


async def daily_summary_job() -> None:
    queue_daily_summary()
    await send_pending()
