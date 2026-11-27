"""SQLModel tables. Mirrors docs/ARCHITECTURE.md §3; keep the two in sync."""

import secrets
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Index
from sqlmodel import Field, SQLModel
from ulid import ULID

from app.core.db import UTCDateTime, utcnow

# Owner's default posting times (WIB); editable per account in "Akun & slot".
DEFAULT_SLOTS = ["19:30", "20:30", "21:30", "22:30", "23:30"]


def new_id() -> str:
    return str(ULID())


def new_public_token() -> str:
    return secrets.token_urlsafe(32)


def _created() -> Any:
    return Field(default_factory=utcnow, sa_type=UTCDateTime)


def _updated() -> Any:
    return Field(default_factory=utcnow, sa_type=UTCDateTime, sa_column_kwargs={"onupdate": utcnow})


# Enum member names equal their values: SQLAlchemy stores the name.
class Platform(StrEnum):
    ig = "ig"
    youtube = "youtube"
    tiktok = "tiktok"


class Route(StrEnum):
    ig_direct = "ig_direct"
    buffer = "buffer"


class MediaSource(StrEnum):
    tiktok_link = "tiktok_link"
    upload = "upload"


class MediaStatus(StrEnum):
    pending = "pending"
    downloading = "downloading"
    processing = "processing"
    ready = "ready"
    failed = "failed"
    deleted = "deleted"


class Orientation(StrEnum):
    vertical = "vertical"
    horizontal = "horizontal"
    square = "square"


class YtKind(StrEnum):
    short = "short"
    video = "video"


class ScheduleMode(StrEnum):
    exact = "exact"
    slot = "slot"


class TargetStatus(StrEnum):
    draft = "draft"
    waiting_media = "waiting_media"
    queued_local = "queued_local"
    sent_to_buffer = "sent_to_buffer"
    publishing = "publishing"
    published = "published"
    failed = "failed"
    cancelled = "cancelled"
    manual_required = "manual_required"


class EventLevel(StrEnum):
    info = "info"
    warn = "warn"
    error = "error"


class Account(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    platform: Platform
    label: str
    handle: str = ""
    route: Route
    ig_user_id: str | None = None
    buffer_channel_id: str | None = None
    buffer_key_ref: str | None = None
    token_enc: str | None = None
    token_expires_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    timezone: str = "Asia/Jakarta"
    slots: list[str] = Field(default_factory=lambda: list(DEFAULT_SLOTS), sa_type=JSON)
    weekdays: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7], sa_type=JSON)
    active: bool = True
    created_at: datetime = _created()
    updated_at: datetime = _updated()


class MediaAsset(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    source: MediaSource
    source_url: str | None = None
    source_caption: str | None = None
    status: MediaStatus = Field(default=MediaStatus.pending, index=True)
    progress_pct: int = 0
    file_path: str | None = None
    public_url: str | None = None
    public_token: str = Field(default_factory=new_public_token, unique=True)
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    orientation: Orientation | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    error: str | None = None
    created_at: datetime = _created()
    updated_at: datetime = _updated()


class Post(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    media_id: str = Field(foreign_key="mediaasset.id")
    default_caption: str = ""
    created_at: datetime = _created()


class PostTarget(SQLModel, table=True):
    __table_args__ = (
        Index("ix_posttarget_status_scheduled_at", "status", "scheduled_at"),
        Index("ix_posttarget_account_id_scheduled_at", "account_id", "scheduled_at"),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    post_id: str = Field(foreign_key="post.id")
    account_id: str = Field(foreign_key="account.id")
    title: str | None = None
    caption: str = ""
    yt_kind: YtKind | None = None
    scheduled_at: datetime = Field(sa_type=UTCDateTime)
    schedule_mode: ScheduleMode = ScheduleMode.exact
    status: TargetStatus = TargetStatus.waiting_media
    provider_ref: str | None = None
    published_url: str | None = None
    attempts: int = 0
    next_attempt_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    last_error: str | None = None
    last_error_human: str | None = None
    created_at: datetime = _created()
    updated_at: datetime = _updated()


class EventLog(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    at: datetime = _created()
    level: EventLevel = EventLevel.info
    entity_type: str
    entity_id: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value_enc: str | None = None
    value: str | None = None
