from fastapi.testclient import TestClient
from sqlmodel import Session

from app.cli import seed_accounts
from tests.conftest import TEST_PASSWORD


def test_login_sets_session_and_me_returns_csrf(client: TestClient) -> None:
    res = client.post("/api/v1/auth/login", json={"password": TEST_PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["dry_run"] is True
    me = client.get("/api/v1/auth/me").json()
    assert me["csrf_token"] == body["csrf_token"]


def test_wrong_password_rejected_with_human_message(client: TestClient) -> None:
    res = client.post("/api/v1/auth/login", json={"password": "nope"})
    assert res.status_code == 401
    assert res.json()["error"] == {
        "code": "wrong_password",
        "message": "Password salah.",
        "detail": {},
    }


def test_login_rate_limited_after_5_failures_even_with_right_password(client: TestClient) -> None:
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"password": "nope"}).status_code == 401
    res = client.post("/api/v1/auth/login", json={"password": TEST_PASSWORD})
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "login_rate_limited"


def test_protected_routes_need_login(client: TestClient) -> None:
    assert client.get("/api/v1/accounts").status_code == 401
    assert client.get("/api/v1/auth/me").json()["error"]["code"] == "not_logged_in"


def test_mutation_without_csrf_header_rejected(auth_client: TestClient) -> None:
    del auth_client.headers["X-CSRF-Token"]
    res = auth_client.post("/api/v1/auth/logout")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "csrf_invalid"


def test_logout_ends_session(auth_client: TestClient) -> None:
    assert auth_client.post("/api/v1/auth/logout").status_code == 204
    assert auth_client.get("/api/v1/accounts").status_code == 401


def test_seed_accounts_is_idempotent_and_listed(auth_client: TestClient, session: Session) -> None:
    assert seed_accounts(session) == ["IG #1", "IG #2", "YT #1", "YT #2", "TikTok"]
    assert seed_accounts(session) == []
    accounts = auth_client.get("/api/v1/accounts").json()
    assert [(a["label"], a["route"]) for a in accounts] == [
        ("IG #1", "ig_direct"),
        ("IG #2", "ig_direct"),
        ("TikTok", "buffer"),
        ("YT #1", "buffer"),
        ("YT #2", "buffer"),
    ]
