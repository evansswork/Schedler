import shutil
from pathlib import Path
from typing import Any

import pytest
from yt_dlp.utils import DownloadError

from app.core.errors import DomainError
from app.models import Orientation, Platform, YtKind
from app.pipeline import download
from app.pipeline.normalize import Plan, normalize, plan_for
from app.pipeline.probe import classify, probe
from app.services.routing import warnings_for, youtube_kind
from tests.clips import make_clip


@pytest.fixture(scope="session")
def clips(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    d = tmp_path_factory.mktemp("clips")
    return {
        "vertical": make_clip(d / "vertical.mp4", "1080x1920"),
        "horizontal": make_clip(d / "horizontal.mp4", "1920x1080"),
        "square": make_clip(d / "square.mp4", "1080x1080"),
        "rotated": make_clip(d / "rotated.mp4", "1920x1080", rotation=90),
        "no_faststart": make_clip(d / "no_faststart.mp4", "1080x1920", faststart=False),
        "yuv444": make_clip(d / "yuv444.mp4", "1080x1920", pix_fmt="yuv444p"),
        "big_horizontal": make_clip(d / "big.mp4", "2560x1440"),
    }


def _copy(src: Path, tmp_path: Path) -> Path:
    return Path(shutil.copy(src, tmp_path / src.name))


@pytest.mark.parametrize(
    ("w", "h", "expected"),
    [
        (1080, 1920, Orientation.vertical),
        (1920, 1080, Orientation.horizontal),
        (1080, 1080, Orientation.square),
        (1000, 1100, Orientation.square),  # 0.909 is inside the square band
        (890, 1000, Orientation.vertical),
        (1110, 1000, Orientation.horizontal),
    ],
)
def test_classify(w: int, h: int, expected: Orientation) -> None:
    assert classify(w, h) is expected


@pytest.mark.parametrize(
    ("name", "orientation"),
    [
        ("vertical", Orientation.vertical),
        ("horizontal", Orientation.horizontal),
        ("square", Orientation.square),
        ("rotated", Orientation.vertical),  # 1920x1080 stored, rotated 90 degrees
    ],
)
async def test_probe_orientation(
    clips: dict[str, Path], name: str, orientation: Orientation
) -> None:
    result = await probe(clips[name])
    assert result.orientation is orientation
    assert result.vcodec == "h264"
    assert result.acodec == "aac"
    assert result.duration_s == pytest.approx(1, abs=0.2)


async def test_probe_rejects_non_video(tmp_path: Path) -> None:
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(DomainError) as exc:
        await probe(bad)
    assert exc.value.code == "probe_failed"


@pytest.mark.parametrize(
    ("name", "plan"),
    [
        ("vertical", Plan.none),
        ("no_faststart", Plan.remux),
        ("yuv444", Plan.reencode),
        ("big_horizontal", Plan.reencode),
    ],
)
async def test_normalize_plan(clips: dict[str, Path], name: str, plan: Plan) -> None:
    assert plan_for(await probe(clips[name])) is plan


async def test_normalize_keeps_ready_file_untouched(clips: dict[str, Path], tmp_path: Path) -> None:
    src = _copy(clips["vertical"], tmp_path)
    out, result = await normalize(src)
    assert out == src
    assert (result.width, result.height) == (1080, 1920)


async def test_normalize_remuxes_missing_faststart(clips: dict[str, Path], tmp_path: Path) -> None:
    src = _copy(clips["no_faststart"], tmp_path)
    _, result = await normalize(src)
    assert result.faststart
    assert not src.exists()  # original removed after the result probed cleanly


async def test_normalize_reencodes_without_changing_aspect(
    clips: dict[str, Path], tmp_path: Path
) -> None:
    _, result = await normalize(_copy(clips["big_horizontal"], tmp_path))
    assert (result.width, result.height) == (1920, 1080)
    assert result.pix_fmt == "yuv420p"
    assert plan_for(result) is Plan.none
    _, yuv = await normalize(_copy(clips["yuv444"], tmp_path))
    assert (yuv.width, yuv.height) == (1080, 1920)  # never upscaled or cropped


@pytest.mark.parametrize(
    ("orientation", "duration", "kind"),
    [
        (Orientation.vertical, 59, YtKind.short),
        (Orientation.square, 180, YtKind.short),
        (Orientation.vertical, 181, YtKind.video),
        (Orientation.horizontal, 30, YtKind.video),
    ],
)
def test_youtube_kind(orientation: Orientation, duration: float, kind: YtKind) -> None:
    assert youtube_kind(orientation, duration) is kind


def test_platform_warnings() -> None:
    assert warnings_for(Platform.ig, Orientation.vertical, 30) == []
    assert warnings_for(Platform.ig, Orientation.horizontal, 30) == [
        "Video horizontal akan tampil dengan bar hitam di Reels."
    ]
    assert warnings_for(Platform.tiktok, Orientation.vertical, 700) == [
        "Durasi 12 menit melebihi batas TikTok (10 menit)."
    ]
    assert warnings_for(Platform.youtube, Orientation.horizontal, 7200) == []


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/video/1",
        "ftp://www.tiktok.com/x",
        "tiktok.com/@a/video/1",
        "https://www.tiktok.com.evil.io/x",
    ],
)
def test_rejects_non_tiktok_links(url: str) -> None:
    with pytest.raises(DomainError) as exc:
        download.validate_tiktok_url(url)
    assert exc.value.code == "invalid_tiktok_link"


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("ERROR: [TikTok] 123: This video is private", "ytdlp_private"),
        ("ERROR: [TikTok] 123: Video not available, status code 10204", "ytdlp_private"),
        ("ERROR: [TikTok] 123: Not available in your region", "ytdlp_geo_blocked"),
        ("ERROR: HTTP Error 429: Too Many Requests", "ytdlp_rate_limited"),
        ("ERROR: [TikTok] 123: Unable to extract universal data", "ytdlp_broken"),
    ],
)
def test_download_error_mapping(raw: str, code: str) -> None:
    err = download.map_download_error(raw)
    assert err.code == code
    assert err.detail["raw"] == raw


class _FakeYDL:
    """Stands in for yt_dlp.YoutubeDL: no network."""

    error: str | None = None

    def __init__(self, opts: dict[str, Any]) -> None:
        self.opts = opts

    def __enter__(self) -> _FakeYDL:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def extract_info(self, url: str, download: bool) -> dict[str, Any]:
        if self.error:
            raise DownloadError(self.error)
        out = Path(self.opts["outtmpl"].replace("%(ext)s", "mp4"))
        for done in (0, 30, 31, 100):
            for hook in self.opts["progress_hooks"]:
                hook({"status": "downloading", "downloaded_bytes": done, "total_bytes": 100})
        out.write_bytes(b"video")
        return {"description": "  caption #fyp  ", "requested_downloads": [{"filepath": str(out)}]}


async def test_download_reports_throttled_progress_and_caption(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(download.yt_dlp, "YoutubeDL", _FakeYDL)
    seen: list[int] = []
    result = await download.download_tiktok(
        "https://www.tiktok.com/@owner/video/1", tmp_path / "abc", seen.append
    )
    assert result.path == tmp_path / "abc.mp4"
    assert result.caption == "caption #fyp"
    assert seen == [0, 30, 99]


async def test_download_failure_maps_to_human_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(_FakeYDL, "error", "ERROR: [TikTok] 1: This video is private")
    monkeypatch.setattr(download.yt_dlp, "YoutubeDL", _FakeYDL)
    with pytest.raises(DomainError) as exc:
        await download.download_tiktok("https://vm.tiktok.com/ZS123/", tmp_path / "x", print)
    assert exc.value.message == "Videonya private atau sudah dihapus dari TikTok."
