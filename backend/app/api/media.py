from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, SQLModel, col, select

from app.core.db import get_session
from app.jobs import PROCESS_MEDIA, kick
from app.models import MediaAsset, MediaSource, MediaStatus, Orientation, Platform, YtKind
from app.services import media as media_service
from app.services.routing import warnings_for, youtube_kind

router = APIRouter(prefix="/media")


class MediaRead(SQLModel):
    id: str
    source: MediaSource
    source_url: str | None
    source_caption: str | None
    status: MediaStatus
    progress_pct: int
    public_url: str | None
    width: int | None
    height: int | None
    duration_s: float | None
    orientation: Orientation | None
    error: str | None
    yt_kind: YtKind | None = None
    warnings: dict[Platform, list[str]] = {}

    @classmethod
    def of(cls, m: MediaAsset) -> MediaRead:
        read = cls.model_validate(m, from_attributes=True)
        if m.orientation is not None and m.duration_s is not None:
            read.yt_kind = youtube_kind(m.orientation, m.duration_s)
            read.warnings = {
                p: w for p in Platform if (w := warnings_for(p, m.orientation, m.duration_s))
            }
        return read


class LinksIn(BaseModel):
    urls: list[str]


@router.post("/links", status_code=201)
def create_from_links(
    body: LinksIn, request: Request, session: Annotated[Session, Depends(get_session)]
) -> list[MediaRead]:
    created = media_service.create_from_links(session, body.urls)
    kick(request.app.state.scheduler, PROCESS_MEDIA)
    return [MediaRead.of(m) for m in created]


@router.post("/upload", status_code=201)
def upload(
    files: list[UploadFile], request: Request, session: Annotated[Session, Depends(get_session)]
) -> list[MediaRead]:
    created = [
        media_service.create_from_upload(session, f.filename or "video", f.file) for f in files
    ]
    kick(request.app.state.scheduler, PROCESS_MEDIA)
    return [MediaRead.of(m) for m in created]


@router.get("")
def list_media(
    session: Annotated[Session, Depends(get_session)],
    ids: Annotated[list[str], Query(max_length=100)],
) -> list[MediaRead]:
    rows = session.exec(select(MediaAsset).where(col(MediaAsset.id).in_(ids))).all()
    by_id = {m.id: m for m in rows}
    return [MediaRead.of(by_id[i]) for i in ids if i in by_id]
