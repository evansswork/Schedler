import secrets
import time
from collections import defaultdict

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request

from app.core.config import get_settings
from app.core.errors import DomainError

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_S = 300

_hasher = PasswordHasher()
# shortcut: in-memory, per-process login limiter; fine for the single uvicorn worker,
# resets on restart. Move to the DB if we ever run more than one process.
_login_failures: dict[str, list[float]] = defaultdict(list)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def check_login_allowed(ip: str) -> None:
    now = time.monotonic()
    recent = [t for t in _login_failures[ip] if now - t < LOGIN_WINDOW_S]
    _login_failures[ip] = recent
    if len(recent) >= LOGIN_MAX_FAILURES:
        raise DomainError(
            "login_rate_limited",
            "Terlalu banyak percobaan login. Tunggu 5 menit, lalu coba lagi.",
            status_code=429,
        )


def verify_password(ip: str, password: str) -> None:
    stored = get_settings().admin_password_hash
    if not stored:
        raise DomainError(
            "password_not_configured",
            "Password dashboard belum diatur. Jalankan `python -m app.cli hash-password` "
            "lalu isi ADMIN_PASSWORD_HASH di .env.",
            status_code=503,
        )
    try:
        _hasher.verify(stored, password)
    except InvalidHashError as exc:
        raise DomainError(
            "password_hash_invalid",
            "ADMIN_PASSWORD_HASH di .env nggak valid. Buat ulang dengan "
            "`python -m app.cli hash-password`.",
            status_code=503,
        ) from exc
    except VerificationError as exc:
        _login_failures[ip].append(time.monotonic())
        raise DomainError("wrong_password", "Password salah.", status_code=401) from exc
    _login_failures.pop(ip, None)


def start_session(request: Request) -> str:
    request.session.clear()
    csrf = secrets.token_urlsafe(32)
    request.session.update({"user": "owner", "csrf": csrf})
    return csrf


def require_auth(request: Request) -> None:
    if request.session.get("user") != "owner":
        raise DomainError("not_logged_in", "Sesi kamu habis. Login lagi.", status_code=401)
    if request.method not in SAFE_METHODS:
        sent = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(sent, request.session.get("csrf", "")):
            raise DomainError(
                "csrf_invalid", "Sesi nggak valid. Muat ulang halaman.", status_code=403
            )
