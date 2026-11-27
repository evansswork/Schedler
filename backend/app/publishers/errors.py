from datetime import timedelta
from enum import StrEnum
from typing import Any


class ErrorKind(StrEnum):
    reconnect = "reconnect"  # token/key invalid or account not connected; never retried
    wait = "wait"  # quota used up or queue full; retry later without counting an attempt
    manual = "manual"  # the platform route cannot post it; the owner posts by hand
    retryable = "retryable"
    fatal = "fatal"  # retrying will not help (bad format, caption too long, ...)


class PublishError(Exception):
    """A publishing failure with a stable code and a human Indonesian message."""

    def __init__(
        self,
        kind: ErrorKind,
        human: str,
        *,
        code: str,
        raw: dict[str, Any] | None = None,
        wait: timedelta = timedelta(hours=1),
    ) -> None:
        super().__init__(f"{code}: {human}")
        self.kind = kind
        self.human = human
        self.code = code
        self.raw = raw or {}
        self.wait = wait  # only used for ErrorKind.wait
