"""Account connections (IG token, Buffer channel) and per-account settings."""

import logging
from datetime import timedelta

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.core.db import get_engine, utcnow
from app.core.errors import DomainError
from app.models import Account, EventLevel, Platform, Route
from app.publishers.buffer_client import BufferClient, BufferError, Channel
from app.publishers.ig_client import IgClient, IgError, IgErrorKind
from app.services.events import log_event

logger = logging.getLogger(__name__)

# shortcut: IG does not report the expiry of a pasted token; dashboard tokens last 60 days.
# The first refresh replaces this with the real `expires_in`.
PASTED_TOKEN_LIFETIME = timedelta(days=60)
REFRESH_WHEN_LEFT = timedelta(days=15)


# YouTube's standard categories (Buffer requires one per YouTube post).
YT_CATEGORIES = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "19": "Travel & Events",
    "20": "Gaming",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
    "29": "Nonprofits & Activism",
}


class AccountUpdate(BaseModel):
    slots: list[str] | None = Field(default=None, max_length=24)
    weekdays: list[int] | None = Field(default=None, min_length=1, max_length=7)
    yt_category_id: str | None = None

    @field_validator("slots")
    @classmethod
    def _slots(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        for s in v:
            hh, _, mm = s.partition(":")
            if not (len(hh) == len(mm) == 2 and hh.isdigit() and mm.isdigit()) or not (
                int(hh) < 24 and int(mm) < 60
            ):
                raise ValueError(f"Jam slot {s!r} nggak valid. Pakai format JJ:MM, misalnya 19:30.")
        return sorted(set(v))

    @field_validator("weekdays")
    @classmethod
    def _weekdays(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        if any(d < 1 or d > 7 for d in v):
            raise ValueError("Hari harus antara 1 (Senin) dan 7 (Minggu).")
        return sorted(set(v))

    @field_validator("yt_category_id")
    @classmethod
    def _category(cls, v: str | None) -> str | None:
        if v is not None and v not in YT_CATEGORIES:
            raise ValueError("Kategori YouTube nggak dikenal.")
        return v


def get_account(session: Session, account_id: str) -> Account:
    account = session.get(Account, account_id)
    if account is None or not account.active:
        raise DomainError("account_not_found", "Akun nggak ditemukan.", status_code=404)
    return account


def update_account(session: Session, account_id: str, body: AccountUpdate) -> Account:
    account = get_account(session, account_id)
    account.sqlmodel_update(body.model_dump(exclude_unset=True))
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


async def connect_ig(session: Session, account_id: str, token: str) -> Account:
    account = get_account(session, account_id)
    if account.platform is not Platform.ig:
        raise DomainError(
            "not_instagram", f"{account.label} bukan akun Instagram.", status_code=422
        )
    token = token.strip()
    if not token:
        raise DomainError("token_empty", "Tempel token Instagram-nya dulu.", status_code=422)
    try:
        async with IgClient(token) as ig:
            ig_user_id, username = await ig.me()
    except IgError as err:
        log_event(session, EventLevel.warn, "account", account.id, err.code, err.raw)
        session.commit()
        message = (
            "Token ditolak Instagram. Pastikan token disalin utuh dari Meta App Dashboard."
            if err.kind is IgErrorKind.token
            else err.human
        )
        raise DomainError("ig_token_rejected", message, status_code=422) from err
    if other := session.exec(
        select(Account).where(Account.ig_user_id == ig_user_id, Account.id != account.id)
    ).first():
        raise DomainError(
            "ig_account_in_use",
            f"Akun @{username} sudah tersambung ke {other.label}.",
            status_code=409,
        )
    account.sqlmodel_update(
        {
            "ig_user_id": ig_user_id,
            "handle": username,
            "token_enc": encrypt(token),
            "token_expires_at": utcnow() + PASTED_TOKEN_LIFETIME,
        }
    )
    session.add(account)
    log_event(
        session, EventLevel.info, "account", account.id, "IG tersambung", {"handle": username}
    )
    session.commit()
    session.refresh(account)
    return account


def mark_token_invalid(session: Session, account: Account) -> None:
    """Expired tokens show as "Perlu login ulang"; the caller commits."""
    account.token_expires_at = utcnow()
    session.add(account)


async def refresh_expiring_tokens() -> int:
    """Refresh IG tokens that expire within 15 days. Returns how many were refreshed."""
    now = utcnow()
    with Session(get_engine()) as s:
        due = [
            (a.id, decrypt(a.token_enc))
            for a in s.exec(
                select(Account).where(
                    Account.platform == Platform.ig,
                    Account.active,
                    col(Account.token_enc).is_not(None),
                    col(Account.token_expires_at) < now + REFRESH_WHEN_LEFT,
                    col(Account.token_expires_at) > now,  # expired tokens cannot be refreshed
                )
            )
            if a.token_enc
        ]
    refreshed = 0
    for account_id, token in due:
        try:
            async with IgClient(token) as ig:
                new_token, expires_in = await ig.refresh_token()
        except IgError as err:
            with Session(get_engine()) as s:
                account = s.get_one(Account, account_id)
                if err.kind is IgErrorKind.token:
                    mark_token_invalid(s, account)
                log_event(s, EventLevel.warn, "account", account_id, err.code, err.raw)
                s.commit()
            continue
        with Session(get_engine()) as s:
            account = s.get_one(Account, account_id)
            account.token_enc = encrypt(new_token)
            account.token_expires_at = utcnow() + timedelta(seconds=expires_in)
            s.add(account)
            log_event(s, EventLevel.info, "account", account_id, "Token IG diperbarui")
            s.commit()
        refreshed += 1
    if refreshed:
        logger.info("refresh_ig_tokens: %d refreshed", refreshed)
    return refreshed


def _keys() -> list[str]:
    keys = get_settings().buffer_keys
    if not keys:
        raise DomainError(
            "buffer_not_configured",
            "Isi BUFFER_API_KEYS di .env dulu, lalu restart backend.",
            status_code=409,
        )
    return keys


async def list_buffer_channels() -> list[Channel]:
    channels: list[Channel] = []
    for ref, key in enumerate(_keys()):
        try:
            async with BufferClient(key, str(ref)) as buffer:
                channels += await buffer.channels()
        except BufferError as err:
            raise DomainError(err.code, err.human, status_code=502, detail=err.raw) from err
    return channels


async def connect_buffer(
    session: Session, account_id: str, key_ref: str, channel_id: str
) -> Account:
    account = get_account(session, account_id)
    if account.route is not Route.buffer:
        raise DomainError("not_buffer", f"{account.label} nggak lewat Buffer.", status_code=422)
    channel = next(
        (c for c in await list_buffer_channels() if (c.key_ref, c.id) == (key_ref, channel_id)),
        None,
    )
    if channel is None:
        raise DomainError(
            "buffer_channel_not_found",
            "Channel Buffer nggak ditemukan. Muat ulang daftar channel.",
            status_code=422,
        )
    if channel.service != account.platform.value:
        raise DomainError(
            "buffer_channel_mismatch",
            f"Channel {channel.name} bukan channel {account.platform.value}.",
            status_code=422,
        )
    if other := session.exec(
        select(Account).where(Account.buffer_channel_id == channel_id, Account.id != account.id)
    ).first():
        raise DomainError(
            "buffer_channel_in_use",
            f"Channel {channel.name} sudah dipakai {other.label}.",
            status_code=409,
        )
    account.sqlmodel_update(
        {"buffer_channel_id": channel_id, "buffer_key_ref": key_ref, "handle": channel.name}
    )
    session.add(account)
    log_event(
        session,
        EventLevel.info,
        "account",
        account.id,
        "Buffer tersambung",
        {"channel": channel_id},
    )
    session.commit()
    session.refresh(account)
    return account
