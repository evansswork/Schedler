from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers

SESSION_MAX_AGE_S = 30 * 24 * 3600


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast on missing config
    app = FastAPI(title="Schedler")
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
