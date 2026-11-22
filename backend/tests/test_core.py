from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import REPO_ROOT, Settings
from app.models import PostTarget
from tests.factories import make_account, make_media, make_target


def test_health(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_sqlite_pragmas(session: Session) -> None:
    conn = session.connection()
    assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
    assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
    assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_datetimes_round_trip_as_aware_utc(session: Session) -> None:
    wib = timezone(timedelta(hours=7))
    target = make_target(
        session,
        make_media(session),
        make_account(session),
        scheduled_at=datetime(2026, 11, 24, 19, 0, tzinfo=wib),
    )
    session.expire_all()
    loaded = session.exec(select(PostTarget).where(PostTarget.id == target.id)).one()
    assert loaded.scheduled_at == datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    assert loaded.scheduled_at.tzinfo is UTC
    assert loaded.created_at.tzinfo is UTC


def test_naive_datetime_rejected(session: Session) -> None:
    with pytest.raises(Exception, match="Naive datetime"):
        make_target(
            session,
            make_media(session),
            make_account(session),
            scheduled_at=datetime(2026, 11, 24, 12, 0),
        )


def test_ids_are_sortable_ulids(session: Session) -> None:
    a = make_media(session)
    b = make_media(session)
    assert len(a.id) == 26
    assert a.id < b.id


def test_settings_resolve_relative_paths_to_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/schedler.db")
    monkeypatch.setenv("MEDIA_DIR", "./media")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.database_url == f"sqlite:///{REPO_ROOT / 'data/schedler.db'}"
    assert s.media_dir == REPO_ROOT / "media"


def test_settings_fail_fast_on_missing_r2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "r2")
    with pytest.raises(ValidationError, match="R2_ACCOUNT_ID"):
        Settings(_env_file=None)  # type: ignore[call-arg]
