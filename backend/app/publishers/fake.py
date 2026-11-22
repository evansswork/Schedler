from app.models import MediaAsset, PostTarget, Route, TargetStatus
from app.publishers.base import SubmitResult, SyncResult


class FakePublisher:
    """Used for every route when DRY_RUN=true: accepts everything, posts nothing."""

    def __init__(self, route: Route) -> None:
        self.route = route

    async def validate(self, target: PostTarget, media: MediaAsset) -> list[str]:
        return []

    async def submit(self, target: PostTarget, media: MediaAsset) -> SubmitResult:
        status = (
            TargetStatus.published if self.route is Route.ig_direct else TargetStatus.sent_to_buffer
        )
        return SubmitResult(provider_ref=f"fake-{target.id}", status=status)

    async def sync(self, target: PostTarget) -> SyncResult:
        return SyncResult(status=TargetStatus.published)

    async def cancel(self, target: PostTarget) -> None:
        return None
