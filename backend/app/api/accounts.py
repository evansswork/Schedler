from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, SQLModel, select

from app.core.db import get_session
from app.models import Account, Platform, Route
from app.services.accounts import (
    YT_CATEGORIES,
    AccountUpdate,
    connect_buffer,
    connect_ig,
    list_buffer_channels,
    update_account,
)

router = APIRouter(prefix="/accounts")


class AccountRead(SQLModel):
    id: str
    platform: Platform
    label: str
    handle: str
    route: Route
    active: bool
    connected: bool
    token_expires_at: datetime | None
    slots: list[str]
    weekdays: list[int]
    yt_category_id: str | None
    buffer_channel_id: str | None

    @classmethod
    def of(cls, a: Account) -> AccountRead:
        connected = bool(a.token_enc) if a.route is Route.ig_direct else bool(a.buffer_channel_id)
        return cls.model_validate(a.model_dump() | {"connected": connected})


class IgTokenIn(BaseModel):
    token: str


@router.get("")
def list_accounts(session: Annotated[Session, Depends(get_session)]) -> list[AccountRead]:
    rows = session.exec(select(Account).where(Account.active).order_by(Account.label)).all()
    return [AccountRead.of(a) for a in rows]


class BufferChannelIn(BaseModel):
    key_ref: str
    channel_id: str


class BufferChannelRead(BaseModel):
    key_ref: str
    organization: str
    id: str
    service: str
    name: str
    is_disconnected: bool


@router.patch("/{account_id}")
def patch_account(
    account_id: str, body: AccountUpdate, session: Annotated[Session, Depends(get_session)]
) -> AccountRead:
    return AccountRead.of(update_account(session, account_id, body))


@router.get("/youtube-categories")
def youtube_categories() -> dict[str, str]:
    return YT_CATEGORIES


@router.get("/buffer-channels")
async def buffer_channels() -> list[BufferChannelRead]:
    return [BufferChannelRead(**vars(c)) for c in await list_buffer_channels()]


@router.put("/{account_id}/buffer-channel")
async def put_buffer_channel(
    account_id: str, body: BufferChannelIn, session: Annotated[Session, Depends(get_session)]
) -> AccountRead:
    return AccountRead.of(await connect_buffer(session, account_id, body.key_ref, body.channel_id))


@router.put("/{account_id}/ig-token")
async def put_ig_token(
    account_id: str, body: IgTokenIn, session: Annotated[Session, Depends(get_session)]
) -> AccountRead:
    return AccountRead.of(await connect_ig(session, account_id, body.token))
