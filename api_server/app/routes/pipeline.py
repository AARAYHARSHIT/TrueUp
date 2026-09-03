"""Pipeline endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from api_server.app.schemas import PipelineResponse
from api_server.app.services.pipeline_service import get_pipeline_data

router = APIRouter()


@router.get("/pipeline", response_model=PipelineResponse)
def get_pipeline() -> PipelineResponse:
    """Return pipeline processing details."""
    p = get_pipeline_data()
    gw_total = len(p["gateway"])
    det_n = len(p["det_matched"])
    final_n = len(p["all_matched"])
    det_rate = det_n / gw_total if gw_total else 0.0
    final_rate = final_n / gw_total if gw_total else 0.0

    exc_by_type: dict[str, int] = {}
    for e in p["exc_report"]["exceptions"]:
        t = e["type"]
        exc_by_type[t] = exc_by_type.get(t, 0) + 1

    return PipelineResponse(
        gateway_total=gw_total,
        bank_total=len(p["bank"]),
        ledger_total=len(p["ledger"]),
        deterministic_matched=det_n,
        fuzzy_matched=len(p["fuzzy_matched"]),
        total_matched=final_n,
        exceptions_total=len(p["exceptions"]),
        exception_types=exc_by_type,
        deterministic_rate=f"{det_rate * 100:.2f}%",
        final_rate=f"{final_rate * 100:.2f}%",
    )
