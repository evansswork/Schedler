from app.services.accounts import refresh_expiring_tokens


async def refresh_ig_tokens_job() -> None:
    await refresh_expiring_tokens()
