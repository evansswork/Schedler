from fastapi import APIRouter, Depends

from app.api import accounts, auth, health
from app.core.security import require_auth

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)

protected = APIRouter(dependencies=[Depends(require_auth)])
protected.include_router(accounts.router)
api_router.include_router(protected)
