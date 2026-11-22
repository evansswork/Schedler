import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.jobs import create_scheduler
from app.services.media import reset_stuck_media

SESSION_MAX_AGE_S = 30 * 24 * 3600


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = None
    if get_settings().scheduler_enabled:
        reset_stuck_media()
        scheduler = create_scheduler()
        scheduler.start()
    app.state.scheduler = scheduler
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast on missing config
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("apscheduler").setLevel(logging.WARNING)  # logs every 30 s run otherwise
    app = FastAPI(title="Schedler", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="schedler_session",
        max_age=SESSION_MAX_AGE_S,
        same_site="lax",
        https_only=settings.app_env == "production",
    )
    install_error_handlers(app)
    app.include_router(api_router)
    if settings.storage_backend == "local_public":
        public_dir = settings.media_dir / "public"
        public_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/m", StaticFiles(directory=public_dir), name="media")
    return app


app = create_app()
