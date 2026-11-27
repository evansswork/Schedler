from datetime import UTC, datetime, timedelta

import time_machine
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.db import utcnow
from app.models import Account, MediaStatus, PostTarget, ScheduleMode, TargetStatus
from app.services.slots import MIN_LEAD, slot_times
from tests.factories import make_account, make_media, make_target

TUESDAY_19_WIB = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


def utc(day: int, hour: int, minute: int = 30) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def test_default_slots_in_wib_order_and_roll_over_to_the_next_day() -> None:
    account = Account(platform="ig", label="IG #1", route="ig_direct")
    got = slot_times(account, TUESDAY_19_WIB, 6, set())
    # 19.30 ... 23.30 WIB on Tuesday = 12:30 ... 16:30 UTC, then Wednesday 19.30 WIB.
    assert got == [utc(24, 12), utc(24, 13), utc(24, 14), utc(24, 15), utc(24, 16), utc(25, 12)]


def test_only_chosen_weekdays_and_taken_slots_are_skipped() -> None:
    account = Account(
        platform="ig", label="IG #1", route="ig_direct", slots=["10:00"], weekdays=[1, 3]
    )
    taken = {datetime(2026, 11, 25, 3, 0, tzinfo=UTC)}  # Wednesday 10.00 WIB
    got = slot_times(account, TUESDAY_19_WIB, 2, taken)
    assert got == [
        datetime(2026, 11, 30, 3, 0, tzinfo=UTC),
        datetime(2026, 12, 2, 3, 0, tzinfo=UTC),
    ]


def test_slot_exactly_at_after_is_not_reused() -> None:
    account = Account(platform="ig", label="IG #1", route="ig_direct", slots=["19:30"])
    assert slot_times(account, utc(24, 12), 1, set()) == [utc(25, 12)]


def test_no_slots_returns_nothing() -> None:
    account = Account(platform="ig", label="IG #1", route="ig_direct", slots=[])
    assert slot_times(account, TUESDAY_19_WIB, 3, set()) == []


def test_batch_in_slot_mode_spreads_each_account_over_its_own_free_slots(
    auth_client: TestClient, session: Session
) -> None:
    ig1 = make_account(session)
    ig2 = make_account(session, label="IG #2", slots=["10:00"])
    media = [make_media(session, status=MediaStatus.ready) for _ in range(3)]
    now = utcnow() + timedelta(days=1)  # after login, so the session cookie stays valid
    after = now + MIN_LEAD
    first_ig1 = slot_times(ig1, after, 1, set())[0]
    make_target(session, media[0], ig1, scheduled_at=first_ig1, status=TargetStatus.queued_local)
    second_ig1 = slot_times(ig1, after, 2, set())[1]
    make_target(session, media[0], ig1, scheduled_at=second_ig1, status=TargetStatus.cancelled)

    with time_machine.travel(now, tick=False):
        res = auth_client.post(
            "/api/v1/posts",
            json={
                "account_ids": [ig1.id, ig2.id],
                "items": [{"media_id": m.id} for m in media],
                "schedule_mode": "slot",
            },
        )

    assert res.status_code == 201, res.text
    by_account: dict[str, list[datetime]] = {}
    for t in session.exec(
        select(PostTarget).where(PostTarget.schedule_mode == ScheduleMode.slot)
    ).all():
        by_account.setdefault(t.account_id, []).append(t.scheduled_at)
    assert sorted(by_account[ig1.id]) == slot_times(ig1, after, 3, {first_ig1})
    assert sorted(by_account[ig2.id]) == slot_times(ig2, after, 3, set())
    assert second_ig1 in by_account[ig1.id]  # a cancelled post frees its slot


def test_batch_in_slot_mode_needs_slots(auth_client: TestClient, session: Session) -> None:
    account = make_account(session, slots=[])
    media = make_media(session, status=MediaStatus.ready)
    res = auth_client.post(
        "/api/v1/posts",
        json={
            "account_ids": [account.id],
            "items": [{"media_id": media.id}],
            "schedule_mode": "slot",
        },
    )
    assert res.status_code == 422
    assert res.json()["error"]["message"] == "Atur slot dulu untuk IG #1 di Akun & slot."


def test_exact_mode_still_needs_a_time(auth_client: TestClient, session: Session) -> None:
    account = make_account(session)
    media = make_media(session, status=MediaStatus.ready)
    res = auth_client.post(
        "/api/v1/posts", json={"account_ids": [account.id], "items": [{"media_id": media.id}]}
    )
    assert res.json()["error"]["code"] == "time_missing"


def test_preview_lists_next_slots_per_account(auth_client: TestClient, session: Session) -> None:
    account = make_account(session)
    res = auth_client.get("/api/v1/slots/preview", params={"account_ids": [account.id], "count": 2})
    assert res.status_code == 200, res.text
    got = [datetime.fromisoformat(t) for t in res.json()[account.id]]
    assert len(got) == 2 and got[0] < got[1]
    assert all(t.astimezone(UTC).minute == 30 for t in got)


def test_platform_overrides_and_youtube_title(auth_client: TestClient, session: Session) -> None:
    from app.models import Platform, Route

    ig = make_account(session)
    yt = make_account(session, label="YT #1", platform=Platform.youtube, route=Route.buffer)
    media = make_media(session, status=MediaStatus.ready, orientation="vertical", duration_s=30)
    res = auth_client.post(
        "/api/v1/posts",
        json={
            "account_ids": [ig.id, yt.id],
            "schedule_mode": "slot",
            "items": [
                {
                    "media_id": media.id,
                    "caption": "Caption umum",
                    "overrides": {"youtube": {"title": "Judul YT", "caption": "Deskripsi YT"}},
                }
            ],
        },
    )
    assert res.status_code == 201, res.text
    by_label = {t["account"]["label"]: t for t in res.json()}
    assert (by_label["IG #1"]["caption"], by_label["IG #1"]["title"]) == ("Caption umum", None)
    assert (by_label["YT #1"]["caption"], by_label["YT #1"]["title"]) == (
        "Deskripsi YT",
        "Judul YT",
    )


def test_instagram_hashtag_limit(auth_client: TestClient, session: Session) -> None:
    ig = make_account(session)
    media = make_media(session, status=MediaStatus.ready)
    tags = " ".join(f"#t{i}" for i in range(31))
    res = auth_client.post(
        "/api/v1/posts",
        json={
            "account_ids": [ig.id],
            "schedule_mode": "slot",
            "items": [
                {"media_id": media.id, "caption": "ok", "overrides": {"ig": {"caption": tags}}}
            ],
        },
    )
    assert res.json()["error"]["message"] == "Caption Instagram maksimal 30 hashtag."
