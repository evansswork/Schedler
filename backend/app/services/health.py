"""Dashboard health summary, built only from local data (no external API calls)."""

from datetime import timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app.core.config import get_settings
from app.core.db import get_engine, utcnow
from app.models import Account, MediaAsset, MediaStatus, Notification, PostTarget, Route, Setting
from app.models import TargetStatus as S
from app.notify import telegram
from app.publishers.buffer_client import WINDOW_DAY, WINDOW_MONTH, rate_limit
from app.services.buffer_sync import CHANNEL_LIMIT
from app.services.maintenance import YTDLP_KEY, ytdlp_versions

# shortcut: IG's limit is read live before every publish (content_publishing_limit);
# the meter assumes Meta's documented 50 per 24 h. Store the live value if it ever differs.
IG_DAILY_LIMIT = 50
TOKEN_WARN_DAYS = 15


class AccountHealth(BaseModel):
    id: str
    label: str
    route: Route
    connected: bool
    used: int  # IG: posts in the last 24 h; Buffer: posts waiting in Buffer
    limit: int
    token_days_left: int | None


class BufferBudget(BaseModel):
    day_left: int | None
    day_quota: int | None
    month_left: int | None
    month_quota: int | None


class Ytdlp(BaseModel):
    running: str
    installed: str
    last_update: str | None


class HealthSummary(BaseModel):
    status: Literal["ok", "warn", "error"]
    problems: list[str]
    notices: list[str]  # quota and API-budget limits (subset of problems)
    dry_run: bool
    accounts: list[AccountHealth]
    failed: int
    manual: int
    telegram: bool
    outbox_waiting: int
    buffer_budget: BufferBudget | None
    storage_backend: str
    storage_bytes: int
    ytdlp: Ytdlp


def _count(s: Session, *where: ColumnElement[bool] | bool) -> int:
    return s.exec(select(func.count()).select_from(PostTarget).where(*where)).one()


def summary() -> HealthSummary:
    settings = get_settings()
    now = utcnow()
    errors: list[str] = []
    warnings: list[str] = []
    notices: list[str] = []
    with Session(get_engine()) as s:
        accounts = []
        for a in s.exec(select(Account).where(Account.active).order_by(col(Account.label))):
            if a.route is Route.ig_direct:
                used = _count(
                    s,
                    PostTarget.account_id == a.id,
                    PostTarget.status == S.published,
                    col(PostTarget.updated_at) > now - timedelta(hours=24),
                )
                limit, connected = IG_DAILY_LIMIT, bool(a.token_enc)
            else:
                used = _count(
                    s, PostTarget.account_id == a.id, PostTarget.status == S.sent_to_buffer
                )
                limit, connected = CHANNEL_LIMIT, bool(a.buffer_channel_id)
            days = None
            if a.route is Route.ig_direct and connected and a.token_expires_at:
                days = (a.token_expires_at - now).days
                if days <= 0:
                    errors.append(f"Login {a.label} kedaluwarsa.")
                elif days <= TOKEN_WARN_DAYS:
                    warnings.append(f"Login {a.label} kedaluwarsa {days} hari lagi.")
            if a.route is Route.ig_direct and used >= limit * 0.8:
                notices.append(f"Kuota {a.label} hari ini hampir habis ({used}/{limit}).")
            accounts.append(
                AccountHealth(
                    id=a.id,
                    label=a.label,
                    route=a.route,
                    connected=connected,
                    used=used,
                    limit=limit,
                    token_days_left=days,
                )
            )
        failed = _count(s, PostTarget.status == S.failed)
        manual = _count(s, PostTarget.status == S.manual_required)
        outbox = s.exec(
            select(func.count())
            .select_from(Notification)
            .where(col(Notification.sent_at).is_(None))
        ).one()
        storage_bytes = s.exec(
            select(func.coalesce(func.sum(MediaAsset.size_bytes), 0)).where(
                MediaAsset.status == MediaStatus.ready
            )
        ).one()
        ytdlp_row = s.get(Setting, YTDLP_KEY)

    if failed:
        errors.append(f"{failed} post gagal tayang.")
    if manual:
        warnings.append(f"{manual} post perlu diupload manual.")

    budget = None
    if settings.buffer_keys:
        windows = rate_limit("0")
        day, month = windows.get(WINDOW_DAY, {}), windows.get(WINDOW_MONTH, {})
        budget = BufferBudget(
            day_left=day.get("r"),
            day_quota=day.get("q"),
            month_left=month.get("r"),
            month_quota=month.get("q"),
        )
        if day.get("q") and day.get("r", 0) / day["q"] < 0.2:
            notices.append("Kuota API Buffer hari ini hampir habis. Pengiriman ke Buffer ditahan.")

    running, installed = ytdlp_versions()
    warnings += notices
    status: Literal["ok", "warn", "error"] = "error" if errors else "warn" if warnings else "ok"
    return HealthSummary(
        status=status,
        problems=errors + warnings,
        notices=notices,
        dry_run=settings.dry_run,
        accounts=accounts,
        failed=failed,
        manual=manual,
        telegram=telegram.configured(),
        outbox_waiting=outbox,
        buffer_budget=budget,
        storage_backend=settings.storage_backend,
        storage_bytes=storage_bytes,
        ytdlp=Ytdlp(
            running=running, installed=installed, last_update=ytdlp_row.value if ytdlp_row else None
        ),
    )
