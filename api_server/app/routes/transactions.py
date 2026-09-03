"""Transactions endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api_server.app.schemas import (
    TransactionMatchedResponse,
    TransactionExceptionResponse,
    TransactionNotFoundResponse,
)
from api_server.app.services.pipeline_service import explain_match

router = APIRouter()


@router.get("/transactions/{txn_id}")
def get_transaction(txn_id: str) -> dict:
    """Return detailed explanation for a specific transaction."""
    data = explain_match(txn_id)

    if data["status"] == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=data)
    if data["status"] == "ERROR":
        raise HTTPException(status_code=500, detail=data)

    return data
