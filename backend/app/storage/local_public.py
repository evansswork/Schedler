import shutil
from pathlib import Path


class LocalPublicStorage:
    """Files in `public_dir` are served at `base_url` (FastAPI /m in dev, Caddy on the VPS)."""

    def __init__(self, public_dir: Path, base_url: str) -> None:
        self.public_dir = public_dir
        self.base_url = base_url.rstrip("/")

    def put(self, local_path: Path, key: str) -> str:
        self.public_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(local_path, self.public_dir / key)
        return f"{self.base_url}/{key}"

    def delete(self, key: str) -> None:
        (self.public_dir / key).unlink(missing_ok=True)
