from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, SQLModel, select

from app.core.db import get_session
from app.models import Account, Platform, Route
from app.services.accounts import SlotsIn, connect_ig, update_slots

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


@router.patch("/{account_id}")
def patch_slots(
    account_id: str, body: SlotsIn, session: Annotated[Session, Depends(get_session)]
) -> AccountRead:
    return AccountRead.of(update_slots(session, account_id, body))


@router.put("/{account_id}/ig-token")
async def put_ig_token(
    account_id: str, body: IgTokenIn, session: Annotated[Session, Depends(get_session)]
) -> AccountRead:
    return AccountRead.of(await connect_ig(session, account_id, body.token))
