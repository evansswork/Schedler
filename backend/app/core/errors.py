from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """An error with a stable code and a human Indonesian message for the UI."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}


async def _handle_domain_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    body = {"error": {"code": exc.code, "message": exc.message, "detail": exc.detail}}
    return JSONResponse(body, status_code=exc.status_code)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)
