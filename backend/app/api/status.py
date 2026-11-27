from fastapi import APIRouter

from app.services.health import HealthSummary, summary

router = APIRouter(prefix="/health")


@router.get("/summary")
def health_summary() -> HealthSummary:
    return summary()
