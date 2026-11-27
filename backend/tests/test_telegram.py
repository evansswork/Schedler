import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
import time_machine
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import MediaAsset, MediaStatus, Notification, TargetStatus
from app.services import media as media_service
from app.services.notifications import notify, queue_daily_summary, send_pending
from app.services.publishing import publish_ig_due
from tests.factories import make_account, make_media, make_target

SEND = "https://api.telegram.org/botbot-token/sendMessage"
T = datetime(2026, 11, 24, 12, 30, tzinfo=UTC)  # 19.30 WIB


@pytest.fixture
def telegram_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    get_settings.cache_clear()


def outbox(session: Session, sent: bool = False) -> list[str]:
    session.expire_all()
    cond = col(Notification.sent_at).is_not(None) if sent else col(Notification.sent_at).is_(None)
    rows = session.exec(select(Notification).where(cond).order_by(col(Notification.id)))
    return [n.text for n in rows]


def queue(session: Session, *texts: str) -> None:
    for t in texts:
        notify(session, t)
    session.commit()


@pytest.fixture
def media(session: Session) -> MediaAsset:
    return make_media(session, status=MediaStatus.ready, public_url="https://x/v.mp4")


async def test_published_post_queues_a_message(session: Session, media: MediaAsset) -> None:
    make_target(
        session,
        media,
        make_account(session),
        scheduled_at=T,
        status=TargetStatus.queued_local,
        caption="Resep <sambal> matah 5 menit, pedas mantap sekali",
    )
    with time_machine.travel(T - timedelta(minutes=5), tick=False):
        await publish_ig_due()
    with time_machine.travel(T, tick=False):
        await publish_ig_due()
    assert outbox(session) == [
        "✅ <b>IG #1</b> tayang 19.30 WIB\nResep &lt;sambal&gt; matah 5 menit…"
    ]


async def test_final_failure_queues_a_message_with_a_link(
    monkeypatch: pytest.MonkeyPatch, session: Session, media: MediaAsset
) -> None:
    monkeypatch.setenv("DRY_RUN", "false")
    get_settings.cache_clear()
    make_target(
        session, media, make_account(session, label="IG #2"), status=TargetStatus.queued_local
    )
    await publish_ig_due()  # not connected → fails at once
    assert outbox(session) == [
        "❌ <b>IG #2</b> gagal: IG #2 belum tersambung. Tempel token di Akun &amp; slot.\n"
        "Buka: http://localhost:8000/#/perhatian"
    ]


def test_failed_media_queues_a_message(session: Session) -> None:
    m = make_media(session, status=MediaStatus.downloading)
    media_service._mark_failed(m.id, DomainError("private", "Videonya private."))
    assert outbox(session) == [
        "❌ Video gagal diproses: Videonya private.\nhttps://www.tiktok.com/@owner/video/1"
    ]


async def test_nothing_is_sent_without_telegram_config(session: Session) -> None:
    queue(session, "halo")
    assert await send_pending() == 0
    assert outbox(session) == ["halo"]


@pytest.mark.usefixtures("telegram_on")
async def test_sends_each_message_as_html(session: Session, http: respx.MockRouter) -> None:
    route = http.post(SEND).respond(json={"ok": True})
    queue(session, "satu", "dua")
    assert await send_pending() == 2
    assert [json.loads(c.request.content)["text"] for c in route.calls] == ["satu", "dua"]
    body = json.loads(route.calls[0].request.content)
    assert body["chat_id"] == "42" and body["parse_mode"] == "HTML"
    assert outbox(session) == [] and outbox(session, sent=True) == ["satu", "dua"]


@pytest.mark.usefixtures("telegram_on")
async def test_more_than_5_waiting_become_one_message(
    session: Session, http: respx.MockRouter
) -> None:
    route = http.post(SEND).respond(json={"ok": True})
    queue(session, *[f"pesan {i}" for i in range(7)])
    assert await send_pending() == 7
    assert route.call_count == 1
    text = json.loads(route.calls[0].request.content)["text"]
    assert text.startswith("🗂 7 kabar terbaru\n\npesan 0") and text.endswith("pesan 6")


@pytest.mark.usefixtures("telegram_on")
async def test_failed_send_keeps_messages_for_later(
    session: Session, http: respx.MockRouter
) -> None:
    http.post(SEND).respond(400, json={"ok": False, "description": "Bad Request: chat not found"})
    queue(session, "satu")
    assert await send_pending() == 0
    assert outbox(session) == ["satu"]


@pytest.mark.usefixtures("telegram_on")
async def test_rate_limited_send_waits_and_retries(
    session: Session, http: respx.MockRouter
) -> None:
    route = http.post(SEND).mock(
        side_effect=[
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 3}}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    queue(session, "satu")
    assert await send_pending() == 1
    assert route.call_count == 2


def test_daily_summary_counts_the_wib_day(session: Session, media: MediaAsset) -> None:
    account = make_account(session)
    for at, status in [
        (T, TargetStatus.published),  # 24 Nov 19.30 WIB
        (T + timedelta(hours=1), TargetStatus.failed),
        (T - timedelta(hours=20), TargetStatus.published),  # 23 Nov 23.30 WIB: yesterday
        (T + timedelta(days=1), TargetStatus.queued_local),
        (T + timedelta(days=1, hours=1), TargetStatus.sent_to_buffer),
    ]:
        make_target(session, media, account, scheduled_at=at, status=status)
    with time_machine.travel(datetime(2026, 11, 24, 16, 59, tzinfo=UTC), tick=False):
        text = queue_daily_summary()
    assert text == (
        "📊 Ringkasan 24/11\nTayang: 1 · Gagal: 1\nBesok terjadwal: 2\n"
        "Buka: http://localhost:8000/#/perhatian"
    )
    assert outbox(session) == [text]


def test_test_message_endpoint(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch, http: respx.MockRouter
) -> None:
    res = auth_client.post("/api/v1/settings/telegram/test")
    assert res.status_code == 409
    assert "TELEGRAM_BOT_TOKEN" in res.json()["error"]["message"]

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    get_settings.cache_clear()
    http.post(SEND).mock(
        side_effect=[
            httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    res = auth_client.post("/api/v1/settings/telegram/test")
    assert res.status_code == 502
    assert res.json()["error"]["message"].startswith("Chat Telegram nggak ditemukan")
    assert auth_client.post("/api/v1/settings/telegram/test").status_code == 204


async def test_token_that_could_not_be_refreshed_is_reminded(
    session: Session, http: respx.MockRouter
) -> None:
    from app.core.crypto import encrypt
    from app.services.accounts import refresh_expiring_tokens

    make_account(
        session, ig_user_id="1", token_enc=encrypt("t"), token_expires_at=T + timedelta(days=3)
    )
    http.get("https://graph.instagram.com/refresh_access_token").respond(500)
    with time_machine.travel(T, tick=False):
        assert await refresh_expiring_tokens() == 0
    assert outbox(session) == [
        "🔑 Login IG #1 kedaluwarsa 3 hari lagi. Sambungkan ulang di Akun &amp; slot: "
        "http://localhost:8000/#/akun"
    ]
