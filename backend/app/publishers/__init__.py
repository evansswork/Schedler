from app.core.config import Settings
from app.models import Account, Route
from app.publishers.base import Publisher
from app.publishers.buffer import BufferPublisher
from app.publishers.fake import FakePublisher
from app.publishers.ig_direct import IgDirectPublisher


def get_publisher(account: Account, settings: Settings) -> Publisher:
    if settings.dry_run:
        return FakePublisher(account.route)
    if account.route is Route.ig_direct:
        return IgDirectPublisher(account)
    return BufferPublisher(account, settings)
