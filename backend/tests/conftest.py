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

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _set_env(monkeypatch: pytest.MonkeyPatch, db_path: Path, media_dir: Path) -> None:
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STORAGE_BACKEND", "local_public")
    monkeypatch.setenv("MEDIA_DIR", str(media_dir))
    monkeypatch.setenv("PUBLIC_MEDIA_BASE_URL", "http://testserver/m")
    get_settings.cache_clear()
    get_engine.cache_clear()


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
def env(migrated_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    db_path = tmp_path / "schedler.db"
    shutil.copy(migrated_db, db_path)
    _set_env(monkeypatch, db_path, tmp_path / "media")
    engine = get_engine()
    with respx.mock(assert_all_mocked=True, assert_all_called=False):
        yield
    engine.dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.fixture
def session() -> Iterator[Session]:
    with Session(get_engine()) as s:
        yield s


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
