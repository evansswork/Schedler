"""Tiny generated test videos (never real user videos)."""

import subprocess
from pathlib import Path


def make_clip(
    path: Path,
    size: str,
    *,
    pix_fmt: str = "yuv420p",
    faststart: bool = True,
    rotation: int | None = None,
    duration: float = 1,
) -> Path:
    cmd = ["ffmpeg", "-y", "-v", "error"]
    cmd += ["-f", "lavfi", "-i", f"testsrc=size={size}:rate=5:duration={duration}"]
    cmd += ["-f", "lavfi", "-i", f"sine=duration={duration}"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", pix_fmt]
    cmd += ["-c:a", "aac", "-shortest"]
    if faststart:
        cmd += ["-movflags", "+faststart"]
    target = path.with_name(f"raw-{path.name}") if rotation is not None else path
    subprocess.run([*cmd, str(target)], check=True)
    if rotation is not None:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-display_rotation:v:0", str(rotation),
             "-i", str(target), "-c", "copy", "-movflags", "+faststart", str(path)],
            check=True,
        )  # fmt: skip
        target.unlink()
    return path
