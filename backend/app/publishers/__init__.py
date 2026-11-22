from app.core.config import Settings
from app.core.errors import DomainError
from app.models import Account
from app.publishers.base import Publisher
from app.publishers.fake import FakePublisher


def get_publisher(account: Account, settings: Settings) -> Publisher:
    if settings.dry_run:
        return FakePublisher(account.route)
    # Real adapters arrive in Phase 2 (ig_direct) and Phase 3 (buffer); see docs/ROADMAP.md.
    raise DomainError(
        "route_not_available",
        f"Posting beneran ke {account.label} belum tersedia. Nyalakan mode uji (DRY_RUN=true).",
        status_code=409,
    )
