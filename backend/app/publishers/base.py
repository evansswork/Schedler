from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models import MediaAsset, PostTarget, Route, TargetStatus


@dataclass(frozen=True)
class SubmitResult:
    provider_ref: str
    status: TargetStatus  # published (IG direct) or sent_to_buffer (Buffer)
    published_url: str | None = None


@dataclass(frozen=True)
class SyncResult:
    status: TargetStatus
    published_url: str | None = None


class Publisher(Protocol):
    route: Route

    async def validate(self, target: PostTarget, media: MediaAsset) -> list[str]:
        """Route-specific problems as human Indonesian messages (empty = OK)."""
        ...

    async def submit(self, target: PostTarget, media: MediaAsset) -> SubmitResult: ...

    async def sync(self, target: PostTarget) -> SyncResult: ...

    async def cancel(self, target: PostTarget) -> None: ...

    async def reschedule(self, target: PostTarget, at: datetime) -> None:
        """Move a post already handed to the platform (Buffer); no-op elsewhere."""
        ...
