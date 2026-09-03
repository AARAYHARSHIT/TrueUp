"""Pydantic schemas for TrueUp API responses.

Defines request/response models for all API endpoints.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    pipeline_loaded: bool = True
    match_rate: str = ""


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class DeterministicPass(BaseModel):
    matched: int
    rate: str
    full_triples: int
    amount_disagreements: int
    date_drifts: int


class FuzzyPass(BaseModel):
    additional_matched: int
    split_detected: int
    batch_detected: int
    fuzzy_amount_date_edit: int


class FinalStats(BaseModel):
    matched: int
    rate: str


class UnmatchedStats(BaseModel):
    gateway: int
    exceptions_total: int


class SummaryResponse(BaseModel):
    gateway_total: int
    bank_total: int
    ledger_total: int
    deterministic_pass: DeterministicPass
    fuzzy_pass: FuzzyPass
    final: FinalStats
    improvement_pp: str
    unmatched: UnmatchedStats


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class PipelineResponse(BaseModel):
    gateway_total: int
    bank_total: int
    ledger_total: int
    deterministic_matched: int
    fuzzy_matched: int
    total_matched: int
    exceptions_total: int
    exception_types: dict[str, int]
    deterministic_rate: str
    final_rate: str


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ExceptionItem(BaseModel):
    exception_id: str
    type: str
    source: str
    record_id: str
    amount: Optional[str] = None
    date: Optional[str] = None
    reason: str


class ExceptionsResponse(BaseModel):
    filter_applied: str
    total: int
    by_type: dict[str, int]
    exceptions: list[ExceptionItem]


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class BankSettlementInfo(BaseModel):
    utr: str
    settlement_amount: str
    settlement_date: str


class MerchantLedgerInfo(BaseModel):
    order_id: str
    expected_amount: str
    entry_date: str
    notes: str


class TransactionMatchedResponse(BaseModel):
    txn_id: str
    status: str = "MATCHED"
    match_pass: str
    method: str
    confidence: float
    gateway_amount: str
    gateway_date: str
    gateway_fee: str
    amount_agrees: bool
    date_lag_days: Optional[int] = None
    bank_settlement: Optional[BankSettlementInfo] = None
    merchant_ledger: Optional[MerchantLedgerInfo] = None


class TransactionExceptionResponse(BaseModel):
    txn_id: str
    status: str = "EXCEPTION"
    exception_id: str
    exception_type: str
    source: str
    amount: Optional[str] = None
    date: Optional[str] = None
    reason: str
    evidence: dict[str, Any] = {}
    linked_record_ids: list[str] = []


class TransactionNotFoundResponse(BaseModel):
    txn_id: str
    status: str
    error: str
    hint: Optional[str] = None


# ---------------------------------------------------------------------------
# Cash Position
# ---------------------------------------------------------------------------

class CashComponent(BaseModel):
    description: str
    count: int
    order_ids: list[str] = []
    exposure_inr: str


class BatchPendingComponent(BaseModel):
    description: str
    count: int
    exposure_inr: str


class CashPositionResponse(BaseModel):
    as_of: str
    missing_settlement: CashComponent
    orphan_ledger: CashComponent
    batch_settlement_pending: BatchPendingComponent
    total_unreconciled_inr: str


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

class ForecastEntry(BaseModel):
    forecast_date: str
    order_id: str
    amount_inr: str
    confidence: float
    reason: str
    source_exception_type: str


class ForecastResponse(BaseModel):
    generated_at: str
    horizon_days: int
    total_forecast_inr: str
    by_date: dict[str, str]
    by_exception_type: dict[str, str]
    entries: list[ForecastEntry]


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="Natural-language question")
    provider: Optional[str] = Field(None, description="Override provider: 'groq' or 'gemini'")


class ToolUsed(BaseModel):
    name: str
    input: dict[str, Any]
    result_summary: str


class ChatResponse(BaseModel):
    answer: str
    tools_used: list[ToolUsed]
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

class RunDemoResponse(BaseModel):
    status: str
    message: str
    match_rate: str
    exceptions: int
    tests_passed: bool


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class ReconciliationReportResponse(BaseModel):
    generated_at: Optional[str] = None
    pipeline: Optional[str] = None
    record_counts: Optional[dict[str, int]] = None
    match_rates: Optional[dict[str, Any]] = None
    exceptions: Optional[dict[str, Any]] = None
    ground_truth_comparison: Optional[dict[str, Any]] = None
