import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
import respx
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlmodel import Session

from alembic import command
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.security import _login_failures, hash_password
from app.notify import telegram
from app.publishers import buffer_client, ig_client

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_PASSWORD = "correct horse battery"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)
TEST_FERNET_KEY = "x" * 43 + "="  # 32 bytes, url-safe base64


def _set_env(monkeypatch: pytest.MonkeyPatch, db_path: Path, media_dir: Path) -> None:
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")  # tests run jobs explicitly
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("FERNET_KEY", TEST_FERNET_KEY)
    monkeypatch.setenv("IG_GRAPH_VERSION", "v27.0")
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("APP_ENV", "local")
    # Never pick up real credentials from the owner's .env.
    for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "BUFFER_API_KEYS"):
        monkeypatch.setenv(name, "")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", TEST_PASSWORD_HASH)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STORAGE_BACKEND", "local_public")
    monkeypatch.setenv("MEDIA_DIR", str(media_dir))
    monkeypatch.setenv("PUBLIC_MEDIA_BASE_URL", "http://testserver/m")
    get_settings.cache_clear()
    get_engine.cache_clear()


async def _no_sleep(_s: float) -> None:
    return None


@pytest.fixture(scope="session")
def migrated_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run migrations once; each test gets a copy of the result."""
    tmp = tmp_path_factory.mktemp("template")
    db_path = tmp / "template.db"
    with pytest.MonkeyPatch.context() as mp:
        _set_env(mp, db_path, tmp / "media")
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.attributes["configure_logger"] = False
        command.upgrade(cfg, "head")
        get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()
    return db_path


@pytest.fixture(autouse=True)
def env(
    migrated_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[respx.MockRouter]:
    db_path = tmp_path / "schedler.db"
    shutil.copy(migrated_db, db_path)
    _set_env(monkeypatch, db_path, tmp_path / "media")
    engine = get_engine()
    _login_failures.clear()
    monkeypatch.setattr(ig_client, "RETRY_BASE_S", 0)
    monkeypatch.setattr(buffer_client, "_sleep", _no_sleep)
    monkeypatch.setattr(telegram, "sleep", _no_sleep)
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        yield router
    engine.dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.fixture
def http(env: respx.MockRouter) -> respx.MockRouter:
    """Mocks outgoing HTTP; any unmocked request fails the test."""
    return env


@pytest.fixture
def session() -> Iterator[Session]:
    with Session(get_engine()) as s:
        yield s


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    """Logged-in client that sends the CSRF header on every request."""
    res = client.post("/api/v1/auth/login", json={"password": TEST_PASSWORD})
    assert res.status_code == 200, res.text
    client.headers["X-CSRF-Token"] = res.json()["csrf_token"]
    return client
