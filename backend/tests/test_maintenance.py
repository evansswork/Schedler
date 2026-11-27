import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.models import MediaAsset, MediaStatus, TargetStatus
from app.services import maintenance
from app.services.maintenance import cleanup_media, update_ytdlp
from tests.factories import make_account, make_media, make_target

OLD = timedelta(hours=25)


def stored(session: Session, **kw: Any) -> MediaAsset:
    media = make_media(session, status=MediaStatus.ready, **kw)
    path = get_settings().media_dir / "public" / f"{media.public_token}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"mp4")
    return media


def file_of(media: MediaAsset) -> Path:
    return get_settings().media_dir / "public" / f"{media.public_token}.mp4"


async def test_cleanup_deletes_only_settled_media_after_a_day(session: Session) -> None:
    account = make_account(session)
    now = utcnow()
    done = stored(session)
    make_target(session, done, account, status=TargetStatus.published, updated_at=now - OLD)
    make_target(session, done, account, status=TargetStatus.cancelled, updated_at=now - OLD)
    waiting = stored(session)
    make_target(session, waiting, account, status=TargetStatus.published, updated_at=now - OLD)
    make_target(session, waiting, account, status=TargetStatus.sent_to_buffer)
    manual = stored(session)
    make_target(session, manual, account, status=TargetStatus.manual_required, updated_at=now - OLD)
    recent = stored(session)
    make_target(session, recent, account, status=TargetStatus.published)
    orphan = stored(session, updated_at=now - timedelta(days=4))
    fresh_orphan = stored(session)

    assert await cleanup_media() == 2

    for m in (done, orphan):
        session.refresh(m)
        assert (m.status, m.public_url) == (MediaStatus.deleted, None)
        assert not file_of(m).exists()
    for m in (waiting, manual, recent, fresh_orphan):
        session.refresh(m)
        assert m.status is MediaStatus.ready
        assert file_of(m).exists()


def test_retry_explains_a_deleted_file(auth_client: TestClient, session: Session) -> None:
    media = make_media(session, status=MediaStatus.deleted)
    target = make_target(session, media, make_account(session), status=TargetStatus.failed)
    res = auth_client.post(f"/api/v1/targets/{target.id}/retry")
    assert res.json()["error"]["message"].startswith("File videonya sudah dihapus otomatis")


class FakeProc:
    def __init__(self, code: int) -> None:
        self.returncode = code

    async def communicate(self) -> tuple[bytes, None]:
        return b"pip output", None

    def kill(self) -> None: ...


@pytest.fixture
def pip(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []

    async def fake_exec(*args: str, **_kw: Any) -> FakeProc:
        calls.append(args)
        return FakeProc(getattr(fake_exec, "code", 0))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return calls


async def test_update_when_already_current(
    monkeypatch: pytest.MonkeyPatch, pip: list[tuple[str, ...]]
) -> None:
    monkeypatch.setattr(maintenance, "ytdlp_versions", lambda: ("2026.11.20", "2026.11.20"))
    assert await update_ytdlp() == "Pengunduh sudah versi terbaru (2026.11.20)."
    assert pip[0][1:] == (
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-q",
        "-U",
        "yt-dlp",
    )


async def test_update_locally_waits_for_a_restart(
    monkeypatch: pytest.MonkeyPatch, pip: list[tuple[str, ...]]
) -> None:
    monkeypatch.setattr(maintenance, "ytdlp_versions", lambda: ("2026.11.01", "2026.11.20"))
    killed: list[int] = []
    monkeypatch.setattr(maintenance.os, "kill", lambda pid, sig: killed.append(sig))
    message = await update_ytdlp()
    assert message == "Pengunduh diupdate ke 2026.11.20. Dipakai setelah backend direstart."
    assert killed == []


async def test_update_in_production_restarts_the_server(
    monkeypatch: pytest.MonkeyPatch, pip: list[tuple[str, ...]]
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    monkeypatch.setattr(maintenance, "ytdlp_versions", lambda: ("2026.11.01", "2026.11.20"))
    killed: list[int] = []
    monkeypatch.setattr(maintenance.os, "kill", lambda pid, sig: killed.append(sig))
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "call_later", lambda _d, fn, *a: fn(*a))
    assert (await update_ytdlp()).endswith("Server restart sebentar.")
    assert len(killed) == 1


async def test_update_failure_is_reported(
    monkeypatch: pytest.MonkeyPatch, pip: list[tuple[str, ...]]
) -> None:
    async def failing(*_a: str, **_kw: Any) -> FakeProc:
        return FakeProc(1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", failing)
    with time_machine.travel(utcnow(), tick=False):
        assert await update_ytdlp() == "Update pengunduh gagal. Detailnya ada di log server."
