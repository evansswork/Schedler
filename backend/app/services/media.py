"""Media lifecycle: create from link/upload, then download → normalize → store → ready."""

import asyncio
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy import update
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.db import get_engine, utcnow
from app.core.errors import DomainError
from app.models import (
    Account,
    EventLevel,
    MediaAsset,
    MediaSource,
    MediaStatus,
    Platform,
    Post,
    PostTarget,
    TargetStatus,
)
from app.pipeline.download import download_tiktok, validate_tiktok_url
from app.pipeline.normalize import normalize
from app.pipeline.probe import ProbeResult
from app.services.events import log_event
from app.services.notifications import esc, notify
from app.services.routing import youtube_kind
from app.storage import get_storage

logger = logging.getLogger(__name__)

UNEXPECTED_ERROR = "Gagal memproses video karena error tak terduga. Detailnya ada di log server."
_IN_FLIGHT = (MediaStatus.downloading, MediaStatus.processing)


def incoming_dir() -> Path:
    return get_settings().media_dir / "incoming"


def create_from_links(session: Session, urls: list[str]) -> list[MediaAsset]:
    cleaned = list(dict.fromkeys(u.strip() for u in urls if u.strip()))
    if not cleaned:
        raise DomainError("no_links", "Tempel minimal satu link TikTok.", status_code=422)
    invalid = []
    for url in cleaned:
        try:
            validate_tiktok_url(url)
        except DomainError:
            invalid.append(url)
    if invalid:
        raise DomainError(
            "invalid_tiktok_link",
            f"{len(invalid)} link bukan link video TikTok. Cek lagi baris yang ditandai.",
            status_code=422,
            detail={"invalid": invalid},
        )
    media = [MediaAsset(source=MediaSource.tiktok_link, source_url=u) for u in cleaned]
    session.add_all(media)
    session.commit()
    for m in media:
        session.refresh(m)
    return media


def create_from_upload(session: Session, filename: str, data: BinaryIO) -> MediaAsset:
    if not filename.lower().endswith(".mp4"):
        raise DomainError(
            "not_mp4", f"{filename} bukan file MP4. Cuma bisa upload MP4.", status_code=422
        )
    media = MediaAsset(source=MediaSource.upload)
    path = incoming_dir() / f"{media.id}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as out:
        shutil.copyfileobj(data, out)
    media.file_path = str(path)
    session.add(media)
    session.commit()
    session.refresh(media)
    return media


def reset_stuck_media() -> int:
    """After a crash/restart, media left mid-processing goes back to pending."""
    with Session(get_engine()) as s:
        result = s.connection().execute(
            update(MediaAsset)
            .where(col(MediaAsset.status).in_(_IN_FLIGHT))
            .values(status=MediaStatus.pending, progress_pct=0, updated_at=utcnow())
        )
        s.commit()
        return result.rowcount


def claim_next_pending() -> str | None:
    """Atomically move the oldest pending media to its first in-flight status."""
    with Session(get_engine()) as s:
        while True:
            row = s.exec(
                select(MediaAsset.id, MediaAsset.source)
                .where(MediaAsset.status == MediaStatus.pending)
                .order_by(col(MediaAsset.id))
                .limit(1)
            ).first()
            if row is None:
                return None
            media_id, source = row
            first = (
                MediaStatus.downloading
                if source is MediaSource.tiktok_link
                else MediaStatus.processing
            )
            claimed = s.connection().execute(
                update(MediaAsset)
                .where(col(MediaAsset.id) == media_id, MediaAsset.status == MediaStatus.pending)
                .values(status=first, updated_at=utcnow())
            )
            s.commit()
            if claimed.rowcount == 1:
                return media_id


def _update_media(media_id: str, **values: Any) -> None:
    with Session(get_engine()) as s:
        s.connection().execute(
            update(MediaAsset)
            .where(col(MediaAsset.id) == media_id)
            .values(**values, updated_at=utcnow())
        )
        s.commit()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _targets_waiting_for(s: Session, media_id: str) -> list[tuple[PostTarget, Post, Account]]:
    rows = s.exec(
        select(PostTarget, Post, Account)
        .join(Post, col(Post.id) == PostTarget.post_id)
        .join(Account, col(Account.id) == PostTarget.account_id)
        .where(Post.media_id == media_id, PostTarget.status == TargetStatus.waiting_media)
    ).all()
    return list(rows)


def _mark_ready(media_id: str, info: ProbeResult, sha: str, size: int, public_url: str) -> None:
    with Session(get_engine()) as s:
        media = s.get_one(MediaAsset, media_id)
        media.sqlmodel_update(
            {
                "status": MediaStatus.ready,
                "progress_pct": 100,
                "file_path": None,  # the storage backend owns the file now
                "public_url": public_url,
                "width": info.width,
                "height": info.height,
                "duration_s": info.duration_s,
                "orientation": info.orientation,
                "size_bytes": size,
                "sha256": sha,
                "error": None,
            }
        )
        caption = media.source_caption or ""
        for target, post, account in _targets_waiting_for(s, media_id):
            # The owner may have scheduled before the TikTok caption was known.
            if not target.caption:
                target.caption = caption
            if not post.default_caption:
                post.default_caption = caption
            if account.platform is Platform.youtube:
                target.yt_kind = youtube_kind(info.orientation, info.duration_s)
            target.status = TargetStatus.queued_local
        log_event(s, EventLevel.info, "media", media_id, "Media siap", {"public_url": public_url})
        s.commit()


def _mark_failed(media_id: str, err: DomainError) -> None:
    with Session(get_engine()) as s:
        media = s.get_one(MediaAsset, media_id)
        media.status = MediaStatus.failed
        media.error = err.message
        for target, _post, _account in _targets_waiting_for(s, media_id):
            target.status = TargetStatus.failed
            target.last_error = err.code
            target.last_error_human = err.message
        log_event(s, EventLevel.error, "media", media_id, err.code, err.detail)
        source = f"\n{esc(media.source_url)}" if media.source_url else ""
        notify(s, f"❌ Video gagal diproses: {esc(err.message)}{source}")
        s.commit()
    for leftover in incoming_dir().glob(f"{media_id}*"):
        leftover.unlink()


async def process_claimed(media_id: str) -> None:
    with Session(get_engine()) as s:
        media = s.get_one(MediaAsset, media_id)
        source, url, file_path, token = (
            media.source,
            media.source_url,
            media.file_path,
            media.public_token,
        )
    try:
        if source is MediaSource.tiktok_link:
            assert url is not None
            dl = await download_tiktok(
                url,
                incoming_dir() / media_id,
                lambda pct: _update_media(media_id, progress_pct=pct),
            )
            path = dl.path
            _update_media(
                media_id,
                status=MediaStatus.processing,
                progress_pct=100,
                source_caption=dl.caption,
                file_path=str(path),
            )
        else:
            assert file_path is not None
            path = Path(file_path)
        path, info = await normalize(path)
        sha = await asyncio.to_thread(_sha256, path)
        size = path.stat().st_size
        storage = get_storage(get_settings())
        public_url = await asyncio.to_thread(storage.put, path, f"{token}.mp4")
    except DomainError as err:
        _mark_failed(media_id, err)
        return
    except Exception as exc:  # keep the job alive; the media gets a clear failed state
        logger.exception("process_media failed for %s", media_id)
        _mark_failed(
            media_id,
            DomainError("unexpected", UNEXPECTED_ERROR, detail={"raw": repr(exc)}),
        )
        return
    _mark_ready(media_id, info, sha, size, public_url)


async def process_next() -> bool:
    """Process one pending media. Returns False when nothing was pending."""
    media_id = claim_next_pending()
    if media_id is None:
        return False
    await process_claimed(media_id)
    return True
