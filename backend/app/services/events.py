from typing import Any

from sqlmodel import Session

from app.models import EventLevel, EventLog


def log_event(
    session: Session,
    level: EventLevel,
    entity_type: str,
    entity_id: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Adds an EventLog row to the caller's transaction (the caller commits)."""
    session.add(
        EventLog(
            level=level,
            entity_type=entity_type,
            entity_id=entity_id,
            message=message,
            payload=payload or {},
        )
    )
