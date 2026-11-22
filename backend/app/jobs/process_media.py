import logging
import time

from app.services.media import process_next

logger = logging.getLogger(__name__)


async def process_media_job() -> None:
    started = time.monotonic()
    count = 0
    while await process_next():
        count += 1
    if count:
        logger.info("process_media: %d media in %.1fs", count, time.monotonic() - started)
