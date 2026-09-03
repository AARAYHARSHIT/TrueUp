"""Cash forecast endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Query

from api_server.app.schemas import ForecastResponse
from api_server.app.services.pipeline_service import get_cash_forecast

router = APIRouter()


@router.get("/forecast", response_model=ForecastResponse)
def forecast(
    horizon_days: int = Query(14, ge=1, le=90, description="Forecast horizon in days"),
) -> ForecastResponse:
    """Return cash flow forecast for unreconciled funds."""
    data = get_cash_forecast(horizon_days)
    return ForecastResponse(**data)
