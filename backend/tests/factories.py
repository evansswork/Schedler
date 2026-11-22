from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session

from app.models import Account, MediaAsset, MediaSource, Platform, Post, PostTarget, Route


def make_account(session: Session, **kw: Any) -> Account:
    defaults: dict[str, Any] = {"platform": Platform.ig, "label": "IG #1", "route": Route.ig_direct}
    account = Account(**(defaults | kw))
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def make_media(session: Session, **kw: Any) -> MediaAsset:
    defaults: dict[str, Any] = {
        "source": MediaSource.tiktok_link,
        "source_url": "https://www.tiktok.com/@owner/video/1",
    }
    media = MediaAsset(**(defaults | kw))
    session.add(media)
    session.commit()
    session.refresh(media)
    return media


def make_target(session: Session, media: MediaAsset, account: Account, **kw: Any) -> PostTarget:
    post = Post(media_id=media.id)
    session.add(post)
    session.flush()
    defaults: dict[str, Any] = {
        "post_id": post.id,
        "account_id": account.id,
        "scheduled_at": datetime(2026, 11, 24, 12, 0, tzinfo=UTC),
    }
    target = PostTarget(**(defaults | kw))
    session.add(target)
    session.commit()
    session.refresh(target)
    return target
