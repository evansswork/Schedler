"""Per-platform routing rules by orientation and duration (see the video-pipeline skill)."""

from app.core.config import get_settings
from app.models import Orientation, Platform, YtKind

YT_SHORT_MAX_S = 180


def youtube_kind(orientation: Orientation, duration_s: float) -> YtKind:
    if orientation is not Orientation.horizontal and duration_s <= YT_SHORT_MAX_S:
        return YtKind.short
    return YtKind.video


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:.0f} menit" if seconds >= 60 else f"{seconds:.0f} detik"


def warnings_for(platform: Platform, orientation: Orientation, duration_s: float) -> list[str]:
    settings = get_settings()
    warnings: list[str] = []
    if platform is Platform.ig:
        if orientation is Orientation.horizontal:
            warnings.append("Video horizontal akan tampil dengan bar hitam di Reels.")
        if duration_s > settings.ig_reels_max_seconds:
            limit = _minutes(settings.ig_reels_max_seconds)
            warnings.append(f"Durasi {_minutes(duration_s)} melebihi batas Reels ({limit}).")
    elif platform is Platform.tiktok:
        if orientation is Orientation.horizontal:
            warnings.append("Video horizontal akan tampil kecil di TikTok.")
        if duration_s > settings.tiktok_max_seconds:
            limit = _minutes(settings.tiktok_max_seconds)
            warnings.append(f"Durasi {_minutes(duration_s)} melebihi batas TikTok ({limit}).")
    return warnings
