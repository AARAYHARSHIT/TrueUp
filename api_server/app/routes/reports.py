"""Reports endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from api_server.app.schemas import ReconciliationReportResponse
from api_server.app.services.pipeline_service import get_reconciliation_report

router = APIRouter()


@router.get("/reports/reconciliation", response_model=ReconciliationReportResponse)
def reconciliation_report() -> ReconciliationReportResponse:
    """Return the full reconciliation report."""
    data = get_reconciliation_report()
    if "error" in data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=data)
    return ReconciliationReportResponse(**data)
