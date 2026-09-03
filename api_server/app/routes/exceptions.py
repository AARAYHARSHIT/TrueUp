"""Exceptions endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api_server.app.schemas import ExceptionsResponse
from api_server.app.services.pipeline_service import list_exceptions

router = APIRouter()


@router.get("/exceptions", response_model=ExceptionsResponse)
def get_exceptions(
    filter: str = Query("all", description="Filter by exception type or source"),
) -> ExceptionsResponse:
    """Return reconciliation exceptions with optional filtering."""
    data = list_exceptions(filter)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data)
    return ExceptionsResponse(**data)
