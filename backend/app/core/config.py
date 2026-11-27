from functools import lru_cache
from pathlib import Path
from typing import Literal

from cryptography.fernet import Fernet
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

_R2_FIELDS = (
    "r2_account_id",
    "r2_access_key_id",
    "r2_secret_access_key",
    "r2_bucket",
    "r2_public_base_url",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_env: Literal["local", "production"] = "local"
    dry_run: bool = True
    app_base_url: str = "http://localhost:8000"
    tz_default: str = "Asia/Jakarta"
    secret_key: str = ""
    fernet_key: str = ""
    admin_password_hash: str = ""
    database_url: str = "sqlite:///./data/schedler.db"
    scheduler_enabled: bool = True

    storage_backend: Literal["r2", "local_public"] = "r2"
    media_dir: Path = Path("./media")
    static_dir: Path = Path("./frontend/dist")  # built SPA; served at / when it exists
    public_media_base_url: str = ""
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_public_base_url: str = ""

    # Platform limits change; verify against current docs (video-pipeline skill).
    ig_reels_max_seconds: int = 900
    tiktok_max_seconds: int = 600

    ig_graph_version: str = "v27.0"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    buffer_api_keys: str = ""  # comma-separated, one per legitimately owned Buffer organization

    @property
    def buffer_keys(self) -> list[str]:
        return [k.strip() for k in self.buffer_api_keys.split(",") if k.strip()]

    @model_validator(mode="after")
    def _check_and_resolve(self) -> Settings:
        missing = [f for f in ("secret_key", "fernet_key") if not getattr(self, f)]
        if self.storage_backend == "r2":
            missing += [f for f in _R2_FIELDS if not getattr(self, f)]
        elif not self.public_media_base_url:
            missing.append("public_media_base_url")
        if missing:
            names = ", ".join(f.upper() for f in missing)
            raise ValueError(f"Missing required settings in .env: {names}")
        try:
            Fernet(self.fernet_key)
        except ValueError as exc:
            raise ValueError("FERNET_KEY in .env is not a valid Fernet key") from exc

        # Relative paths in .env are relative to the repo root, not the process cwd.
        if not self.media_dir.is_absolute():
            self.media_dir = REPO_ROOT / self.media_dir
        if not self.static_dir.is_absolute():
            self.static_dir = REPO_ROOT / self.static_dir
        prefix = "sqlite:///"
        db_path = Path(self.database_url.removeprefix(prefix))
        if self.database_url.startswith(prefix) and not db_path.is_absolute():
            self.database_url = f"{prefix}{REPO_ROOT / db_path}"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
