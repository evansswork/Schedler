from app.core.config import Settings
from app.storage.base import StorageBackend
from app.storage.local_public import LocalPublicStorage
from app.storage.r2 import R2Storage


def get_storage(settings: Settings) -> StorageBackend:
    if settings.storage_backend == "r2":
        return R2Storage.from_settings(settings)
    return LocalPublicStorage(settings.media_dir / "public", settings.public_media_base_url)
