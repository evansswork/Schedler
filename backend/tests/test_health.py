from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import get_settings
from app.core.crypto import encrypt
from app.core.db import utcnow
from app.models import MediaStatus, Platform, Route, TargetStatus
from app.publishers.buffer_client import save_rate_limit
from tests.factories import make_account, make_media, make_target


def get(client: TestClient) -> dict:
    res = client.get("/api/v1/health/summary")
    assert res.status_code == 200, res.text
    return res.json()


def test_all_quiet_is_ok(auth_client: TestClient, session: Session) -> None:
    make_account(session)
    body = get(auth_client)
    assert body["status"] == "ok" and body["problems"] == []
    assert body["dry_run"] is True and body["telegram"] is False
    assert body["accounts"][0] == {
        "id": body["accounts"][0]["id"],
        "label": "IG #1",
        "route": "ig_direct",
        "connected": False,
        "used": 0,
        "limit": 50,
        "token_days_left": None,
    }
    assert body["ytdlp"]["running"]


def test_meters_and_problems(auth_client: TestClient, session: Session) -> None:
    now = utcnow()
    ig = make_account(
        session, token_enc=encrypt("t"), token_expires_at=now + timedelta(days=5, hours=1)
    )
    yt = make_account(
        session,
        label="YT #1",
        platform=Platform.youtube,
        route=Route.buffer,
        buffer_channel_id="ch",
    )
    media = make_media(session, status=MediaStatus.ready, size_bytes=1_500_000)
    for _ in range(41):
        make_target(session, media, ig, status=TargetStatus.published)
    for _ in range(3):
        make_target(session, media, yt, status=TargetStatus.sent_to_buffer)
    make_target(session, media, ig, status=TargetStatus.failed)
    make_target(session, media, yt, status=TargetStatus.manual_required)

    body = get(auth_client)

    assert body["status"] == "error"
    assert body["problems"] == [
        "1 post gagal tayang.",
        "Login IG #1 kedaluwarsa 5 hari lagi.",
        "1 post perlu diupload manual.",
        "Kuota IG #1 hari ini hampir habis (41/50).",
    ]
    assert body["notices"] == ["Kuota IG #1 hari ini hampir habis (41/50)."]
    by_label = {a["label"]: a for a in body["accounts"]}
    assert (by_label["IG #1"]["used"], by_label["IG #1"]["token_days_left"]) == (41, 5)
    assert (by_label["YT #1"]["used"], by_label["YT #1"]["limit"]) == (3, 10)
    assert body["storage_bytes"] == 1_500_000


def test_buffer_budget_comes_from_saved_headers(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BUFFER_API_KEYS", "k")
    get_settings.cache_clear()
    save_rate_limit("0", {86_400: {"q": 600, "r": 90, "t": 50_000}})
    body = get(auth_client)
    assert body["buffer_budget"] == {
        "day_left": 90,
        "day_quota": 600,
        "month_left": None,
        "month_quota": None,
    }
    assert body["status"] == "warn"
