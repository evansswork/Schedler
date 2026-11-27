from collections.abc import Awaitable, Callable
from datetime import timedelta

from pydantic import AwareDatetime, BaseModel
from sqlmodel import Session, col, select

from app.core.config import get_settings
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
from app.publishers import get_publisher
from app.publishers.base import Publisher
from app.publishers.errors import PublishError
from app.services.routing import youtube_kind
from app.services.slots import next_free_slots

PAST_GRACE = timedelta(minutes=1)


class PostItemIn(BaseModel):
    media_id: str
    caption: str = ""
    scheduled_at: AwareDatetime | None = None  # required in exact mode


class PostBatchIn(BaseModel):
    account_ids: list[str]
    items: list[PostItemIn]
    schedule_mode: ScheduleMode = ScheduleMode.exact


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
        if batch.schedule_mode is ScheduleMode.slot:
            continue
        if item.scheduled_at is None:
            raise DomainError(
                "time_missing",
                "Pilih waktu tayang untuk setiap video.",
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
    # Slot mode: each account fills its own next free slots, in video order.
    slot_times = (
        {a: next_free_slots(session, accounts[a], len(batch.items)) for a in batch.account_ids}
        if batch.schedule_mode is ScheduleMode.slot
        else {}
    )

    targets: list[PostTarget] = []
    for index, item in enumerate(batch.items):
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
                    scheduled_at=(
                        slot_times[account_id][index] if slot_times else item.scheduled_at
                    ),
                    schedule_mode=batch.schedule_mode,
                    status=TargetStatus.queued_local if ready else TargetStatus.waiting_media,
                )
            )
    session.add_all(targets)
    session.commit()
    for t in targets:
        session.refresh(t)
    return targets


RESCHEDULABLE = (TargetStatus.waiting_media, TargetStatus.queued_local, TargetStatus.sent_to_buffer)
CANCELLABLE = (
    TargetStatus.waiting_media,
    TargetStatus.queued_local,
    TargetStatus.sent_to_buffer,
    TargetStatus.failed,
    TargetStatus.manual_required,
)


class RescheduleIn(BaseModel):
    ids: list[str]
    scheduled_at: AwareDatetime


def _target(session: Session, target_id: str) -> PostTarget:
    target = session.get(PostTarget, target_id)
    if target is None:
        raise DomainError("target_not_found", "Post nggak ditemukan.", status_code=404)
    return target


async def reschedule(session: Session, body: RescheduleIn) -> list[PostTarget]:
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
        if t.status is TargetStatus.sent_to_buffer:  # Buffer first, so both stay in step
            await _on_platform(session, t, lambda p, t=t: p.reschedule(t, body.scheduled_at))
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
    if media.status is MediaStatus.deleted:
        raise DomainError(
            "media_deleted",
            "File videonya sudah dihapus otomatis. Buat post baru dengan video ini.",
            status_code=409,
        )
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


async def cancel(session: Session, target_id: str) -> PostTarget:
    target = _target(session, target_id)
    if target.status is TargetStatus.publishing:
        raise DomainError(
            "busy_publishing",
            "Post ini lagi dikirim ke Instagram, jadi nggak bisa dibatalkan sekarang.",
            status_code=409,
        )
    if target.status not in CANCELLABLE:
        raise DomainError("not_cancellable", "Post yang sudah tayang nggak bisa dibatalkan.", 409)
    if target.status is TargetStatus.sent_to_buffer:
        await _on_platform(session, target, lambda p: p.cancel(target))
    target.status = TargetStatus.cancelled
    target.next_attempt_at = None
    session.add(target)
    session.commit()
    return target


def mark_published(session: Session, target_id: str) -> PostTarget:
    """The owner posted a manual_required video by hand."""
    target = _target(session, target_id)
    if target.status is not TargetStatus.manual_required:
        raise DomainError("not_manual", "Cuma post manual yang bisa ditandai sudah diposting.", 409)
    target.sqlmodel_update(
        {"status": TargetStatus.published, "last_error": None, "last_error_human": None}
    )
    session.add(target)
    session.commit()
    return target


async def _on_platform(
    session: Session, target: PostTarget, action: Callable[[Publisher], Awaitable[None]]
) -> None:
    account = session.get_one(Account, target.account_id)
    try:
        await action(get_publisher(account, get_settings()))
    except PublishError as err:
        raise DomainError(err.code, err.human, status_code=502, detail=err.raw) from err
