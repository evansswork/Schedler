"""Thin client for Buffer's GraphQL API (https://developers.buffer.com).

Field names: .claude/skills/platform-apis/SKILL.md. Items marked "verify live" there were
taken from the docs without a live key; check them on the first real run.
"""

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Self

import httpx
from sqlmodel import Session

from app.core.db import get_engine, utcnow
from app.models import Setting
from app.publishers.errors import ErrorKind, PublishError

ENDPOINT = "https://api.buffer.com"
_sleep = asyncio.sleep  # tests replace this
TIMEOUT_S = 30
MAX_TRIES = 3
RETRY_BASE_S = 1.0
MAX_RETRY_AFTER_S = 60
WINDOW_DAY = 86_400
WINDOW_MONTH = 2_592_000
# Stop sending new posts before Buffer's own limits bite (see ARCHITECTURE §5).
MIN_LEFT = {WINDOW_DAY: 0.2, WINDOW_MONTH: 0.1}


class BufferError(PublishError):
    pass


@dataclass(frozen=True)
class Channel:
    key_ref: str
    organization: str
    id: str
    service: str
    name: str
    is_disconnected: bool


@dataclass(frozen=True)
class BufferPost:
    id: str
    status: str
    external_link: str | None


AUTH_FAILED = "API key Buffer ditolak. Cek BUFFER_API_KEYS di .env."
UNAVAILABLE = "Buffer lagi gangguan."
RATE_LIMITED = "Buffer lagi membatasi permintaan."

_FULL = re.compile(r"limit|maximum|queue is full", re.I)
_MANUAL = re.compile(r"domain|verif|pull_from_url|unaudited|not allowed to post", re.I)
_RATELIMIT_ENTRY = re.compile(r'"([^"]+)"\s*((?:;\s*\w+=[^,;]+)*)')


def classify_mutation_error(message: str, service: str) -> BufferError:
    raw = {"message": message}
    if _FULL.search(message):
        human = "Antrian Buffer untuk akun ini penuh. Sisanya nunggu otomatis."
        return BufferError(
            ErrorKind.wait, human, code="buffer_full", raw=raw, wait=timedelta(minutes=30)
        )
    if service == "tiktok" and _MANUAL.search(message):
        human = (
            "TikTok belum bisa diposting lewat Buffer. Upload manual: unduh file dan salin caption."
        )
        return BufferError(ErrorKind.manual, human, code="buffer_tiktok_manual", raw=raw)
    human = f"Buffer menolak post: {message}"
    return BufferError(ErrorKind.retryable, human, code="buffer_rejected", raw=raw)


def parse_rate_limit(headers: httpx.Headers) -> dict[int, dict[str, int]]:
    """`RateLimit` + `RateLimit-Policy` → {window_s: {"r": left, "q": quota, "t": reset_s}}."""

    def entries(value: str) -> dict[str, dict[str, int]]:
        out = {}
        for name, params in _RATELIMIT_ENTRY.findall(value):
            pairs = (p.split("=", 1) for p in params.split(";") if "=" in p)
            out[name] = {k.strip(): int(v) for k, v in pairs if v.strip().isdigit()}
        return out

    usage = entries(headers.get("ratelimit", ""))
    policy = entries(headers.get("ratelimit-policy", ""))
    windows: dict[int, dict[str, int]] = {}
    for name, p in policy.items():
        if "w" in p and name in usage:
            windows[p["w"]] = {"q": p.get("q", 0), **usage[name]}
    return windows


def _setting_key(key_ref: str) -> str:
    return f"buffer_ratelimit:{key_ref}"


def save_rate_limit(key_ref: str, windows: dict[int, dict[str, int]]) -> None:
    if not windows:
        return
    value = json.dumps({"at": utcnow().isoformat(), "windows": windows})
    with Session(get_engine()) as s:
        s.merge(Setting(key=_setting_key(key_ref), value=value))
        s.commit()


def rate_limit(key_ref: str) -> dict[int, dict[str, int]]:
    """Last known windows for this key, dropping ones that have reset since."""
    with Session(get_engine()) as s:
        row = s.get(Setting, _setting_key(key_ref))
    if row is None or not row.value:
        return {}
    data = json.loads(row.value)
    age = (utcnow() - datetime.fromisoformat(data["at"])).total_seconds()
    return {int(w): v for w, v in data["windows"].items() if v.get("t", 0) > age}


def budget_ok(key_ref: str) -> bool:
    for window, w in rate_limit(key_ref).items():
        floor = MIN_LEFT.get(window)
        if floor is not None and w.get("q") and w.get("r", 0) / w["q"] < floor:
            return False
    return True


class BufferClient:
    """One instance per API key; use as `async with BufferClient(key, key_ref) as buffer:`."""

    def __init__(self, key: str, key_ref: str) -> None:
        self.key_ref = key_ref
        self._http = httpx.AsyncClient(
            timeout=TIMEOUT_S, headers={"Authorization": f"Bearer {key}"}
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._http.aclose()

    async def _gql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {"query": query, "variables": variables or {}}
        for attempt in range(MAX_TRIES):
            last = attempt == MAX_TRIES - 1
            wait = RETRY_BASE_S * 2**attempt
            try:
                res = await self._http.post(ENDPOINT, json=payload)
            except httpx.TransportError as exc:
                if last:
                    raw = {"exception": repr(exc)}
                    raise BufferError(
                        ErrorKind.retryable, UNAVAILABLE, code="buffer_network", raw=raw
                    ) from exc
            else:
                save_rate_limit(self.key_ref, parse_rate_limit(res.headers))
                body = _json(res)
                if res.status_code == 401:
                    raise BufferError(ErrorKind.reconnect, AUTH_FAILED, code="buffer_401", raw=body)
                if res.status_code == 429:
                    if last:
                        raise BufferError(
                            ErrorKind.retryable, RATE_LIMITED, code="buffer_429", raw=body
                        )
                    retry_after = res.headers.get("retry-after", "")
                    if retry_after.isdigit():
                        wait = min(int(retry_after), MAX_RETRY_AFTER_S)
                elif res.status_code >= 500:
                    if last:
                        raise BufferError(
                            ErrorKind.retryable, UNAVAILABLE, code="buffer_5xx", raw=body
                        )
                elif errors := body.get("errors"):
                    # GraphQL-level errors: schema mismatch or bad input. Not retried.
                    raise BufferError(
                        ErrorKind.fatal,
                        "Permintaan ke Buffer nggak valid. Detailnya ada di log server.",
                        code="buffer_graphql",
                        raw={"errors": errors},
                    )
                elif res.is_success:
                    return body.get("data") or {}
                else:
                    raise BufferError(
                        ErrorKind.fatal,
                        UNAVAILABLE,
                        code=f"buffer_{res.status_code}",
                        raw=body,
                    )
            await _sleep(wait)
        raise AssertionError("unreachable")

    async def channels(self) -> list[Channel]:
        data = await self._gql("query { account { organizations { id name } } }")
        out: list[Channel] = []
        for org in data["account"]["organizations"]:
            res = await self._gql(
                "query($org: OrganizationId!) { channels(input: {organizationId: $org}) "
                "{ id name displayName service isDisconnected } }",
                {"org": org["id"]},
            )
            out += [
                Channel(
                    key_ref=self.key_ref,
                    organization=org["name"],
                    id=c["id"],
                    service=str(c["service"]).lower(),
                    name=c.get("displayName") or c["name"],
                    is_disconnected=bool(c.get("isDisconnected")),
                )
                for c in res["channels"]
            ]
        return out

    async def create_post(self, payload: dict[str, Any], service: str) -> str:
        data = await self._gql(
            "mutation($input: CreatePostInput!) { createPost(input: $input) { __typename "
            "... on PostActionSuccess { post { id } } ... on MutationError { message } } }",
            {"input": payload},
        )
        result = data["createPost"]
        if "post" in result:
            return str(result["post"]["id"])
        raise classify_mutation_error(str(result.get("message", "")), service)

    async def get_post(self, post_id: str) -> BufferPost:
        data = await self._gql(
            "query($id: PostId!) { post(input: {id: $id}) { id status externalLink } }",
            {"id": post_id},
        )
        post = data["post"]
        return BufferPost(
            id=str(post["id"]),
            status=str(post["status"]).lower(),
            external_link=post.get("externalLink"),
        )

    async def edit_due(self, post_id: str, due_at: datetime) -> None:
        await self._mutate(
            "editPost", "EditPostInput", {"id": post_id, "dueAt": iso(due_at)}, "edit"
        )

    async def delete_post(self, post_id: str) -> None:
        await self._mutate("deletePost", "DeletePostInput", {"id": post_id}, "delete")

    async def _mutate(self, name: str, input_type: str, value: dict[str, Any], what: str) -> None:
        data = await self._gql(
            f"mutation($input: {input_type}!) {{ {name}(input: $input) {{ __typename "
            "... on MutationError { message } } }",
            {"input": value},
        )
        if message := data[name].get("message"):
            raise BufferError(
                ErrorKind.fatal,
                f"Buffer menolak perubahan: {message}",
                code=f"buffer_{what}_rejected",
                raw={"message": message},
            )


def iso(at: datetime) -> str:
    return at.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _json(res: httpx.Response) -> dict[str, Any]:
    try:
        body = res.json()
    except ValueError:
        return {"raw": res.text[:500]}
    return body if isinstance(body, dict) else {"raw": body}
