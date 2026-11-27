"""Account connection (IG token) and slot settings."""

import logging
from datetime import timedelta

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, col, select

from app.core.crypto import decrypt, encrypt
from app.core.db import get_engine, utcnow
from app.core.errors import DomainError
from app.models import Account, EventLevel, Platform
from app.publishers.ig_client import IgClient, IgError, IgErrorKind
from app.services.events import log_event

logger = logging.getLogger(__name__)

# shortcut: IG does not report the expiry of a pasted token; dashboard tokens last 60 days.
# The first refresh replaces this with the real `expires_in`.
PASTED_TOKEN_LIFETIME = timedelta(days=60)
REFRESH_WHEN_LEFT = timedelta(days=15)


class SlotsIn(BaseModel):
    slots: list[str] = Field(max_length=24)
    weekdays: list[int] = Field(min_length=1, max_length=7)

    @field_validator("slots")
    @classmethod
    def _slots(cls, v: list[str]) -> list[str]:
        for s in v:
            hh, _, mm = s.partition(":")
            if not (len(hh) == len(mm) == 2 and hh.isdigit() and mm.isdigit()) or not (
                int(hh) < 24 and int(mm) < 60
            ):
                raise ValueError(f"Jam slot {s!r} nggak valid. Pakai format JJ:MM, misalnya 19:30.")
        return sorted(set(v))

    @field_validator("weekdays")
    @classmethod
    def _weekdays(cls, v: list[int]) -> list[int]:
        if any(d < 1 or d > 7 for d in v):
            raise ValueError("Hari harus antara 1 (Senin) dan 7 (Minggu).")
        return sorted(set(v))


def _get(session: Session, account_id: str) -> Account:
    account = session.get(Account, account_id)
    if account is None or not account.active:
        raise DomainError("account_not_found", "Akun nggak ditemukan.", status_code=404)
    return account


def update_slots(session: Session, account_id: str, body: SlotsIn) -> Account:
    account = _get(session, account_id)
    account.slots = body.slots
    account.weekdays = body.weekdays
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


async def connect_ig(session: Session, account_id: str, token: str) -> Account:
    account = _get(session, account_id)
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
