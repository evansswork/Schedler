"""Instagram Reels via the Instagram API with Instagram Login.

submit() creates the REELS container (a few minutes before the slot); sync() polls it and
publishes once it is FINISHED and the target is due. Every step is safe to repeat: a
container that is already PUBLISHED (crash after publishing) is reported as published.
"""

import re
from datetime import timedelta

from app.core.crypto import decrypt
from app.core.db import utcnow
from app.models import Account, MediaAsset, PostTarget, Route, TargetStatus
from app.publishers.base import SubmitResult, SyncResult
from app.publishers.ig_client import SUBCODES, IgClient, IgError, IgErrorKind

# Meta suggests polling ≤ 5 min; long videos can take longer, so allow 15.
CONTAINER_TIMEOUT = timedelta(minutes=15)
REJECTED = "Instagram menolak videonya (format/durasi). Cek file atau coba upload ulang."


class IgDirectPublisher:
    route = Route.ig_direct

    def __init__(self, account: Account) -> None:
        if not (account.token_enc and account.ig_user_id):
            raise IgError(
                IgErrorKind.token,
                f"{account.label} belum tersambung. Tempel token di Akun & slot.",
                code="ig_not_connected",
            )
        self._token = decrypt(account.token_enc)
        self._ig_user_id = account.ig_user_id

    async def validate(self, target: PostTarget, media: MediaAsset) -> list[str]:
        return []  # orientation/duration warnings come from services/routing.py

    async def submit(self, target: PostTarget, media: MediaAsset) -> SubmitResult:
        assert media.public_url is not None
        async with IgClient(self._token) as ig:
            container_id = await ig.create_reels_container(
                self._ig_user_id, media.public_url, target.caption
            )
        return SubmitResult(provider_ref=container_id, status=TargetStatus.publishing)

    async def sync(self, target: PostTarget) -> SyncResult:
        assert target.provider_ref is not None
        async with IgClient(self._token) as ig:
            code, detail = await ig.container_status(target.provider_ref)
            if code == "PUBLISHED":
                return SyncResult(status=TargetStatus.published)
            if code in ("ERROR", "EXPIRED"):
                raise _container_error(code, detail)
            if code != "FINISHED":
                # updated_at is when the container was created: nothing else writes a
                # target while it is publishing (reschedule and cancel refuse it).
                if utcnow() - target.updated_at > CONTAINER_TIMEOUT:
                    raise IgError(IgErrorKind.retryable, REJECTED, code="ig_container_timeout")
                return SyncResult(status=TargetStatus.publishing)
            if target.scheduled_at > utcnow():
                return SyncResult(status=TargetStatus.publishing)
            used, total = await ig.publishing_limit(self._ig_user_id)
            if used >= total:
                kind, human = SUBCODES[2207042]
                raise IgError(kind, human, code="ig_quota_exhausted", raw={"used": used})
            media_id = await ig.publish(self._ig_user_id, target.provider_ref)
            try:
                url = await ig.permalink(media_id)
            except IgError:
                url = None  # the Reel is live; a missing link is not a failure
        return SyncResult(status=TargetStatus.published, published_url=url)

    async def cancel(self, target: PostTarget) -> None:
        return None  # unpublished containers expire on their own after 24 h


def _container_error(code: str, detail: str) -> IgError:
    raw = {"status_code": code, "status": detail}
    if code == "EXPIRED":
        return IgError(IgErrorKind.retryable, REJECTED, code="ig_container_expired", raw=raw)
    subcode = next((int(n) for n in re.findall(r"\d{7}", detail) if int(n) in SUBCODES), None)
    if subcode is None:
        return IgError(IgErrorKind.retryable, REJECTED, code="ig_container_error", raw=raw)
    kind, human = SUBCODES[subcode]
    return IgError(kind, human, code=f"ig_container_{subcode}", raw=raw)
