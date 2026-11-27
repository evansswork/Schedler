"""Publishing steps shared by every route: one small step per target per job run.

IG direct is driven by publish_ig_due here; Buffer by services/buffer_sync.py.
See ARCHITECTURE §4-5.
"""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import update
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.db import get_engine, utcnow
from app.models import (
    Account,
    EventLevel,
    MediaAsset,
    Post,
    PostTarget,
    Route,
    TargetStatus,
)
from app.publishers import get_publisher
from app.publishers.errors import ErrorKind, PublishError
from app.publishers.ig_client import IgError
from app.services.accounts import mark_token_invalid
from app.services.events import log_event

logger = logging.getLogger(__name__)

LEAD = timedelta(minutes=5)  # create the container early so it is ready at the slot
BACKOFF = (timedelta(minutes=2), timedelta(minutes=5))
MAX_ATTEMPTS = len(BACKOFF) + 1
MISSED_AFTER = timedelta(hours=6)
MISSED_HUMAN = "Terlewat karena server mati. Jadwalkan ulang?"
UNEXPECTED_HUMAN = "Gagal posting karena error tak terduga. Detailnya ada di log server."
_ACTIVE = (TargetStatus.queued_local, TargetStatus.publishing)


def _ig_account_ids() -> Any:
    return select(Account.id).where(Account.route == Route.ig_direct)


def fail_missed_ig() -> int:
    """At startup: IG posts more than 6 h overdue are not published late."""
    with Session(get_engine()) as s:
        result = s.connection().execute(
            update(PostTarget)
            .where(
                col(PostTarget.status).in_(_ACTIVE),
                col(PostTarget.scheduled_at) < utcnow() - MISSED_AFTER,
                col(PostTarget.account_id).in_(_ig_account_ids()),
            )
            .values(
                status=TargetStatus.failed,
                last_error="missed_downtime",
                last_error_human=MISSED_HUMAN,
                updated_at=utcnow(),
            )
        )
        s.commit()
    if result.rowcount:
        logger.warning("fail_missed_ig: %d IG posts missed", result.rowcount)
    return result.rowcount


def _due_ids() -> list[str]:
    now = utcnow()
    with Session(get_engine()) as s:
        return list(
            s.exec(
                select(PostTarget.id)
                .join(Account, col(Account.id) == PostTarget.account_id)
                .where(
                    Account.route == Route.ig_direct,
                    Account.active,
                    col(PostTarget.status).in_(_ACTIVE),
                    col(PostTarget.scheduled_at) <= now + LEAD,
                    (col(PostTarget.next_attempt_at).is_(None))
                    | (col(PostTarget.next_attempt_at) <= now),
                )
                .order_by(col(PostTarget.scheduled_at), col(PostTarget.id))
            )
        )


async def publish_ig_due() -> int:
    """Advance every due IG target by one step. Returns how many were published."""
    published = 0
    for target_id in _due_ids():
        published += await advance(target_id)
    if published:
        logger.info("publish_ig_due: %d published", published)
    return published


async def advance(target_id: str, recheck: timedelta | None = None) -> bool:
    """Submit a queued target or sync a sent one. Returns True when it went live.

    `recheck`: when nothing changed, wait this long before looking again."""
    with Session(get_engine()) as s:
        row = s.exec(
            select(PostTarget, Account, MediaAsset)
            .join(Account, col(Account.id) == PostTarget.account_id)
            .join(Post, col(Post.id) == PostTarget.post_id)
            .join(MediaAsset, col(MediaAsset.id) == Post.media_id)
            .where(PostTarget.id == target_id)
        ).one()
    target, account, media = row  # detached snapshots; no transaction held during I/O
    was = target.status
    try:
        publisher = get_publisher(account, get_settings())
        if was is TargetStatus.queued_local:
            sub = await publisher.submit(target, media)
            status, ref, url = sub.status, sub.provider_ref, sub.published_url
        else:
            res = await publisher.sync(target)
            status, ref, url = res.status, target.provider_ref, res.published_url
    except PublishError as err:
        _on_error(target_id, was, err)
        return False
    except Exception as exc:  # keep the job alive; the target gets a clear state
        logger.exception("publish step failed for %s", target_id)
        err = PublishError(
            ErrorKind.retryable, UNEXPECTED_HUMAN, code="unexpected", raw={"error": repr(exc)}
        )
        _on_error(target_id, was, err)
        return False
    if status is was and ref == target.provider_ref:
        # Still waiting (IG container processing, not due yet, Buffer not sent yet).
        if recheck is not None:
            _update_if(target_id, was, {"next_attempt_at": utcnow() + recheck})
        return False
    values: dict[str, Any] = {"status": status, "provider_ref": ref, "next_attempt_at": None}
    if status is TargetStatus.published:
        values |= {"published_url": url, "last_error": None, "last_error_human": None}
    applied = _update_if(target_id, was, values)
    if applied and status is TargetStatus.published:
        with Session(get_engine()) as s:
            log_event(s, EventLevel.info, "target", target_id, "Tayang", {"url": url})
            s.commit()
    return applied and status is TargetStatus.published


def _update_if(target_id: str, expected: TargetStatus, values: dict[str, Any]) -> bool:
    """Write only if nobody changed the status meanwhile (e.g. the owner cancelled)."""
    with Session(get_engine()) as s:
        result = s.connection().execute(
            update(PostTarget)
            .where(col(PostTarget.id) == target_id, PostTarget.status == expected)
            .values(**values, updated_at=utcnow())
        )
        s.commit()
        return result.rowcount == 1


def _on_error(target_id: str, was: TargetStatus, err: PublishError) -> None:
    now = utcnow()
    with Session(get_engine()) as s:
        target = s.get_one(PostTarget, target_id)
        if target.status is not was:
            return  # cancelled or changed while we were talking to Instagram
        log_event(s, EventLevel.error, "target", target_id, err.code, err.raw)
        target.last_error = err.code
        if err.kind is ErrorKind.wait:
            target.next_attempt_at = now + err.wait  # not counted as an attempt
            target.last_error_human = err.human
        elif err.kind is ErrorKind.manual:
            target.status = TargetStatus.manual_required
            target.next_attempt_at = None
            target.last_error_human = err.human
        elif err.kind is ErrorKind.retryable and target.attempts + 1 < MAX_ATTEMPTS:
            target.attempts += 1
            target.status = TargetStatus.queued_local
            target.provider_ref = None  # a fresh container next time
            target.next_attempt_at = now + BACKOFF[target.attempts - 1]
            target.last_error_human = f"{err.human} Dicoba lagi otomatis."
        else:
            if err.kind is ErrorKind.retryable:
                target.attempts += 1
                human = f"{err.human} Sudah dicoba {target.attempts}x."
            else:
                human = err.human
            target.status = TargetStatus.failed
            target.next_attempt_at = None
            target.last_error_human = human
            # A dead IG token flags the account; a missing Buffer link or key does not.
            if (
                err.kind is ErrorKind.reconnect
                and isinstance(err, IgError)
                and err.code != "ig_not_connected"
            ):
                mark_token_invalid(s, s.get_one(Account, target.account_id))
        s.add(target)
        s.commit()
