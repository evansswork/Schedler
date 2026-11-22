from fastapi import FastAPI

from app.api import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers


def create_app() -> FastAPI:
    get_settings()  # fail fast on missing config
    app = FastAPI(title="Schedler")
    install_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
