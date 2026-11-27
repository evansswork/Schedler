from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
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


async def _handle_validation_error(_request: Request, exc: Exception) -> JSONResponse:
    """Schema errors in the same shape as DomainError. Our own validators raise
    ValueError with an Indonesian message; pydantic's built-in messages are English."""
    assert isinstance(exc, RequestValidationError)
    errors = list(exc.errors())
    ours = next((e for e in errors if e.get("type") == "value_error"), None)
    message = str(ours["ctx"]["error"]) if ours else "Data yang dikirim nggak valid."
    detail = {"errors": [{"loc": list(e["loc"]), "type": e["type"]} for e in errors]}
    body = {"error": {"code": "invalid_request", "message": message, "detail": detail}}
    return JSONResponse(body, status_code=422)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
