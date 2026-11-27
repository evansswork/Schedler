from datetime import timedelta

from pydantic import AwareDatetime, BaseModel
from sqlmodel import Session, col, select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.models import (
    Account,
    MediaAsset,
    MediaStatus,
    Platform,
    Post,
    PostTarget,
    ScheduleMode,
    TargetStatus,
)
from app.services.routing import youtube_kind

PAST_GRACE = timedelta(minutes=1)


class PostItemIn(BaseModel):
    media_id: str
    caption: str = ""
    scheduled_at: AwareDatetime


class PostBatchIn(BaseModel):
    account_ids: list[str]
    items: list[PostItemIn]


def _check(batch: PostBatchIn, accounts: dict[str, Account], media: dict[str, MediaAsset]) -> None:
    if not batch.account_ids:
        raise DomainError("no_accounts", "Pilih minimal satu akun.", status_code=422)
    if not batch.items:
        raise DomainError("no_videos", "Tambahkan minimal satu video.", status_code=422)
    if missing := set(batch.account_ids) - accounts.keys():
        raise DomainError(
            "account_not_found",
            "Akun yang dipilih nggak ditemukan. Muat ulang halaman.",
            status_code=422,
            detail={"account_ids": sorted(missing)},
        )
    for item in batch.items:
        m = media.get(item.media_id)
        if m is None or m.status in (MediaStatus.failed, MediaStatus.deleted):
            raise DomainError(
                "media_unusable",
                "Ada video yang gagal diproses. Hapus dari daftar dulu.",
                status_code=422,
                detail={"media_id": item.media_id},
            )
        if item.scheduled_at < utcnow() - PAST_GRACE:
            raise DomainError(
                "time_in_past",
                "Waktu tayang sudah lewat. Pilih waktu yang akan datang.",
                status_code=422,
                detail={"media_id": item.media_id},
            )


def create_batch(session: Session, batch: PostBatchIn) -> list[PostTarget]:
    """One Post per video, one PostTarget per (video, account)."""
    accounts = {
        a.id: a
        for a in session.exec(
            select(Account).where(col(Account.id).in_(batch.account_ids), Account.active)
        )
    }
    media_ids = [i.media_id for i in batch.items]
    media = {
        m.id: m for m in session.exec(select(MediaAsset).where(col(MediaAsset.id).in_(media_ids)))
    }
    _check(batch, accounts, media)

    targets: list[PostTarget] = []
    for item in batch.items:
        m = media[item.media_id]
        ready = m.status is MediaStatus.ready
        caption = item.caption.strip() or (m.source_caption or "")
        post = Post(media_id=m.id, default_caption=caption)
        session.add(post)
        for account_id in batch.account_ids:
            account = accounts[account_id]
            yt_kind = None
            if ready and account.platform is Platform.youtube:
                assert m.orientation is not None and m.duration_s is not None
                yt_kind = youtube_kind(m.orientation, m.duration_s)
            targets.append(
                PostTarget(
                    post_id=post.id,
                    account_id=account_id,
                    caption=caption,
                    yt_kind=yt_kind,
                    scheduled_at=item.scheduled_at,
                    schedule_mode=ScheduleMode.exact,
                    status=TargetStatus.queued_local if ready else TargetStatus.waiting_media,
                )
            )
    session.add_all(targets)
    session.commit()
    for t in targets:
        session.refresh(t)
    return targets


RESCHEDULABLE = (TargetStatus.waiting_media, TargetStatus.queued_local)
CANCELLABLE = (TargetStatus.waiting_media, TargetStatus.queued_local, TargetStatus.failed)


class RescheduleIn(BaseModel):
    ids: list[str]
    scheduled_at: AwareDatetime


def _target(session: Session, target_id: str) -> PostTarget:
    target = session.get(PostTarget, target_id)
    if target is None:
        raise DomainError("target_not_found", "Post nggak ditemukan.", status_code=404)
    return target


def reschedule(session: Session, body: RescheduleIn) -> list[PostTarget]:
    if body.scheduled_at < utcnow() - PAST_GRACE:
        raise DomainError(
            "time_in_past", "Waktu tayang sudah lewat. Pilih waktu yang akan datang.", 422
        )
    targets = [_target(session, i) for i in dict.fromkeys(body.ids)]
    if not targets:
        raise DomainError("no_targets", "Pilih minimal satu post.", status_code=422)
    if any(t.status not in RESCHEDULABLE for t in targets):
        raise DomainError(
            "not_reschedulable",
            "Post yang lagi diproses atau sudah tayang nggak bisa dipindah jadwalnya.",
            status_code=409,
        )
    for t in targets:
        t.scheduled_at = body.scheduled_at
        t.next_attempt_at = None
        session.add(t)
    session.commit()
    return targets


def retry(session: Session, target_id: str) -> PostTarget:
    target = _target(session, target_id)
    if target.status is not TargetStatus.failed:
        raise DomainError("not_failed", "Cuma post yang gagal yang bisa dicoba lagi.", 409)
    media = session.exec(
        select(MediaAsset)
        .join(Post, col(Post.media_id) == MediaAsset.id)
        .where(Post.id == target.post_id)
    ).one()
    if media.status is not MediaStatus.ready:
        raise DomainError(
            "media_unusable",
            "Videonya gagal diproses, jadi post ini nggak bisa dicoba lagi. Buat post baru.",
            status_code=409,
        )
    target.sqlmodel_update(
        {
            "status": TargetStatus.queued_local,
            "attempts": 0,
            "next_attempt_at": None,
            "provider_ref": None,
            "last_error": None,
            "last_error_human": None,
        }
    )
    session.add(target)
    session.commit()
    return target


def cancel(session: Session, target_id: str) -> PostTarget:
    target = _target(session, target_id)
    if target.status is TargetStatus.publishing:
        raise DomainError(
            "busy_publishing",
            "Post ini lagi dikirim ke Instagram, jadi nggak bisa dibatalkan sekarang.",
            status_code=409,
        )
    if target.status not in CANCELLABLE:
        raise DomainError(
            "not_cancellable", "Post yang sudah tayang atau dikirim nggak bisa dibatalkan.", 409
        )
    target.status = TargetStatus.cancelled
    target.next_attempt_at = None
    session.add(target)
    session.commit()
    return target
