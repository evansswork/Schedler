import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
import time_machine
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.crypto import decrypt
from app.models import Account, EventLog, Platform, Route
from app.publishers.ig_client import IgClient, IgError, IgErrorKind, map_error
from app.services.accounts import refresh_expiring_tokens
from tests.factories import make_account

FIXTURES = Path(__file__).parent / "fixtures" / "ig"
GRAPH = "https://graph.instagram.com/v27.0"
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def test_connect_stores_encrypted_token_and_account_id(
    http: respx.MockRouter, auth_client: TestClient, session: Session
) -> None:
    account = make_account(session)
    route = http.get(f"{GRAPH}/me").respond(json=fixture("me.json"))

    res = auth_client.put(f"/api/v1/accounts/{account.id}/ig-token", json={"token": " IGAA-tok "})

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["connected"] is True and body["handle"] == "owner.ig"
    assert "token_enc" not in body
    assert route.calls.last.request.headers["authorization"] == "Bearer IGAA-tok"
    session.refresh(account)
    assert account.ig_user_id == "17841400000000001"
    assert account.token_enc and "IGAA" not in account.token_enc
    assert decrypt(account.token_enc) == "IGAA-tok"


def test_connect_rejected_token_gives_human_message(
    http: respx.MockRouter, auth_client: TestClient, session: Session
) -> None:
    account = make_account(session)
    http.get(f"{GRAPH}/me").respond(400, json=fixture("error_token_expired.json"))

    res = auth_client.put(f"/api/v1/accounts/{account.id}/ig-token", json={"token": "bad"})

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "ig_token_rejected"
    assert "Meta App Dashboard" in res.json()["error"]["message"]
    session.refresh(account)
    assert account.token_enc is None
    assert session.exec(select(EventLog).where(EventLog.entity_id == account.id)).first()


def test_connect_same_ig_account_twice_is_refused(
    http: respx.MockRouter, auth_client: TestClient, session: Session
) -> None:
    make_account(session, label="IG #1", ig_user_id="17841400000000001")
    second = make_account(session, label="IG #2")
    http.get(f"{GRAPH}/me").respond(json=fixture("me.json"))

    res = auth_client.put(f"/api/v1/accounts/{second.id}/ig-token", json={"token": "t"})

    assert res.status_code == 409
    assert res.json()["error"]["message"] == "Akun @owner.ig sudah tersambung ke IG #1."


def test_connect_non_instagram_account_refused(auth_client: TestClient, session: Session) -> None:
    yt = make_account(session, label="YT #1", platform=Platform.youtube, route=Route.buffer)
    res = auth_client.put(f"/api/v1/accounts/{yt.id}/ig-token", json={"token": "t"})
    assert res.status_code == 422


def test_patch_slots_sorts_and_dedupes(auth_client: TestClient, session: Session) -> None:
    account = make_account(session)
    res = auth_client.patch(
        f"/api/v1/accounts/{account.id}",
        json={"slots": ["21:30", "09:00", "21:30"], "weekdays": [7, 1, 1]},
    )
    assert res.status_code == 200, res.text
    assert res.json()["slots"] == ["09:00", "21:30"]
    assert res.json()["weekdays"] == [1, 7]


@pytest.mark.parametrize("slot", ["9:00", "24:00", "19:60", "abc"])
def test_patch_slots_rejects_bad_times(
    auth_client: TestClient, session: Session, slot: str
) -> None:
    account = make_account(session)
    res = auth_client.patch(
        f"/api/v1/accounts/{account.id}", json={"slots": [slot], "weekdays": [1]}
    )
    assert res.status_code == 422
    assert res.json()["error"]["message"].startswith("Jam slot")


def test_new_accounts_get_default_slots(session: Session) -> None:
    assert make_account(session).slots == ["19:30", "20:30", "21:30", "22:30", "23:30"]


def _connected(session: Session, expires_at: datetime, label: str = "IG #1") -> Account:
    from app.core.crypto import encrypt

    return make_account(
        session,
        label=label,
        ig_user_id=f"id-{label}",
        token_enc=encrypt(f"old-{label}"),
        token_expires_at=expires_at,
    )


@time_machine.travel(NOW, tick=False)
async def test_refresh_only_tokens_expiring_within_15_days(
    http: respx.MockRouter, session: Session
) -> None:
    soon = _connected(session, NOW + timedelta(days=10), "IG #1")
    later = _connected(session, NOW + timedelta(days=40), "IG #2")
    expired = _connected(session, NOW - timedelta(days=1), "IG #3")
    route = http.get("https://graph.instagram.com/refresh_access_token").respond(
        json=fixture("refresh.json")
    )

    assert await refresh_expiring_tokens() == 1

    assert route.call_count == 1
    assert route.calls.last.request.url.params["access_token"] == "old-IG #1"
    for a in (soon, later, expired):
        session.refresh(a)
    assert soon.token_enc and decrypt(soon.token_enc) == "IGAA-refreshed-token"
    assert soon.token_expires_at == NOW + timedelta(seconds=5183944)
    assert later.token_expires_at == NOW + timedelta(days=40)
    assert expired.token_expires_at == NOW - timedelta(days=1)


@time_machine.travel(NOW, tick=False)
async def test_refresh_with_dead_token_marks_it_expired_and_logs(
    http: respx.MockRouter, session: Session
) -> None:
    account = _connected(session, NOW + timedelta(days=3))
    http.get("https://graph.instagram.com/refresh_access_token").respond(
        400, json=fixture("error_token_expired.json")
    )

    assert await refresh_expiring_tokens() == 0

    session.refresh(account)
    assert account.token_expires_at == NOW
    event = session.exec(select(EventLog).where(EventLog.entity_id == account.id)).one()
    assert event.message == "ig_190_463"


async def test_client_retries_5xx_then_succeeds(http: respx.MockRouter) -> None:
    route = http.get(f"{GRAPH}/me").mock(
        side_effect=[httpx.Response(502), httpx.Response(200, json=fixture("me.json"))]
    )
    async with IgClient("t") as ig:
        assert await ig.me() == ("17841400000000001", "owner.ig")
    assert route.call_count == 2


async def test_client_does_not_retry_4xx(http: respx.MockRouter) -> None:
    route = http.get(f"{GRAPH}/me").respond(400, json=fixture("error_token_expired.json"))
    async with IgClient("t") as ig:
        with pytest.raises(IgError) as exc:
            await ig.me()
    assert exc.value.kind is IgErrorKind.token
    assert route.call_count == 1


async def test_client_gives_up_after_3_network_errors(http: respx.MockRouter) -> None:
    route = http.get(f"{GRAPH}/me").mock(side_effect=httpx.ConnectError("boom"))
    async with IgClient("t") as ig:
        with pytest.raises(IgError) as exc:
            await ig.me()
    assert exc.value.kind is IgErrorKind.retryable
    assert route.call_count == 3


@pytest.mark.parametrize(
    ("name", "status", "kind"),
    [
        ("error_quota.json", 400, IgErrorKind.quota),
        ("error_media_fetch.json", 400, IgErrorKind.retryable),
        ("error_token_expired.json", 400, IgErrorKind.token),
    ],
)
def test_error_mapping(name: str, status: int, kind: IgErrorKind) -> None:
    err = map_error(status, fixture(name))
    assert err.kind is kind
    assert err.human and "error" not in err.human.lower()
