"""Summary endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from api_server.app.schemas import SummaryResponse
from api_server.app.services.pipeline_service import get_match_rate

router = APIRouter()


@router.get("/summary", response_model=SummaryResponse)
def get_summary() -> SummaryResponse:
    """Return reconciliation summary statistics."""
    data = get_match_rate()
    return SummaryResponse(**data)
