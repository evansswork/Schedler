from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    def put(self, local_path: Path, key: str) -> str:
        """Take ownership of `local_path` (it is moved or deleted) and return its public URL."""
        ...

    def delete(self, key: str) -> None: ...
