"""Health check endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from api_server.app.schemas import HealthResponse
from api_server.app.services.pipeline_service import get_match_rate

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return API health status with pipeline data."""
    try:
        stats = get_match_rate()
        return HealthResponse(
            status="ok",
            version="1.0.0",
            pipeline_loaded=True,
            match_rate=stats["final"]["rate"],
        )
    except Exception:
        return HealthResponse(
            status="degraded",
            version="1.0.0",
            pipeline_loaded=False,
            match_rate="",
        )
