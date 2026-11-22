"""Download the owner's own TikTok videos with yt-dlp (see the platform-apis skill)."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yt_dlp
from yt_dlp.utils import DownloadError

from app.core.errors import DomainError

TIKTOK_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}
FORMAT = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b"
PROGRESS_STEP = 5

_PRIVATE = "Videonya private atau sudah dihapus dari TikTok."
_GEO = "Videonya diblokir di negara server. Upload MP4-nya langsung."
_RATE = "TikTok lagi membatasi unduhan. Coba lagi beberapa menit lagi atau upload MP4-nya."
# (substring in the yt-dlp error, code, human message). First match wins, so the geo
# rules must precede "not available" ("Not available in your region").
_ERROR_MAP = [
    ("region", "ytdlp_geo_blocked", _GEO),
    ("country", "ytdlp_geo_blocked", _GEO),
    ("geo", "ytdlp_geo_blocked", _GEO),
    ("429", "ytdlp_rate_limited", _RATE),
    ("private", "ytdlp_private", _PRIVATE),
    ("not available", "ytdlp_private", _PRIVATE),
    ("removed", "ytdlp_private", _PRIVATE),
    ("404", "ytdlp_private", _PRIVATE),
]
_EXTRACTOR_BROKEN = (
    "ytdlp_broken",
    "Pengunduh TikTok lagi bermasalah. Coba lagi nanti atau upload MP4-nya.",
)


@dataclass(frozen=True)
class Downloaded:
    path: Path
    caption: str


def validate_tiktok_url(url: str) -> str:
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in TIKTOK_HOSTS:
        raise DomainError(
            "invalid_tiktok_link",
            "Ini bukan link video TikTok. Contoh: https://www.tiktok.com/@akun/video/123.",
            status_code=422,
            detail={"url": url},
        )
    return url


def map_download_error(message: str) -> DomainError:
    lowered = message.lower()
    code, human = next(((c, h) for s, c, h in _ERROR_MAP if s in lowered), _EXTRACTOR_BROKEN)
    return DomainError(code, human, status_code=422, detail={"raw": message})


def _download_sync(url: str, dest: Path, on_progress: Callable[[int], None]) -> Downloaded:
    last = -PROGRESS_STEP

    def hook(d: dict[str, Any]) -> None:
        nonlocal last
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        if d.get("status") != "downloading" or not total:
            return
        pct = min(99, int(d.get("downloaded_bytes", 0) * 100 / total))
        if pct - last >= PROGRESS_STEP:
            last = pct
            on_progress(pct)

    opts = {
        "format": FORMAT,
        "merge_output_format": "mp4",
        "outtmpl": str(dest.with_suffix(".%(ext)s")),
        "noplaylist": True,
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadError as exc:
        raise map_download_error(str(exc)) from exc
    path = Path(info["requested_downloads"][0]["filepath"])
    return Downloaded(path=path, caption=(info.get("description") or "").strip())


async def download_tiktok(url: str, dest: Path, on_progress: Callable[[int], None]) -> Downloaded:
    """Download `url` to `dest` (extension is set by yt-dlp; usually .mp4)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    return await asyncio.to_thread(_download_sync, validate_tiktok_url(url), dest, on_progress)
