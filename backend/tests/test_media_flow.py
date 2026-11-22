import asyncio
import shutil
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.cli import seed_accounts
from app.core.config import get_settings
from app.core.errors import DomainError
from app.jobs.process_media import process_media_job
from app.models import (
    EventLog,
    MediaAsset,
    MediaStatus,
    Route,
    TargetStatus,
)
from app.pipeline.download import Downloaded
from app.publishers import get_publisher
from app.publishers.fake import FakePublisher
from app.services import media as media_service
from tests.clips import make_clip
from tests.factories import make_account, make_media, make_target

LINK = "https://www.tiktok.com/@owner/video/7300000000000000001"


@pytest.fixture(scope="module")
def vertical_clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_clip(tmp_path_factory.mktemp("flow") / "v.mp4", "1080x1920")


@pytest.fixture
def fake_download(monkeypatch: pytest.MonkeyPatch, vertical_clip: Path) -> list[str]:
    """Replaces yt-dlp: copies a generated clip and reports progress. Returns called URLs."""
    calls: list[str] = []

    async def _download(url: str, dest: Path, on_progress: Callable[[int], None]) -> Downloaded:
        calls.append(url)
        on_progress(40)
        dest.parent.mkdir(parents=True, exist_ok=True)
        path = Path(shutil.copy(vertical_clip, dest.with_suffix(".mp4")))
        return Downloaded(path=path, caption="Caption dari TikTok #fyp")

    monkeypatch.setattr(media_service, "download_tiktok", _download)
    return calls


def _future(hours: int = 2) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _schedule(client: TestClient, media_ids: list[str], account_ids: list[str]) -> Any:
    items = [
        {"media_id": m, "caption": "", "scheduled_at": _future(i + 1)}
        for i, m in enumerate(media_ids)
    ]
    return client.post("/api/v1/posts", json={"account_ids": account_ids, "items": items})


async def test_links_to_scheduled_end_to_end(
    auth_client: TestClient, session: Session, fake_download: list[str]
) -> None:
    seed_accounts(session)
    accounts = auth_client.get("/api/v1/accounts").json()
    ig = next(a["id"] for a in accounts if a["label"] == "IG #1")
    yt = next(a["id"] for a in accounts if a["label"] == "YT #1")
    links = [LINK, LINK.replace("01", "02"), LINK.replace("01", "03"), LINK]  # last one is a dupe

    res = auth_client.post("/api/v1/media/links", json={"urls": links})
    assert res.status_code == 201
    media_ids = [m["id"] for m in res.json()]
    assert len(media_ids) == 3

    # Scheduling before the download finishes is allowed; targets wait for the media.
    res = _schedule(auth_client, media_ids, [ig, yt])
    assert res.status_code == 201
    assert {t["status"] for t in res.json()} == {"waiting_media"}

    await process_media_job()

    media = auth_client.get("/api/v1/media", params={"ids": media_ids}).json()
    assert [m["status"] for m in media] == ["ready"] * 3
    assert all(m["orientation"] == "vertical" and m["yt_kind"] == "short" for m in media)
    assert media[0]["source_caption"] == "Caption dari TikTok #fyp"
    assert (
        auth_client.get(media[0]["public_url"].removeprefix("http://testserver")).status_code == 200
    )

    targets = auth_client.get("/api/v1/targets", params={"status": "queued_local"}).json()
    assert len(targets) == 6
    assert all(t["caption"] == "Caption dari TikTok #fyp" for t in targets)
    assert {t["yt_kind"] for t in targets if t["account"]["label"] == "YT #1"} == {"short"}
    assert not list((get_settings().media_dir / "incoming").iterdir())


async def test_upload_ready_media_schedules_directly_as_queued(
    auth_client: TestClient, session: Session, vertical_clip: Path
) -> None:
    account = make_account(session)
    with vertical_clip.open("rb") as f:
        res = auth_client.post(
            "/api/v1/media/upload", files=[("files", ("my video.MP4", f, "video/mp4"))]
        )
    assert res.status_code == 201
    media_id = res.json()[0]["id"]
    await process_media_job()
    res = _schedule(auth_client, [media_id], [account.id])
    assert [t["status"] for t in res.json()] == ["queued_local"]


def test_upload_rejects_non_mp4(auth_client: TestClient) -> None:
    res = auth_client.post(
        "/api/v1/media/upload", files=[("files", ("clip.mov", b"x", "video/quicktime"))]
    )
    assert res.status_code == 422
    assert res.json()["error"]["message"] == "clip.mov bukan file MP4. Cuma bisa upload MP4."


def test_links_rejects_non_tiktok_lines(auth_client: TestClient) -> None:
    res = auth_client.post("/api/v1/media/links", json={"urls": [LINK, "https://youtu.be/x"]})
    assert res.status_code == 422
    assert res.json()["error"]["detail"] == {"invalid": ["https://youtu.be/x"]}


async def test_download_failure_marks_media_and_targets_failed(
    monkeypatch: pytest.MonkeyPatch, session: Session
) -> None:
    async def _private(*_: Any) -> Downloaded:
        raise DomainError("ytdlp_private", "Videonya private atau sudah dihapus dari TikTok.")

    monkeypatch.setattr(media_service, "download_tiktok", _private)
    media = make_media(session)
    target = make_target(session, media, make_account(session))
    await process_media_job()

    session.expire_all()
    assert session.get_one(MediaAsset, media.id).status is MediaStatus.failed
    failed = session.get_one(type(target), target.id)
    assert failed.status is TargetStatus.failed
    assert failed.last_error_human == "Videonya private atau sudah dihapus dari TikTok."
    event = session.exec(select(EventLog).where(EventLog.entity_id == media.id)).one()
    assert event.message == "ytdlp_private"


async def test_concurrent_job_runs_process_each_media_once(
    session: Session, fake_download: list[str]
) -> None:
    make_media(session)
    await asyncio.gather(process_media_job(), process_media_job())
    assert fake_download == ["https://www.tiktok.com/@owner/video/1"]


def test_reset_stuck_media_after_restart(session: Session) -> None:
    stuck = make_media(session, status=MediaStatus.downloading, progress_pct=60)
    done = make_media(session, status=MediaStatus.ready)
    assert media_service.reset_stuck_media() == 1
    session.expire_all()
    assert session.get_one(MediaAsset, stuck.id).status is MediaStatus.pending
    assert session.get_one(MediaAsset, done.id).status is MediaStatus.ready


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"account_ids": [], "items": []}, "no_accounts"),
        ({"account_ids": ["ACC"], "items": []}, "no_videos"),
    ],
)
def test_schedule_validation(auth_client: TestClient, payload: dict[str, Any], code: str) -> None:
    res = auth_client.post("/api/v1/posts", json=payload)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == code


def test_schedule_rejects_past_time_and_failed_media(
    auth_client: TestClient, session: Session
) -> None:
    account = make_account(session)
    ready = make_media(session, status=MediaStatus.ready)
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    res = auth_client.post(
        "/api/v1/posts",
        json={"account_ids": [account.id], "items": [{"media_id": ready.id, "scheduled_at": past}]},
    )
    assert res.json()["error"]["code"] == "time_in_past"
    failed = make_media(session, status=MediaStatus.failed)
    res = _schedule(auth_client, [failed.id], [account.id])
    assert res.json()["error"]["code"] == "media_unusable"


async def test_fake_publisher_contract(session: Session) -> None:
    media = make_media(session, status=MediaStatus.ready)
    ig = make_account(session)
    buffer = make_account(session, label="YT #1", route=Route.buffer)
    target = make_target(session, media, ig)
    publisher = get_publisher(ig, get_settings())
    assert isinstance(publisher, FakePublisher)
    assert await publisher.validate(target, media) == []
    assert (await publisher.submit(target, media)).status is TargetStatus.published
    buffered = await get_publisher(buffer, get_settings()).submit(target, media)
    assert buffered.status is TargetStatus.sent_to_buffer
    assert buffered.provider_ref == f"fake-{target.id}"


def test_real_publishing_refused_outside_dry_run(
    monkeypatch: pytest.MonkeyPatch, session: Session
) -> None:
    monkeypatch.setenv("DRY_RUN", "false")
    get_settings.cache_clear()
    with pytest.raises(DomainError) as exc:
        get_publisher(make_account(session), get_settings())
    assert exc.value.code == "route_not_available"
