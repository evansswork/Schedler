import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx
import time_machine
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.db import utcnow
from app.models import (
    Account,
    MediaAsset,
    MediaStatus,
    Platform,
    PostTarget,
    Route,
    TargetStatus,
    YtKind,
)
from app.publishers.buffer_client import ENDPOINT
from app.services.buffer_sync import buffer_refill, buffer_sync
from tests.factories import make_account, make_media, make_target

T = datetime(2026, 12, 1, 12, 30, tzinfo=UTC)


class FakeBuffer:
    """Answers Buffer GraphQL calls by operation and records them."""

    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self.created: list[dict[str, Any]] = []
        self.status = "buffer"
        self.create_error: str | None = None
        self.delete_error: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        query, variables = body["query"], body["variables"]
        if "createPost" in query:
            self.calls["create"] += 1
            if self.create_error:
                return self._data("createPost", {"message": self.create_error})
            self.created.append(variables["input"])
            return self._data("createPost", {"post": {"id": f"bp-{len(self.created)}"}})
        if "deletePost" in query:
            self.calls["delete"] += 1
            extra = {"message": self.delete_error} if self.delete_error else {}
            return self._data("deletePost", {"__typename": "DeletePostSuccess", **extra})
        if "editPost" in query:
            self.calls["edit"] += 1
            return self._data("editPost", {"__typename": "PostActionSuccess"})
        self.calls["get"] += 1
        link = "https://youtube.com/shorts/x" if self.status == "sent" else None
        post = {"id": variables["id"], "status": self.status, "externalLink": link}
        return httpx.Response(200, json={"data": {"post": post}})

    @staticmethod
    def _data(name: str, value: dict[str, Any]) -> httpx.Response:
        return httpx.Response(200, json={"data": {name: value}})


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("BUFFER_API_KEYS", "key-a")
    get_settings.cache_clear()


@pytest.fixture
def buffer(http: respx.MockRouter) -> FakeBuffer:
    fake = FakeBuffer()
    http.post(ENDPOINT).mock(side_effect=fake)
    return fake


@pytest.fixture
def media(session: Session) -> MediaAsset:
    return make_media(session, status=MediaStatus.ready, public_url="https://pub.r2.dev/v.mp4")


def linked(
    session: Session, label: str = "YT #1", platform: Platform = Platform.youtube
) -> Account:
    return make_account(
        session,
        label=label,
        platform=platform,
        route=Route.buffer,
        buffer_channel_id=f"ch-{label}",
        buffer_key_ref="0",
        yt_category_id="28",
    )


def queue(session: Session, media: MediaAsset, account: Account, n: int) -> list[PostTarget]:
    return [
        make_target(
            session,
            media,
            account,
            scheduled_at=T + timedelta(hours=i),
            status=TargetStatus.queued_local,
            caption=f"Video {i}\nbaris dua",
            yt_kind=YtKind.short,
        )
        for i in range(n)
    ]


def statuses(session: Session) -> Counter[TargetStatus]:
    session.expire_all()
    return Counter(t.status for t in session.exec(select(PostTarget)))


async def at(when: datetime, job: Any) -> int:
    with time_machine.travel(when, tick=False):
        return await job()


@pytest.mark.usefixtures("live")
async def test_refill_keeps_10_per_channel_and_tops_up_as_posts_publish(
    session: Session, buffer: FakeBuffer, media: MediaAsset
) -> None:
    yt1 = linked(session)
    queue(session, media, yt1, 15)
    now = T - timedelta(days=1)

    assert await at(now, buffer_refill) == 10
    assert statuses(session) == {TargetStatus.sent_to_buffer: 10, TargetStatus.queued_local: 5}
    first = buffer.created[0]
    assert first["channelId"] == "ch-YT #1"
    assert first["mode"] == "customScheduled" and first["dueAt"] == "2026-12-01T12:30:00.000Z"
    assert first["assets"] == [{"video": {"url": "https://pub.r2.dev/v.mp4"}}]
    assert first["metadata"] == {
        "youtube": {"title": "Video 0", "type": "short", "categoryId": "28"}
    }

    assert await at(now, buffer_refill) == 0  # full: nothing more is sent

    buffer.status = "sent"
    assert await at(T + timedelta(hours=1, minutes=3), buffer_sync) == 2
    assert await at(T + timedelta(hours=1, minutes=3), buffer_refill) == 2
    assert statuses(session) == {
        TargetStatus.published: 2,
        TargetStatus.sent_to_buffer: 10,
        TargetStatus.queued_local: 3,
    }


@pytest.mark.usefixtures("live")
async def test_sync_waits_for_due_time_and_rechecks_every_10_minutes(
    session: Session, buffer: FakeBuffer, media: MediaAsset
) -> None:
    (target,) = queue(session, media, linked(session), 1)
    await at(T - timedelta(hours=1), buffer_refill)

    await at(T + timedelta(minutes=1), buffer_sync)
    assert buffer.calls["get"] == 0  # not due + 2 minutes yet
    await at(T + timedelta(minutes=3), buffer_sync)  # still "buffer"
    await at(T + timedelta(minutes=8), buffer_sync)
    assert buffer.calls["get"] == 1  # next look only after 10 minutes

    buffer.status = "sent"
    assert await at(T + timedelta(minutes=14), buffer_sync) == 1
    session.refresh(target)
    assert target.status is TargetStatus.published
    assert target.published_url == "https://youtube.com/shorts/x"


@pytest.mark.usefixtures("live")
async def test_failed_buffer_post_is_deleted_and_retried_then_fails(
    session: Session, buffer: FakeBuffer, media: MediaAsset
) -> None:
    (target,) = queue(session, media, linked(session), 1)
    buffer.status = "error"
    now = T - timedelta(hours=1)
    for attempt in (1, 2, 3):
        await at(now, buffer_refill)
        now = max(now, T) + timedelta(minutes=3)
        await at(now, buffer_sync)
        session.refresh(target)
        assert target.attempts == attempt
        if target.next_attempt_at:
            now = target.next_attempt_at
    assert target.status is TargetStatus.failed
    assert target.last_error_human == "Buffer gagal memposting video ini. Sudah dicoba 3x."
    assert buffer.calls["delete"] == 3
    # A retry after the slot passed is rescheduled a little into the future.
    assert buffer.created[1]["dueAt"] > "2026-12-01T12:33"


@pytest.mark.usefixtures("live")
async def test_tiktok_that_cannot_be_pulled_becomes_manual(
    session: Session, buffer: FakeBuffer, media: MediaAsset
) -> None:
    (target,) = queue(session, media, linked(session, "TikTok", Platform.tiktok), 1)
    buffer.create_error = "TikTok PULL_FROM_URL requires the media domain to be verified."
    await at(T - timedelta(hours=1), buffer_refill)
    session.refresh(target)
    assert target.status is TargetStatus.manual_required
    assert "Upload manual" in (target.last_error_human or "")
    assert buffer.calls["create"] == 1  # no retries: retrying cannot fix a pull ban


@pytest.mark.usefixtures("live")
async def test_full_channel_waits_30_minutes_without_using_an_attempt(
    session: Session, buffer: FakeBuffer, media: MediaAsset
) -> None:
    (target,) = queue(session, media, linked(session), 1)
    buffer.create_error = "You have reached the maximum number of scheduled posts."
    now = T - timedelta(hours=1)
    await at(now, buffer_refill)
    session.refresh(target)
    assert (target.status, target.attempts) == (TargetStatus.queued_local, 0)
    assert target.next_attempt_at == now + timedelta(minutes=30)


@pytest.mark.usefixtures("live")
async def test_low_api_budget_holds_new_posts(
    session: Session, buffer: FakeBuffer, media: MediaAsset
) -> None:
    from app.publishers.buffer_client import save_rate_limit

    queue(session, media, linked(session), 1)
    save_rate_limit("0", {86_400: {"q": 600, "r": 50, "t": 80_000}})
    assert await buffer_refill() == 0
    assert buffer.calls["create"] == 0


@pytest.mark.usefixtures("live")
async def test_unlinked_account_fails_with_instructions(
    session: Session, media: MediaAsset
) -> None:
    yt = make_account(session, label="YT #2", platform=Platform.youtube, route=Route.buffer)
    (target,) = queue(session, media, yt, 1)
    await at(T - timedelta(hours=1), buffer_refill)
    session.refresh(target)
    assert target.status is TargetStatus.failed
    assert (
        target.last_error_human == "YT #2 belum tersambung ke Buffer. Pilih channel di Akun & slot."
    )


async def test_dry_run_hands_posts_to_the_fake_and_publishes_when_due(
    session: Session, media: MediaAsset
) -> None:
    yt = make_account(session, label="YT #1", platform=Platform.youtube, route=Route.buffer)
    (target,) = queue(session, media, yt, 1)
    await at(T - timedelta(hours=1), buffer_refill)
    session.refresh(target)
    assert target.status is TargetStatus.sent_to_buffer
    assert await at(T + timedelta(minutes=3), buffer_sync) == 1


# --- propagation (API, real clock because of the session cookie) ---


def sent(session: Session, media: MediaAsset, account: Account) -> PostTarget:
    return make_target(
        session,
        media,
        account,
        scheduled_at=utcnow() + timedelta(days=2),
        status=TargetStatus.sent_to_buffer,
        provider_ref="bp-9",
    )


@pytest.mark.usefixtures("live")
def test_reschedule_and_cancel_update_buffer(
    auth_client: TestClient, session: Session, buffer: FakeBuffer, media: MediaAsset
) -> None:
    target = sent(session, media, linked(session))
    new = (utcnow() + timedelta(days=3)).replace(microsecond=0)
    res = auth_client.patch(
        "/api/v1/targets/reschedule", json={"ids": [target.id], "scheduled_at": new.isoformat()}
    )
    assert res.status_code == 200, res.text
    assert buffer.calls["edit"] == 1

    res = auth_client.post(f"/api/v1/targets/{target.id}/cancel")
    assert res.status_code == 200, res.text
    assert buffer.calls["delete"] == 1
    session.refresh(target)
    assert target.status is TargetStatus.cancelled


@pytest.mark.usefixtures("live")
def test_cancel_refused_by_buffer_keeps_the_post(
    auth_client: TestClient, session: Session, buffer: FakeBuffer, media: MediaAsset
) -> None:
    target = sent(session, media, linked(session))
    buffer.delete_error = "This post was already sent"
    res = auth_client.post(f"/api/v1/targets/{target.id}/cancel")
    assert res.status_code == 502
    assert res.json()["error"]["message"] == "Buffer menolak perubahan: This post was already sent"
    session.refresh(target)
    assert target.status is TargetStatus.sent_to_buffer


def test_manual_post_can_be_marked_published(
    auth_client: TestClient, session: Session, media: MediaAsset
) -> None:
    tiktok = make_account(session, label="TikTok", platform=Platform.tiktok, route=Route.buffer)
    target = make_target(session, media, tiktok, status=TargetStatus.manual_required)
    res = auth_client.post(f"/api/v1/targets/{target.id}/mark-published")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "published"
    assert auth_client.post(f"/api/v1/targets/{target.id}/mark-published").status_code == 409


@pytest.mark.usefixtures("live")
def test_payload_per_platform(session: Session, media: MediaAsset) -> None:
    from app.publishers.buffer import BufferPublisher

    settings = get_settings()
    yt = linked(session)
    target = make_target(
        session, media, yt, scheduled_at=T, title="Judul sendiri", yt_kind=YtKind.video
    )
    with time_machine.travel(T - timedelta(days=1), tick=False):
        data = BufferPublisher(yt, settings).payload(target, media)
    assert data["metadata"]["youtube"]["title"] == "Judul sendiri"
    assert data["metadata"]["youtube"]["type"] == "regularVideo"

    tiktok = linked(session, "TikTok", Platform.tiktok)
    with time_machine.travel(T - timedelta(days=1), tick=False):
        data = BufferPublisher(tiktok, settings).payload(target, media)
    assert "metadata" not in data
