from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, SQLModel, col, select

from app.api.accounts import AccountRead
from app.api.media import MediaRead
from app.core.db import get_session
from app.models import Account, MediaAsset, Post, PostTarget, TargetStatus, YtKind
from app.services.posts import PostBatchIn, create_batch

router = APIRouter()

# shortcut: plain limit, no cursor; fine at ~25 posts/day. Add keyset paging on
# (scheduled_at, id) once Antrian holds more than a few hundred rows.
MAX_TARGETS = 200


class TargetRead(SQLModel):
    id: str
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
    return [_read(t, a, m) for t, a, m in session.exec(query)]
