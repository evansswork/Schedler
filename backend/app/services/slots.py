"""AutoSchedule: per-account posting slots (slot times on chosen weekdays, account timezone)."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.models import Account, PostTarget, TargetStatus

MIN_LEAD = timedelta(minutes=5)  # IG needs a few minutes to prepare the container
HORIZON_DAYS = 366
_FREE_AGAIN = (TargetStatus.cancelled, TargetStatus.failed)


def slot_times(
    account: Account, after: datetime, count: int, taken: set[datetime]
) -> list[datetime]:
    """The next `count` slot times (UTC) strictly after `after`, skipping `taken`."""
    times = sorted(time.fromisoformat(s) for s in account.slots)
    if not times or not account.weekdays:
        return []
    tz = ZoneInfo(account.timezone)
    first_day = after.astimezone(tz).date()
    out: list[datetime] = []
    for offset in range(HORIZON_DAYS):
        day = first_day + timedelta(days=offset)
        if day.isoweekday() not in account.weekdays:
            continue
        for t in times:
            at = datetime.combine(day, t, tz).astimezone(UTC)
            if at > after and at not in taken:
                out.append(at)
                if len(out) == count:
                    return out
    return out


def next_free_slots(session: Session, account: Account, count: int) -> list[datetime]:
    after = utcnow() + MIN_LEAD
    taken = set(
        session.exec(
            select(PostTarget.scheduled_at).where(
                PostTarget.account_id == account.id,
                col(PostTarget.scheduled_at) > after,
                col(PostTarget.status).not_in(_FREE_AGAIN),
            )
        )
    )
    slots = slot_times(account, after, count, taken)
    if len(slots) < count:
        raise DomainError(
            "no_slots",
            f"Atur slot dulu untuk {account.label} di Akun & slot.",
            status_code=422,
            detail={"account_id": account.id},
        )
    return slots
