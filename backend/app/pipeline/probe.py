import asyncio
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.errors import DomainError
from app.models import Orientation


@dataclass(frozen=True)
class ProbeResult:
    width: int  # after applying rotation metadata
    height: int
    duration_s: float
    vcodec: str
    pix_fmt: str
    acodec: str | None
    faststart: bool

    @property
    def orientation(self) -> Orientation:
        return classify(self.width, self.height)


def classify(width: int, height: int) -> Orientation:
    ratio = width / height
    if ratio < 0.9:
        return Orientation.vertical
    if ratio > 1.1:
        return Orientation.horizontal
    return Orientation.square


def has_faststart(path: Path) -> bool:
    """True if the top-level `moov` atom comes before `mdat` (playable while downloading)."""
    with path.open("rb") as f:
        while header := f.read(8):
            if len(header) < 8:
                return False
            size, kind = struct.unpack(">I4s", header)
            if kind == b"moov":
                return True
            if kind == b"mdat" or size == 0:
                return False
            if size == 1:  # 64-bit size follows the header
                size = struct.unpack(">Q", f.read(8))[0] - 8
            f.seek(size - 8, 1)
    return False


def _rotation(stream: dict[str, Any]) -> int:
    for side in stream.get("side_data_list", []):
        if "rotation" in side:
            return int(side["rotation"])
    return int(stream.get("tags", {}).get("rotate", 0))


def parse_ffprobe(data: dict[str, Any], faststart: bool) -> ProbeResult:
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise DomainError("no_video_stream", "File ini nggak berisi video.", status_code=422)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    width, height = int(video["width"]), int(video["height"])
    if abs(_rotation(video)) % 180 == 90:
        width, height = height, width
    return ProbeResult(
        width=width,
        height=height,
        duration_s=float(data["format"]["duration"]),
        vcodec=video["codec_name"],
        pix_fmt=video.get("pix_fmt", ""),
        acodec=audio["codec_name"] if audio else None,
        faststart=faststart,
    )


async def probe(path: Path) -> ProbeResult:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )  # fmt: skip
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise DomainError(
            "probe_failed",
            "File videonya rusak atau formatnya nggak dikenali. Coba file lain.",
            status_code=422,
            detail={"raw": err.decode(errors="replace")[-2000:]},
        )
    return parse_ffprobe(json.loads(out), await asyncio.to_thread(has_faststart, path))
