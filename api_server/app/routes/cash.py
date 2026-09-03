"""Cash position endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from api_server.app.schemas import CashPositionResponse
from api_server.app.services.pipeline_service import get_cash_position

router = APIRouter()


@router.get("/cash-position", response_model=CashPositionResponse)
def cash_position() -> CashPositionResponse:
    """Return unreconciled cash exposure."""
    data = get_cash_position()
    return CashPositionResponse(**data)
