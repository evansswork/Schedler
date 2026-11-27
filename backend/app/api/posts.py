from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlmodel import Session, SQLModel, col, select

from app.api.accounts import AccountRead
from app.api.media import MediaRead
from app.core.db import get_session
from app.models import Account, MediaAsset, Post, PostTarget, TargetStatus, YtKind
from app.services.accounts import get_account
from app.services.posts import (
    PostBatchIn,
    RescheduleIn,
    cancel,
    create_batch,
    mark_published,
    reschedule,
    retry,
)
from app.services.slots import next_free_slots

router = APIRouter()

# shortcut: plain limit, no cursor; a month of the calendar is ~800 targets at 25/day.
# Add keyset paging on (scheduled_at, id) once unfiltered lists outgrow this.
MAX_TARGETS = 1000


class TargetRead(SQLModel):
    id: str
    post_id: str
    status: TargetStatus
    scheduled_at: datetime
    caption: str
    title: str | None
    yt_kind: YtKind | None
    published_url: str | None
    last_error_human: str | None
    account: AccountRead
    media: MediaRead


def _read(target: PostTarget, account: Account, media: MediaAsset) -> TargetRead:
    return TargetRead.model_validate(
        target.model_dump()
        | {
            "account": AccountRead.of(account),
            "media": MediaRead.of(media),
        }
    )


@router.post("/posts", status_code=201)
def create_posts(
    body: PostBatchIn, session: Annotated[Session, Depends(get_session)]
) -> list[TargetRead]:
    targets = create_batch(session, body)
    return list_targets(session, ids=[t.id for t in targets])


@router.get("/targets")
def list_targets(
    session: Annotated[Session, Depends(get_session)],
    status: Annotated[list[TargetStatus] | None, Query()] = None,
    ids: Annotated[list[str] | None, Query()] = None,
    start: AwareDatetime | None = None,
    end: AwareDatetime | None = None,
) -> list[TargetRead]:
    query = (
        select(PostTarget, Account, MediaAsset)
        .join(Account, col(Account.id) == PostTarget.account_id)
        .join(Post, col(Post.id) == PostTarget.post_id)
        .join(MediaAsset, col(MediaAsset.id) == Post.media_id)
        .order_by(col(PostTarget.scheduled_at), col(PostTarget.id))
        .limit(MAX_TARGETS)
    )
    if status:
        query = query.where(col(PostTarget.status).in_(status))
    if ids is not None:
        query = query.where(col(PostTarget.id).in_(ids))
    if start is not None:
        query = query.where(col(PostTarget.scheduled_at) >= start)
    if end is not None:
        query = query.where(col(PostTarget.scheduled_at) < end)
    return [_read(t, a, m) for t, a, m in session.exec(query)]


@router.patch("/targets/reschedule")
async def reschedule_targets(
    body: RescheduleIn, session: Annotated[Session, Depends(get_session)]
) -> list[TargetRead]:
    targets = await reschedule(session, body)
    return list_targets(session, ids=[t.id for t in targets])


@router.post("/targets/{target_id}/retry")
def retry_target(target_id: str, session: Annotated[Session, Depends(get_session)]) -> TargetRead:
    retry(session, target_id)
    return list_targets(session, ids=[target_id])[0]


@router.post("/targets/{target_id}/cancel")
async def cancel_target(
    target_id: str, session: Annotated[Session, Depends(get_session)]
) -> TargetRead:
    await cancel(session, target_id)
    return list_targets(session, ids=[target_id])[0]


@router.post("/targets/{target_id}/mark-published")
def mark_target_published(
    target_id: str, session: Annotated[Session, Depends(get_session)]
) -> TargetRead:
    mark_published(session, target_id)
    return list_targets(session, ids=[target_id])[0]


@router.get("/slots/preview")
def preview_slots(
    session: Annotated[Session, Depends(get_session)],
    account_ids: Annotated[list[str], Query()],
    count: Annotated[int, Query(ge=1, le=100)],
) -> dict[str, list[datetime]]:
    """Where `count` videos would land per account in "Slot berikutnya" mode."""
    return {a: next_free_slots(session, get_account(session, a), count) for a in account_ids}
