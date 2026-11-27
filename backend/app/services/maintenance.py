"""Housekeeping: delete published video files, keep yt-dlp current."""

import asyncio
import logging
import os
import signal
import sqlite3
import sys
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import case
from sqlmodel import Session, col, func, select

from app.core.config import get_settings
from app.core.db import get_engine, utcnow
from app.models import EventLevel, MediaAsset, MediaStatus, Post, PostTarget, Setting, TargetStatus
from app.services.events import log_event
from app.storage import get_storage

logger = logging.getLogger(__name__)

GRACE = timedelta(hours=24)  # keep files a day after the last post settled (PRD NFR-5)
ORPHAN_AFTER = timedelta(days=3)  # downloaded but never scheduled
FINAL = (TargetStatus.published, TargetStatus.failed, TargetStatus.cancelled)
PIP_TIMEOUT_S = 300
YTDLP_KEY = "ytdlp_version"


def _deletable_ids() -> list[str]:
    now = utcnow()
    with Session(get_engine()) as s:
        stats = (
            select(
                Post.media_id,
                func.count().label("total"),
                # Posts not settled yet (CASE, because SUM over a boolean comes back as bool).
                func.sum(case((col(PostTarget.status).in_(FINAL), 0), else_=1)).label("open"),
                func.max(PostTarget.updated_at).label("last"),
            )
            .join(PostTarget, col(PostTarget.post_id) == Post.id)
            .group_by(col(Post.media_id))
            .subquery()
        )
        rows = s.exec(
            select(MediaAsset.id, MediaAsset.updated_at, stats.c.total, stats.c.open, stats.c.last)
            .outerjoin(stats, stats.c.media_id == MediaAsset.id)
            .where(MediaAsset.status == MediaStatus.ready)
        ).all()
    ids = []
    for media_id, updated_at, total, open_, last in rows:
        if not total:
            if updated_at < now - ORPHAN_AFTER:
                ids.append(media_id)
        elif open_ == 0 and last < now - GRACE:
            ids.append(media_id)
    return ids


async def cleanup_media() -> int:
    """Delete files whose posts are all done (live, failed or cancelled) for 24 h.

    Never touches media with a post still waiting, in Buffer, or marked for manual upload."""
    storage = get_storage(get_settings())
    deleted = 0
    for media_id in _deletable_ids():
        with Session(get_engine()) as s:
            media = s.get_one(MediaAsset, media_id)
            key = f"{media.public_token}.mp4"
        try:
            await asyncio.to_thread(storage.delete, key)
        except Exception as exc:  # one broken file must not stop the rest
            logger.warning("cleanup_media: could not delete %s: %r", key, exc)
            continue
        with Session(get_engine()) as s:
            media = s.get_one(MediaAsset, media_id)
            media.status, media.public_url, media.file_path = MediaStatus.deleted, None, None
            s.add(media)
            log_event(s, EventLevel.info, "media", media_id, "File dihapus otomatis")
            s.commit()
        deleted += 1
    if deleted:
        logger.info("cleanup_media: %d files deleted", deleted)
    return deleted


def ytdlp_versions() -> tuple[str, str]:
    """(running, installed). They differ after an update until the next restart."""
    import yt_dlp.version

    return yt_dlp.version.__version__, version("yt-dlp")


async def update_ytdlp() -> str:
    """pip install -U yt-dlp in this environment. Returns a human Indonesian status line."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-q",
        "-U",
        "yt-dlp",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), PIP_TIMEOUT_S)
    except TimeoutError:
        proc.kill()
        return _record("Update pengunduh kelamaan dan dibatalkan. Dicoba lagi besok.", ok=False)
    if proc.returncode != 0:
        logger.warning("update_ytdlp failed: %s", out.decode(errors="replace")[-500:])
        return _record("Update pengunduh gagal. Detailnya ada di log server.", ok=False)
    running, installed = ytdlp_versions()
    if running == installed:
        return _record(f"Pengunduh sudah versi terbaru ({installed}).")
    if get_settings().app_env == "production":
        # The new version loads on restart; Docker restarts the container after a clean exit.
        asyncio.get_running_loop().call_later(5, os.kill, os.getpid(), signal.SIGTERM)
        return _record(f"Pengunduh diupdate ke {installed}. Server restart sebentar.")
    return _record(f"Pengunduh diupdate ke {installed}. Dipakai setelah backend direstart.")


def _record(message: str, ok: bool = True) -> str:
    with Session(get_engine()) as s:
        s.merge(Setting(key=YTDLP_KEY, value=message))
        log_event(s, EventLevel.info if ok else EventLevel.warn, "system", "ytdlp", message)
        s.commit()
    return message


BACKUPS_KEPT = 7
SQLITE = "sqlite:///"


def backup_db() -> Path | None:
    """Online copy of the SQLite DB to data/backups/schedler-YYYY-MM-DD.db; keeps the last 7."""
    url = get_settings().database_url
    if not url.startswith(SQLITE):
        return None
    source = Path(url.removeprefix(SQLITE))
    folder = source.parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    day = utcnow().astimezone(ZoneInfo("Asia/Jakarta")).date().isoformat()
    target = folder / f"schedler-{day}.db"
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)  # consistent copy even while the app is writing
    for old in sorted(folder.glob("schedler-*.db"))[:-BACKUPS_KEPT]:
        old.unlink()
    logger.info("backup_db: %s", target.name)
    return target
