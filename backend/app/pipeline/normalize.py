"""Make a video platform-safe (H.264/AAC, yuv420p, faststart), re-encoding only when needed."""

import asyncio
from enum import StrEnum
from pathlib import Path

from app.core.errors import DomainError
from app.pipeline.probe import ProbeResult, probe

MAX_LONG_SIDE = 1920
MAX_SHORT_SIDE = 1080
# Cap the short side at 1080 without upscaling or changing the aspect ratio.
SCALE = (
    f"scale='if(gt(iw,ih),-2,min({MAX_SHORT_SIDE},iw))':'if(gt(iw,ih),min({MAX_SHORT_SIDE},ih),-2)'"
)
REENCODE_ARGS = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
    "-vf", SCALE,
    "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
]  # fmt: skip
REMUX_ARGS = ["-c", "copy"]

# The VPS is small: one ffmpeg at a time.
_ffmpeg_slot = asyncio.Semaphore(1)


class Plan(StrEnum):
    none = "none"
    remux = "remux"
    reencode = "reencode"


def plan_for(p: ProbeResult) -> Plan:
    if (
        p.vcodec != "h264"
        or p.pix_fmt != "yuv420p"
        or p.acodec not in (None, "aac")
        or max(p.width, p.height) > MAX_LONG_SIDE
    ):
        return Plan.reencode
    return Plan.none if p.faststart else Plan.remux


async def _ffmpeg(src: Path, dst: Path, args: list[str]) -> None:
    async with _ffmpeg_slot:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-v", "error", "-i", str(src), *args,
            "-movflags", "+faststart", str(dst),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )  # fmt: skip
        _, err = await proc.communicate()
    if proc.returncode != 0:
        dst.unlink(missing_ok=True)
        raise DomainError(
            "normalize_failed",
            "Gagal memproses videonya. Coba upload ulang atau pakai file lain.",
            status_code=422,
            detail={"raw": err.decode(errors="replace")[-2000:]},
        )


async def normalize(src: Path) -> tuple[Path, ProbeResult]:
    """Returns the final file and its probe. The original is deleted only after the
    normalized file probes cleanly."""
    before = await probe(src)
    plan = plan_for(before)
    if plan is Plan.none:
        return src, before
    dst = src.with_name(f"{src.stem}.norm.mp4")
    await _ffmpeg(src, dst, REENCODE_ARGS if plan is Plan.reencode else REMUX_ARGS)
    after = await probe(dst)
    if plan_for(after) is not Plan.none:
        dst.unlink(missing_ok=True)
        raise DomainError(
            "normalize_failed",
            "Gagal memproses videonya. Coba upload ulang atau pakai file lain.",
            status_code=422,
            detail={"plan": plan, "after": str(after)},
        )
    src.unlink()
    return dst, after
