from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    admin_password_hash: str = ""
    database_url: str = "sqlite:///./data/schedler.db"

    storage_backend: Literal["r2", "local_public"] = "r2"
    media_dir: Path = Path("./media")
    public_media_base_url: str = ""
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_public_base_url: str = ""

    @model_validator(mode="after")
    def _check_and_resolve(self) -> Settings:
        missing = [] if self.secret_key else ["secret_key"]
        if self.storage_backend == "r2":
            missing += [f for f in _R2_FIELDS if not getattr(self, f)]
        elif not self.public_media_base_url:
            missing.append("public_media_base_url")
        if missing:
            names = ", ".join(f.upper() for f in missing)
            raise ValueError(f"Missing required settings in .env: {names}")

        # Relative paths in .env are relative to the repo root, not the process cwd.
        if not self.media_dir.is_absolute():
            self.media_dir = REPO_ROOT / self.media_dir
        prefix = "sqlite:///"
        db_path = Path(self.database_url.removeprefix(prefix))
        if self.database_url.startswith(prefix) and not db_path.is_absolute():
            self.database_url = f"{prefix}{REPO_ROOT / db_path}"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
