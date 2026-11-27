"""Owner notifications (Telegram), written to an outbox in the same transaction as the
change they describe, then sent by the send_notifications job."""

import html
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, func, select

from app.core.config import get_settings
from app.core.db import get_engine, utcnow
from app.models import Account, Notification, PostTarget, TargetStatus
from app.notify import telegram

logger = logging.getLogger(__name__)

WIB = ZoneInfo("Asia/Jakarta")
BATCH_OVER = 5  # more than this many waiting → one combined message
_warned_unconfigured = False


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def wib_time(at: datetime) -> str:
    return at.astimezone(WIB).strftime("%H.%M")


def short(caption: str, n: int = 30) -> str:
    line = caption.strip().splitlines()[0] if caption.strip() else ""
    return line if len(line) <= n else line[: n - 1].rstrip(" ,.;:") + "…"


def attention_link() -> str:
    return f"{get_settings().app_base_url.rstrip('/')}/#/perhatian"


def accounts_link() -> str:
    return f"{get_settings().app_base_url.rstrip('/')}/#/akun"


def notify(session: Session, text: str) -> None:
    """Queue a message; the caller commits it together with its own change."""
    session.add(Notification(text=text))


def notify_published(session: Session, account: Account, target: PostTarget) -> None:
    lines = [f"✅ <b>{esc(account.label)}</b> tayang {wib_time(target.scheduled_at)} WIB"]
    if caption := short(target.caption):
        lines.append(esc(caption))
    if target.published_url:
        lines.append(esc(target.published_url))
    notify(session, "\n".join(lines))


def notify_failed(session: Session, account: Account, target: PostTarget) -> None:
    reason = esc(target.last_error_human or "alasan nggak diketahui")
    if target.status is TargetStatus.manual_required:
        text = f"📲 <b>{esc(account.label)}</b> perlu upload manual: {reason}"
    else:
        text = f"❌ <b>{esc(account.label)}</b> gagal: {reason}"
    notify(session, f"{text}\nBuka: {esc(attention_link())}")


async def send_pending() -> int:
    """Send queued messages (≤ 1 per second). Returns how many rows were delivered."""
    global _warned_unconfigured
    if not telegram.configured():
        if not _warned_unconfigured:
            logger.info("Telegram not configured; notifications stay in the outbox")
            _warned_unconfigured = True
        return 0
    with Session(get_engine()) as s:
        pending = s.exec(
            select(Notification)
            .where(col(Notification.sent_at).is_(None))
            .order_by(col(Notification.created_at), col(Notification.id))
        ).all()
    if not pending:
        return 0
    messages = _combine(pending) if len(pending) > BATCH_OVER else [(n.text, [n]) for n in pending]
    delivered = 0
    for text, rows in messages:
        try:
            await telegram.send(text)
        except telegram.TelegramError as err:
            logger.warning("telegram send failed: %s %s", err.human, err.raw)
            break  # keep the rest for the next run
        _mark_sent(rows)
        delivered += len(rows)
        await telegram.sleep(1)  # ≤ 1 message per second
    return delivered


def _combine(rows: list[Notification]) -> list[tuple[str, list[Notification]]]:
    """Join many messages into as few as fit Telegram's length limit."""
    out: list[tuple[str, list[Notification]]] = []
    text, group = f"🗂 {len(rows)} kabar terbaru", []
    for row in rows:
        if group and len(text) + 2 + len(row.text) > telegram.MAX_LEN:
            out.append((text, group))
            text, group = row.text, []
        else:
            text += "\n\n" + row.text
        group.append(row)
    out.append((text, group))
    return out


def _mark_sent(rows: list[Notification]) -> None:
    now = utcnow()
    with Session(get_engine()) as s:
        for row in rows:
            fresh = s.get(Notification, row.id)
            if fresh:
                fresh.sent_at = now
                s.add(fresh)
        s.commit()


def queue_daily_summary(now: datetime | None = None) -> str:
    """Today's results (WIB day) and tomorrow's plan, queued as one message."""
    now = now or utcnow()
    day = now.astimezone(WIB).date()
    start = datetime.combine(day, time(0), WIB)
    tomorrow, after = start + timedelta(days=1), start + timedelta(days=2)

    with Session(get_engine()) as s:

        def count(status: TargetStatus, lo: datetime, hi: datetime) -> int:
            return s.exec(
                select(func.count())
                .select_from(PostTarget)
                .where(
                    PostTarget.status == status,
                    col(PostTarget.scheduled_at) >= lo,
                    col(PostTarget.scheduled_at) < hi,
                )
            ).one()

        published = count(TargetStatus.published, start, tomorrow)
        failed = count(TargetStatus.failed, start, tomorrow) + count(
            TargetStatus.manual_required, start, tomorrow
        )
        upcoming = sum(
            count(st, tomorrow, after)
            for st in (TargetStatus.queued_local, TargetStatus.sent_to_buffer)
        )
        text = (
            f"📊 Ringkasan {day.strftime('%d/%m')}\n"
            f"Tayang: {published} · Gagal: {failed}\n"
            f"Besok terjadwal: {upcoming}"
        )
        if failed:
            text += f"\nBuka: {esc(attention_link())}"
        notify(s, text)
        s.commit()
    return text
