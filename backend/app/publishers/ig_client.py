"""Thin client for the Instagram API with Instagram Login (graph.instagram.com).

Endpoints and error codes: .claude/skills/platform-apis/SKILL.md.
"""

import asyncio
from enum import StrEnum
from typing import Any, Self

import httpx

from app.core.config import get_settings

HOST = "https://graph.instagram.com"
TIMEOUT_S = 30
MAX_TRIES = 3
RETRY_BASE_S = 1.0  # tests set this to 0


class IgErrorKind(StrEnum):
    token = "token"  # needs the owner to reconnect; never retried
    quota = "quota"  # publishing limit reached; retry later without counting an attempt
    retryable = "retryable"
    fatal = "fatal"  # retrying will not help (bad format, caption too long, restricted account)


class IgError(Exception):
    def __init__(
        self, kind: IgErrorKind, human: str, *, code: str, raw: dict[str, Any] | None = None
    ) -> None:
        super().__init__(f"{code}: {human}")
        self.kind = kind
        self.human = human
        self.code = code
        self.raw = raw or {}


# Retryable messages say nothing about retrying; services/publishing.py adds that context.
TOKEN_EXPIRED = "Login Instagram kedaluwarsa. Sambungkan ulang akunnya."
RATE_LIMITED = "Instagram lagi membatasi permintaan."
UNAVAILABLE = "Instagram lagi gangguan."

# Error subcodes from Meta's IG error-code reference.
SUBCODES: dict[int, tuple[IgErrorKind, str]] = {
    2207042: (
        IgErrorKind.quota,
        "Kuota posting IG hari ini habis. Dicoba lagi otomatis 1 jam lagi.",
    ),
    2207052: (
        IgErrorKind.retryable,
        "Instagram nggak bisa mengambil file videonya. Cek storage.",
    ),
    2207026: (
        IgErrorKind.fatal,
        "Instagram menolak format videonya. Upload ulang videonya sebagai MP4.",
    ),
    2207010: (
        IgErrorKind.fatal,
        "Caption terlalu panjang. Maksimal 2.200 karakter, 30 hashtag dan 20 tag @.",
    ),
    2207050: (
        IgErrorKind.fatal,
        "Akun Instagram ini sedang dibatasi. Buka aplikasi Instagram untuk cek.",
    ),
    2207051: (
        IgErrorKind.fatal,
        "Instagram membatasi posting dari akun ini karena dianggap spam. Cek aplikasi Instagram.",
    ),
}
_RATE_LIMIT_CODES = {4, 9, 17, 32, 613}


def map_error(status: int, body: dict[str, Any]) -> IgError:
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    assert isinstance(err, dict)
    code = int(err.get("code") or 0)
    subcode = int(err.get("error_subcode") or 0)
    tag = f"ig_{code}_{subcode}" if subcode else f"ig_{code or status}"
    if subcode in SUBCODES:
        kind, human = SUBCODES[subcode]
        return IgError(kind, human, code=tag, raw=body)
    if code == 190 or (err.get("type") == "OAuthException" and code in (102, 463, 467)):
        return IgError(IgErrorKind.token, TOKEN_EXPIRED, code=tag, raw=body)
    if code == 10 or 200 <= code <= 299:
        human = "Izin posting Instagram hilang. Sambungkan ulang akunnya."
        return IgError(IgErrorKind.token, human, code=tag, raw=body)
    if code in _RATE_LIMIT_CODES or status == 429:
        return IgError(IgErrorKind.retryable, RATE_LIMITED, code=tag, raw=body)
    if status >= 500:
        return IgError(IgErrorKind.retryable, UNAVAILABLE, code=tag, raw=body)
    human = "Instagram menolak permintaan dengan error yang belum dikenal."
    return IgError(IgErrorKind.retryable, human, code=tag, raw=body)


def _json(res: httpx.Response) -> dict[str, Any]:
    try:
        body = res.json()
    except ValueError:
        return {"raw": res.text[:500]}
    return body if isinstance(body, dict) else {"raw": body}


class IgClient:
    """One instance per account token; use as `async with IgClient(token) as ig:`."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._http = httpx.AsyncClient(
            base_url=f"{HOST}/{get_settings().ig_graph_version}",
            timeout=TIMEOUT_S,
            headers={"Authorization": f"Bearer {token}"},
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._http.aclose()

    async def _call(self, method: str, url: str, **kw: Any) -> dict[str, Any]:
        """5xx, 429 and network errors are retried with backoff; other 4xx are not."""
        for attempt in range(MAX_TRIES):
            last = attempt == MAX_TRIES - 1
            try:
                res = await self._http.request(method, url, **kw)
            except httpx.TransportError as exc:
                if last:
                    raw = {"exception": repr(exc)}
                    raise IgError(
                        IgErrorKind.retryable, UNAVAILABLE, code="ig_network", raw=raw
                    ) from exc
            else:
                body = _json(res)
                if res.is_success:
                    return body
                if last or not (res.status_code >= 500 or res.status_code == 429):
                    raise map_error(res.status_code, body)
            await asyncio.sleep(RETRY_BASE_S * 2**attempt)
        raise AssertionError("unreachable")

    async def me(self) -> tuple[str, str]:
        """Returns (ig_user_id, username). Meta documents a `data` list wrapper; accept both."""
        body = await self._call("GET", "/me", params={"fields": "user_id,username"})
        row = body["data"][0] if isinstance(body.get("data"), list) else body
        return str(row["user_id"]), str(row.get("username", ""))

    async def create_reels_container(self, ig_user_id: str, video_url: str, caption: str) -> str:
        body = await self._call(
            "POST",
            f"/{ig_user_id}/media",
            json={"media_type": "REELS", "video_url": video_url, "caption": caption},
        )
        return str(body["id"])

    async def container_status(self, container_id: str) -> tuple[str, str]:
        """Returns (status_code, status). `status` carries the error detail on ERROR."""
        body = await self._call("GET", f"/{container_id}", params={"fields": "status_code,status"})
        return str(body.get("status_code", "")), str(body.get("status", ""))

    async def publishing_limit(self, ig_user_id: str) -> tuple[int, int]:
        """Returns (used, total) for the rolling 24 h window."""
        body = await self._call(
            "GET",
            f"/{ig_user_id}/content_publishing_limit",
            params={"fields": "quota_usage,config"},
        )
        row = body["data"][0] if isinstance(body.get("data"), list) else body
        return int(row.get("quota_usage", 0)), int(row.get("config", {}).get("quota_total", 50))

    async def publish(self, ig_user_id: str, container_id: str) -> str:
        body = await self._call(
            "POST", f"/{ig_user_id}/media_publish", json={"creation_id": container_id}
        )
        return str(body["id"])

    async def permalink(self, media_id: str) -> str | None:
        body = await self._call("GET", f"/{media_id}", params={"fields": "permalink"})
        return body.get("permalink")

    async def refresh_token(self) -> tuple[str, int]:
        """Returns (new_token, expires_in_s). The endpoint is unversioned."""
        body = await self._call(
            "GET",
            f"{HOST}/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": self._token},
        )
        return str(body["access_token"]), int(body["expires_in"])
