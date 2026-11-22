from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, SQLModel, select

from app.core.db import get_session
from app.models import Account, Platform, Route

router = APIRouter(prefix="/accounts")


class AccountRead(SQLModel):
    id: str
    platform: Platform
    label: str
    handle: str
    route: Route
    active: bool


@router.get("")
def list_accounts(session: Annotated[Session, Depends(get_session)]) -> list[AccountRead]:
    rows = session.exec(select(Account).where(Account.active).order_by(Account.label)).all()
    return [AccountRead.model_validate(a, from_attributes=True) for a in rows]
