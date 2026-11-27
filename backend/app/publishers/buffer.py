"""YouTube and TikTok through Buffer: Buffer itself publishes at `dueAt`.

submit() schedules the post (customScheduled); sync() reads its status after the due time.
"""

from datetime import datetime, timedelta
from typing import Any

from app.core.config import Settings
from app.core.db import utcnow
from app.models import Account, MediaAsset, Platform, PostTarget, Route, TargetStatus, YtKind
from app.publishers.base import SubmitResult, SyncResult
from app.publishers.buffer_client import BufferClient, BufferError, iso
from app.publishers.errors import ErrorKind

MIN_LEAD = timedelta(minutes=2)  # Buffer needs dueAt in the future
YT_TITLE_MAX = 100
POST_FAILED = "Buffer gagal memposting video ini."


def youtube_title(target: PostTarget) -> str:
    if target.title:
        return target.title[:YT_TITLE_MAX]
    first_line = next((line.strip() for line in target.caption.splitlines() if line.strip()), "")
    return first_line[:YT_TITLE_MAX] or "Video baru"


class BufferPublisher:
    route = Route.buffer

    def __init__(self, account: Account, settings: Settings) -> None:
        keys = settings.buffer_keys
        ref = account.buffer_key_ref or ""
        if not account.buffer_channel_id or not ref.isdigit() or int(ref) >= len(keys):
            raise BufferError(
                ErrorKind.reconnect,
                f"{account.label} belum tersambung ke Buffer. Pilih channel di Akun & slot.",
                code="buffer_not_connected",
            )
        self._account = account
        self._key = keys[int(ref)]
        self._ref = ref

    def _client(self) -> BufferClient:
        return BufferClient(self._key, self._ref)

    def payload(self, target: PostTarget, media: MediaAsset) -> dict[str, Any]:
        assert media.public_url is not None and self._account.buffer_channel_id is not None
        due = max(target.scheduled_at, utcnow() + MIN_LEAD)
        data: dict[str, Any] = {
            "channelId": self._account.buffer_channel_id,
            "text": target.caption,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": iso(due),
            "assets": [{"video": {"url": media.public_url}}],
        }
        if self._account.platform is Platform.youtube:
            data["metadata"] = {
                "youtube": {
                    "title": youtube_title(target),
                    "type": "regularVideo" if target.yt_kind is YtKind.video else "short",
                    "categoryId": self._account.yt_category_id or "22",
                }
            }
        return data

    async def validate(self, target: PostTarget, media: MediaAsset) -> list[str]:
        return []

    async def submit(self, target: PostTarget, media: MediaAsset) -> SubmitResult:
        async with self._client() as buffer:
            post_id = await buffer.create_post(
                self.payload(target, media), self._account.platform.value
            )
        return SubmitResult(provider_ref=post_id, status=TargetStatus.sent_to_buffer)

    async def sync(self, target: PostTarget) -> SyncResult:
        assert target.provider_ref is not None
        async with self._client() as buffer:
            post = await buffer.get_post(target.provider_ref)
            if post.status == "sent":
                return SyncResult(status=TargetStatus.published, published_url=post.external_link)
            if post.status == "error":
                # Free the channel's slot before retrying with a fresh post.
                await buffer.delete_post(target.provider_ref)
                raise BufferError(
                    ErrorKind.retryable,
                    POST_FAILED,
                    code="buffer_post_error",
                    raw={"post_id": post.id},
                )
        return SyncResult(status=TargetStatus.sent_to_buffer)

    async def cancel(self, target: PostTarget) -> None:
        if target.provider_ref:
            async with self._client() as buffer:
                await buffer.delete_post(target.provider_ref)

    async def reschedule(self, target: PostTarget, at: datetime) -> None:
        if target.provider_ref:
            async with self._client() as buffer:
                await buffer.edit_due(target.provider_ref, at)
