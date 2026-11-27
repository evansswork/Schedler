import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx
import time_machine
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.crypto import encrypt
from app.core.db import utcnow
from app.models import (
    Account,
    EventLog,
    MediaAsset,
    MediaStatus,
    Platform,
    PostTarget,
    Route,
    TargetStatus,
)
from app.services.publishing import fail_missed_ig, publish_ig_due
from tests.factories import make_account, make_media, make_target
from tests.test_ig_connect import FIXTURES, GRAPH

T = datetime(2026, 11, 24, 12, 30, tzinfo=UTC)  # 19.30 WIB
IG_ID = "17841400000000001"
CONTAINER = f"{GRAPH}/c-1"


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DRY_RUN", "false")
    get_settings.cache_clear()


@pytest.fixture
def ig(session: Session) -> Account:
    return make_account(
        session, ig_user_id=IG_ID, token_enc=encrypt("tok"), token_expires_at=T + timedelta(days=30)
    )


@pytest.fixture
def media(session: Session) -> MediaAsset:
    return make_media(
        session, status=MediaStatus.ready, public_url="https://pub.example.r2.dev/v.mp4"
    )


@pytest.fixture
def target(session: Session, media: MediaAsset, ig: Account) -> PostTarget:
    return make_target(
        session, media, ig, scheduled_at=T, status=TargetStatus.queued_local, caption="Halo"
    )


async def run_at(at: datetime) -> int:
    with time_machine.travel(at, tick=False):
        return await publish_ig_due()


def reload(session: Session, obj: Any) -> Any:
    session.expire_all()
    return session.get_one(type(obj), obj.id)


def mock_container(http: respx.MockRouter) -> respx.Route:
    return http.post(f"{GRAPH}/{IG_ID}/media").respond(json={"id": "c-1"})


def mock_publish(http: respx.MockRouter, used: int = 2) -> respx.Route:
    http.get(f"{GRAPH}/{IG_ID}/content_publishing_limit").respond(
        json={"data": [{"quota_usage": used, "config": {"quota_total": 50}}]}
    )
    http.get(f"{GRAPH}/m-1").respond(json={"permalink": "https://www.instagram.com/reel/abc/"})
    return http.post(f"{GRAPH}/{IG_ID}/media_publish").respond(json={"id": "m-1"})


@pytest.mark.usefixtures("live")
async def test_container_created_5_minutes_early_then_published_on_time(
    http: respx.MockRouter, session: Session, target: PostTarget
) -> None:
    create = mock_container(http)
    status = http.get(CONTAINER).mock(
        side_effect=[
            httpx.Response(200, json={"status_code": "IN_PROGRESS"}),
            httpx.Response(200, json={"status_code": "FINISHED"}),
            httpx.Response(200, json={"status_code": "FINISHED"}),
        ]
    )
    publish = mock_publish(http)

    await run_at(T - timedelta(minutes=6))
    assert create.call_count == 0

    await run_at(T - timedelta(minutes=5))
    assert json.loads(create.calls.last.request.content) == {
        "media_type": "REELS",
        "video_url": "https://pub.example.r2.dev/v.mp4",
        "caption": "Halo",
    }
    t = reload(session, target)
    assert (t.status, t.provider_ref) == (TargetStatus.publishing, "c-1")

    await run_at(T - timedelta(minutes=4))  # IN_PROGRESS
    await run_at(T - timedelta(minutes=3))  # FINISHED but not due yet
    assert publish.call_count == 0

    assert await run_at(T) == 1
    assert json.loads(publish.calls.last.request.content) == {"creation_id": "c-1"}
    t = reload(session, target)
    assert t.status is TargetStatus.published
    assert t.published_url == "https://www.instagram.com/reel/abc/"
    assert status.call_count == 3


@pytest.mark.usefixtures("live")
async def test_already_published_container_is_not_published_twice(
    http: respx.MockRouter, session: Session, target: PostTarget
) -> None:
    target.status, target.provider_ref = TargetStatus.publishing, "c-1"
    session.add(target)
    session.commit()
    http.get(CONTAINER).respond(json={"status_code": "PUBLISHED"})
    publish = mock_publish(http)

    assert await run_at(T + timedelta(minutes=1)) == 1

    assert publish.call_count == 0
    assert reload(session, target).status is TargetStatus.published


@pytest.mark.usefixtures("live")
async def test_failure_retries_3_times_then_fails(
    http: respx.MockRouter, session: Session, target: PostTarget
) -> None:
    create = mock_container(http)
    http.get(CONTAINER).respond(
        json={"status_code": "ERROR", "status": "Error: 2207052 media could not be fetched"}
    )
    now = T - timedelta(minutes=5)

    for attempt, wait in ((1, 2), (2, 5)):
        await run_at(now)  # container
        await run_at(now + timedelta(seconds=30))  # status ERROR
        t = reload(session, target)
        assert (t.status, t.attempts, t.provider_ref) == (TargetStatus.queued_local, attempt, None)
        assert t.next_attempt_at == now + timedelta(seconds=30, minutes=wait)
        assert t.last_error_human.endswith("Dicoba lagi otomatis.")
        await run_at(t.next_attempt_at - timedelta(seconds=1))  # backoff respected
        assert create.call_count == attempt
        now = t.next_attempt_at

    await run_at(now)
    await run_at(now + timedelta(seconds=30))
    t = reload(session, target)
    assert (t.status, t.attempts) == (TargetStatus.failed, 3)
    assert t.last_error_human == (
        "Instagram nggak bisa mengambil file videonya. Cek storage. Sudah dicoba 3x."
    )
    assert session.exec(select(EventLog).where(EventLog.entity_id == target.id)).all()


@pytest.mark.usefixtures("live")
async def test_expired_token_fails_immediately_and_flags_account(
    http: respx.MockRouter, session: Session, target: PostTarget, ig: Account
) -> None:
    http.post(f"{GRAPH}/{IG_ID}/media").respond(400, json=fixture("error_token_expired.json"))

    await run_at(T)

    t = reload(session, target)
    assert (t.status, t.attempts) == (TargetStatus.failed, 0)
    assert t.last_error_human == "Login Instagram kedaluwarsa. Sambungkan ulang akunnya."
    assert reload(session, ig).token_expires_at == T


@pytest.mark.usefixtures("live")
async def test_quota_exhausted_waits_an_hour_without_using_an_attempt(
    http: respx.MockRouter, session: Session, target: PostTarget
) -> None:
    target.status, target.provider_ref = TargetStatus.publishing, "c-1"
    session.add(target)
    session.commit()
    http.get(CONTAINER).respond(json={"status_code": "FINISHED"})
    publish = mock_publish(http, used=50)

    await run_at(T)

    t = reload(session, target)
    assert (t.status, t.attempts, t.provider_ref) == (TargetStatus.publishing, 0, "c-1")
    assert t.next_attempt_at == T + timedelta(hours=1)
    assert publish.call_count == 0


@pytest.mark.usefixtures("live")
async def test_container_stuck_in_progress_times_out(
    http: respx.MockRouter, session: Session, target: PostTarget
) -> None:
    mock_container(http)
    http.get(CONTAINER).respond(json={"status_code": "IN_PROGRESS"})
    await run_at(T - timedelta(minutes=5))

    await run_at(T + timedelta(minutes=9))
    assert reload(session, target).status is TargetStatus.publishing
    await run_at(T + timedelta(minutes=11))
    t = reload(session, target)
    assert (t.status, t.attempts, t.last_error) == (
        TargetStatus.queued_local,
        1,
        "ig_container_timeout",
    )


@pytest.mark.usefixtures("live")
async def test_unconnected_account_fails_with_instructions(
    session: Session, media: MediaAsset
) -> None:
    account = make_account(session, label="IG #2")
    t = make_target(session, media, account, scheduled_at=T, status=TargetStatus.queued_local)

    await run_at(T)

    t = reload(session, t)
    assert t.status is TargetStatus.failed
    assert t.last_error_human == "IG #2 belum tersambung. Tempel token di Akun & slot."
    assert reload(session, account).token_expires_at is None


async def test_dry_run_publishes_at_the_scheduled_time(
    session: Session, target: PostTarget
) -> None:
    await run_at(T - timedelta(minutes=5))
    assert reload(session, target).status is TargetStatus.publishing
    await run_at(T - timedelta(minutes=1))
    assert reload(session, target).status is TargetStatus.publishing
    assert await run_at(T) == 1
    assert reload(session, target).status is TargetStatus.published


async def test_buffer_targets_are_left_alone(session: Session, media: MediaAsset) -> None:
    yt = make_account(session, label="YT #1", platform=Platform.youtube, route=Route.buffer)
    t = make_target(session, media, yt, scheduled_at=T, status=TargetStatus.queued_local)
    await run_at(T)
    assert reload(session, t).status is TargetStatus.queued_local


def test_startup_fails_ig_posts_missed_by_more_than_6_hours(
    session: Session, media: MediaAsset, ig: Account
) -> None:
    yt = make_account(session, label="YT #1", platform=Platform.youtube, route=Route.buffer)
    old = make_target(session, media, ig, scheduled_at=T, status=TargetStatus.queued_local)
    recent = make_target(
        session, media, ig, scheduled_at=T + timedelta(hours=2), status=TargetStatus.queued_local
    )
    buffered = make_target(session, media, yt, scheduled_at=T, status=TargetStatus.queued_local)

    with time_machine.travel(T + timedelta(hours=7), tick=False):
        assert fail_missed_ig() == 1

    o = reload(session, old)
    assert (o.status, o.last_error_human) == (
        TargetStatus.failed,
        "Terlewat karena server mati. Jadwalkan ulang?",
    )
    assert reload(session, recent).status is TargetStatus.queued_local
    assert reload(session, buffered).status is TargetStatus.queued_local


# --- target actions (API) ---


def test_reschedule_moves_queued_targets_only(
    auth_client: TestClient, session: Session, media: MediaAsset, ig: Account
) -> None:
    # Real time: the session cookie is signed with the real clock.
    soon = (utcnow() + timedelta(days=1)).replace(microsecond=0)
    a = make_target(session, media, ig, scheduled_at=soon, status=TargetStatus.queued_local)
    b = make_target(session, media, ig, scheduled_at=soon, status=TargetStatus.published)
    new = soon + timedelta(hours=2)

    res = auth_client.patch(
        "/api/v1/targets/reschedule", json={"ids": [a.id], "scheduled_at": new.isoformat()}
    )
    assert res.status_code == 200, res.text
    assert reload(session, a).scheduled_at == new

    res = auth_client.patch(
        "/api/v1/targets/reschedule", json={"ids": [a.id, b.id], "scheduled_at": new.isoformat()}
    )
    assert res.json()["error"]["code"] == "not_reschedulable"
    res = auth_client.patch(
        "/api/v1/targets/reschedule",
        json={"ids": [a.id], "scheduled_at": (utcnow() - timedelta(hours=1)).isoformat()},
    )
    assert res.json()["error"]["code"] == "time_in_past"


def test_retry_resets_a_failed_target(
    auth_client: TestClient, session: Session, media: MediaAsset, ig: Account
) -> None:
    t = make_target(
        session,
        media,
        ig,
        status=TargetStatus.failed,
        attempts=3,
        provider_ref="c-1",
        last_error_human="x",
    )
    res = auth_client.post(f"/api/v1/targets/{t.id}/retry")
    assert res.status_code == 200, res.text
    t = reload(session, t)
    assert (t.status, t.attempts, t.provider_ref, t.last_error_human) == (
        TargetStatus.queued_local,
        0,
        None,
        None,
    )
    assert auth_client.post(f"/api/v1/targets/{t.id}/retry").status_code == 409


def test_retry_refused_when_media_failed(
    auth_client: TestClient, session: Session, ig: Account
) -> None:
    broken = make_media(session, status=MediaStatus.failed)
    t = make_target(session, broken, ig, status=TargetStatus.failed)
    assert auth_client.post(f"/api/v1/targets/{t.id}/retry").json()["error"]["code"] == (
        "media_unusable"
    )


@pytest.mark.parametrize(
    ("status", "ok"),
    [
        (TargetStatus.queued_local, True),
        (TargetStatus.failed, True),
        (TargetStatus.publishing, False),
        (TargetStatus.published, False),
    ],
)
def test_cancel(
    auth_client: TestClient,
    session: Session,
    media: MediaAsset,
    ig: Account,
    status: TargetStatus,
    ok: bool,
) -> None:
    t = make_target(session, media, ig, status=status)
    res = auth_client.post(f"/api/v1/targets/{t.id}/cancel")
    assert (res.status_code == 200) is ok, res.text
    assert reload(session, t).status is (TargetStatus.cancelled if ok else status)


def test_targets_filtered_by_calendar_range(
    auth_client: TestClient, session: Session, media: MediaAsset, ig: Account
) -> None:
    inside = make_target(session, media, ig, scheduled_at=T)
    make_target(session, media, ig, scheduled_at=T + timedelta(days=8))
    res = auth_client.get(
        "/api/v1/targets",
        params={"start": "2026-11-23T17:00:00Z", "end": "2026-11-30T17:00:00Z"},
    )
    assert [t["id"] for t in res.json()] == [inside.id]
