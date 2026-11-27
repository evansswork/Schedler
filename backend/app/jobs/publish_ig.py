from app.services.publishing import publish_ig_due


async def publish_ig_due_job() -> None:
    await publish_ig_due()
