from app.core.config import Settings
from app.core.errors import DomainError
from app.models import Account, Route
from app.publishers.base import Publisher
from app.publishers.fake import FakePublisher
from app.publishers.ig_direct import IgDirectPublisher


def get_publisher(account: Account, settings: Settings) -> Publisher:
    if settings.dry_run:
        return FakePublisher(account.route)
    if account.route is Route.ig_direct:
        return IgDirectPublisher(account)
    # The Buffer adapter arrives in Phase 3; see docs/ROADMAP.md.
    raise DomainError(
        "route_not_available",
        f"Posting beneran ke {account.label} belum tersedia. Nyalakan mode uji (DRY_RUN=true).",
        status_code=409,
    )
