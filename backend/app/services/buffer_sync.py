"""Keep each Buffer channel topped up and read back what Buffer published.

Buffer's free API budget is small (~100 requests/day on average), so the number of posts
waiting in each channel is counted locally (our own sent_to_buffer targets) instead of
asking Buffer, and a post is only looked up after its due time.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app.core.config import get_settings
from app.core.db import get_engine, utcnow
from app.models import Account, PostTarget, Route, TargetStatus
from app.publishers.buffer_client import budget_ok
from app.services.publishing import advance

logger = logging.getLogger(__name__)

CHANNEL_LIMIT = 10  # Buffer free plan: scheduled posts per channel at a time
SYNC_AFTER = timedelta(minutes=2)
RECHECK = timedelta(minutes=10)


def _ready(now: datetime) -> ColumnElement[bool]:
    return (col(PostTarget.next_attempt_at).is_(None)) | (col(PostTarget.next_attempt_at) <= now)


def _refill_plan() -> list[str]:
    """Target ids to send now, earliest first, never more than 10 per channel."""
    now = utcnow()
    dry_run = get_settings().dry_run
    ids: list[str] = []
    with Session(get_engine()) as s:
        accounts = s.exec(select(Account).where(Account.route == Route.buffer, Account.active))
        for account in accounts:
            if not dry_run and not budget_ok(account.buffer_key_ref or "0"):
                logger.warning("buffer_refill: API budget low, holding %s", account.label)
                continue
            in_buffer = s.exec(
                select(func.count())
                .select_from(PostTarget)
                .where(
                    PostTarget.account_id == account.id,
                    PostTarget.status == TargetStatus.sent_to_buffer,
                )
            ).one()
            free = CHANNEL_LIMIT - in_buffer
            if free <= 0:
                continue
            ids += s.exec(
                select(PostTarget.id)
                .where(
                    PostTarget.account_id == account.id,
                    PostTarget.status == TargetStatus.queued_local,
                    _ready(now),
                )
                .order_by(col(PostTarget.scheduled_at), col(PostTarget.id))
                .limit(free)
            ).all()
    return ids


async def buffer_refill() -> int:
    sent = 0
    for target_id in _refill_plan():
        await advance(target_id)
        sent += 1
    if sent:
        logger.info("buffer_refill: %d sent", sent)
    return sent


async def buffer_sync() -> int:
    """Look up posts Buffer should have published by now. Returns how many went live."""
    now = utcnow()
    with Session(get_engine()) as s:
        ids = s.exec(
            select(PostTarget.id)
            .join(Account, col(Account.id) == PostTarget.account_id)
            .where(
                Account.route == Route.buffer,
                PostTarget.status == TargetStatus.sent_to_buffer,
                col(PostTarget.scheduled_at) < now - SYNC_AFTER,
                _ready(now),
            )
            .order_by(col(PostTarget.scheduled_at))
        ).all()
    published = 0
    for target_id in ids:
        published += await advance(target_id, recheck=RECHECK)
    return published
