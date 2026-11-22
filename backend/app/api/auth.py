from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.security import check_login_allowed, require_auth, start_session, verify_password

router = APIRouter(prefix="/auth")


class LoginIn(BaseModel):
    password: str


class Me(BaseModel):
    dry_run: bool
    csrf_token: str


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login")
def login(body: LoginIn, request: Request) -> Me:
    ip = _client_ip(request)
    check_login_allowed(ip)
    verify_password(ip, body.password)
    return Me(dry_run=get_settings().dry_run, csrf_token=start_session(request))


@router.get("/me", dependencies=[Depends(require_auth)])
def me(request: Request) -> Me:
    return Me(dry_run=get_settings().dry_run, csrf_token=request.session["csrf"])


@router.post("/logout", status_code=204, dependencies=[Depends(require_auth)])
def logout(request: Request) -> None:
    request.session.clear()
