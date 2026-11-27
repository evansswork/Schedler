import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.cli import seed_accounts
from app.core.config import get_settings
from app.models import Account, Platform, Route
from app.publishers.buffer_client import ENDPOINT
from tests.factories import make_account
from tests.test_buffer_client import fixture


@pytest.fixture
def buffer_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUFFER_API_KEYS", "key-a")
    get_settings.cache_clear()


def mock_channels(http: respx.MockRouter) -> respx.Route:
    return http.post(ENDPOINT).mock(
        side_effect=lambda req: httpx.Response(
            200,
            json=fixture("organizations.json")
            if b"organizations" in req.content
            else fixture("channels.json"),
        )
    )


def yt(session: Session, label: str = "YT #1") -> Account:
    return make_account(session, label=label, platform=Platform.youtube, route=Route.buffer)


@pytest.mark.usefixtures("buffer_key")
def test_lists_channels(auth_client: TestClient, http: respx.MockRouter) -> None:
    mock_channels(http)
    res = auth_client.get("/api/v1/accounts/buffer-channels")
    assert res.status_code == 200, res.text
    assert [c["id"] for c in res.json()] == ["ch-yt1", "ch-yt2", "ch-tt"]
    assert res.json()[0]["key_ref"] == "0"


def test_channels_need_a_key(auth_client: TestClient) -> None:
    res = auth_client.get("/api/v1/accounts/buffer-channels")
    assert res.status_code == 409
    assert "BUFFER_API_KEYS" in res.json()["error"]["message"]


@pytest.mark.usefixtures("buffer_key")
def test_connect_channel(auth_client: TestClient, session: Session, http: respx.MockRouter) -> None:
    account = yt(session)
    mock_channels(http)
    res = auth_client.put(
        f"/api/v1/accounts/{account.id}/buffer-channel",
        json={"key_ref": "0", "channel_id": "ch-yt1"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["connected"] is True
    assert res.json()["handle"] == "Owner AI"
    session.refresh(account)
    assert (account.buffer_channel_id, account.buffer_key_ref) == ("ch-yt1", "0")


@pytest.mark.usefixtures("buffer_key")
def test_connect_refuses_wrong_platform_and_duplicates(
    auth_client: TestClient, session: Session, http: respx.MockRouter
) -> None:
    first = yt(session)
    first.buffer_channel_id = "ch-yt1"
    session.add(first)
    session.commit()
    second = yt(session, "YT #2")
    mock_channels(http)

    res = auth_client.put(
        f"/api/v1/accounts/{second.id}/buffer-channel", json={"key_ref": "0", "channel_id": "ch-tt"}
    )
    assert res.json()["error"]["code"] == "buffer_channel_mismatch"
    res = auth_client.put(
        f"/api/v1/accounts/{second.id}/buffer-channel",
        json={"key_ref": "0", "channel_id": "ch-yt1"},
    )
    assert res.json()["error"]["message"] == "Channel Owner AI sudah dipakai YT #1."


def test_youtube_category_is_validated(auth_client: TestClient, session: Session) -> None:
    account = yt(session)
    url = f"/api/v1/accounts/{account.id}"
    assert auth_client.patch(url, json={"yt_category_id": "24"}).json()["yt_category_id"] == "24"
    res = auth_client.patch(url, json={"yt_category_id": "999"})
    assert res.status_code == 422
    assert res.json()["error"]["message"] == "Kategori YouTube nggak dikenal."
    session.refresh(account)
    assert account.slots  # a partial update keeps the other fields


def test_seeded_youtube_accounts_get_the_owner_categories(session: Session) -> None:
    seed_accounts(session)
    categories = {a.label: a.yt_category_id for a in session.exec(select(Account))}
    assert categories["YT #1"] == "28"
    assert categories["YT #2"] == "22"
    assert categories["IG #1"] is None
