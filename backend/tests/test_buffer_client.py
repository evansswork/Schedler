import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.publishers.buffer_client import (
    ENDPOINT,
    BufferClient,
    BufferError,
    BufferErrorKind,
    budget_ok,
    parse_rate_limit,
    rate_limit,
)

FIXTURES = Path(__file__).parent / "fixtures" / "buffer"
HEADERS = {
    "RateLimit": '"150-in-15min"; r=140; t=897, "600-in-24h"; r=500; t=40000',
    "RateLimit-Policy": '"150-in-15min"; q=150; w=900, "600-in-24h"; q=600; w=86400',
}


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def gql(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.content)


async def test_channels_lists_every_organization(http: respx.MockRouter) -> None:
    route = http.post(ENDPOINT).mock(
        side_effect=[
            httpx.Response(200, json=fixture("organizations.json"), headers=HEADERS),
            httpx.Response(200, json=fixture("channels.json"), headers=HEADERS),
        ]
    )
    async with BufferClient("key-1", "0") as buffer:
        channels = await buffer.channels()

    assert [(c.id, c.service, c.name, c.is_disconnected) for c in channels] == [
        ("ch-yt1", "youtube", "Owner AI", False),
        ("ch-yt2", "youtube", "Owner Vlog", False),
        ("ch-tt", "tiktok", "owner.tt", True),
    ]
    assert route.calls[0].request.headers["authorization"] == "Bearer key-1"
    assert gql(route.calls[1].request)["variables"] == {"org": "org-1"}
    assert rate_limit("0")[86_400] == {"q": 600, "r": 500, "t": 40000}


async def test_create_post_returns_the_buffer_id(http: respx.MockRouter) -> None:
    route = http.post(ENDPOINT).respond(json=fixture("create_ok.json"))
    payload = {"channelId": "ch-yt1", "text": "Halo"}
    async with BufferClient("k", "0") as buffer:
        assert await buffer.create_post(payload, "youtube") == "post-1"
    assert gql(route.calls.last.request)["variables"] == {"input": payload}


@pytest.mark.parametrize(
    ("name", "service", "kind"),
    [
        ("create_limit.json", "youtube", BufferErrorKind.full),
        ("create_tiktok_domain.json", "tiktok", BufferErrorKind.manual),
        ("create_tiktok_domain.json", "youtube", BufferErrorKind.retryable),
    ],
)
async def test_create_post_errors_are_classified(
    http: respx.MockRouter, name: str, service: str, kind: BufferErrorKind
) -> None:
    http.post(ENDPOINT).respond(json=fixture(name))
    async with BufferClient("k", "0") as buffer:
        with pytest.raises(BufferError) as exc:
            await buffer.create_post({}, service)
    assert exc.value.kind is kind
    assert "message" in exc.value.raw


async def test_get_post(http: respx.MockRouter) -> None:
    http.post(ENDPOINT).respond(json=fixture("post_sent.json"))
    async with BufferClient("k", "0") as buffer:
        post = await buffer.get_post("post-1")
    assert (post.status, post.external_link) == ("sent", "https://youtube.com/shorts/abc")


async def test_bad_key_is_not_retried(http: respx.MockRouter) -> None:
    route = http.post(ENDPOINT).respond(401, json={"errors": [{"message": "Unauthorized"}]})
    async with BufferClient("k", "0") as buffer:
        with pytest.raises(BufferError) as exc:
            await buffer.channels()
    assert exc.value.kind is BufferErrorKind.auth
    assert route.call_count == 1


async def test_429_waits_and_retries(http: respx.MockRouter) -> None:
    route = http.post(ENDPOINT).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "12"}, json={"errors": []}),
            httpx.Response(200, json=fixture("post_sent.json")),
        ]
    )
    async with BufferClient("k", "0") as buffer:
        assert (await buffer.get_post("post-1")).status == "sent"
    assert route.call_count == 2


async def test_5xx_gives_up_after_3_tries(http: respx.MockRouter) -> None:
    route = http.post(ENDPOINT).respond(502)
    async with BufferClient("k", "0") as buffer:
        with pytest.raises(BufferError) as exc:
            await buffer.get_post("post-1")
    assert exc.value.kind is BufferErrorKind.retryable
    assert route.call_count == 3


async def test_graphql_errors_are_fatal_with_details(http: respx.MockRouter) -> None:
    http.post(ENDPOINT).respond(json=fixture("graphql_error.json"))
    async with BufferClient("k", "0") as buffer:
        with pytest.raises(BufferError) as exc:
            await buffer.get_post("post-1")
    assert exc.value.kind is BufferErrorKind.fatal
    assert "externalLink" in exc.value.raw["errors"][0]["message"]


async def test_edit_and_delete_raise_on_mutation_error(http: respx.MockRouter) -> None:
    route = http.post(ENDPOINT).mock(
        side_effect=[
            httpx.Response(200, json={"data": {"editPost": {"__typename": "PostActionSuccess"}}}),
            httpx.Response(
                200,
                json={
                    "data": {
                        "deletePost": {"__typename": "PostNotDeletableError", "message": "Sent"}
                    }
                },
            ),
        ]
    )
    async with BufferClient("k", "0") as buffer:
        await buffer.edit_due("post-1", datetime(2026, 12, 1, 12, 30, tzinfo=UTC))
        with pytest.raises(BufferError):
            await buffer.delete_post("post-1")
    assert gql(route.calls[0].request)["variables"]["input"] == {
        "id": "post-1",
        "dueAt": "2026-12-01T12:30:00.000Z",
    }


def test_parse_rate_limit_matches_windows_by_policy() -> None:
    windows = parse_rate_limit(httpx.Headers(HEADERS))
    assert windows == {
        900: {"q": 150, "r": 140, "t": 897},
        86_400: {"q": 600, "r": 500, "t": 40000},
    }
    assert parse_rate_limit(httpx.Headers({})) == {}


async def test_budget_guard_stops_below_20_percent_of_the_day(http: respx.MockRouter) -> None:
    low = {**HEADERS, "RateLimit": '"150-in-15min"; r=140; t=897, "600-in-24h"; r=100; t=40000'}
    http.post(ENDPOINT).respond(json=fixture("post_sent.json"), headers=low)
    assert budget_ok("0")  # nothing known yet
    async with BufferClient("k", "0") as buffer:
        await buffer.get_post("post-1")
    assert not budget_ok("0")
    assert budget_ok("1")  # other keys have their own budget
