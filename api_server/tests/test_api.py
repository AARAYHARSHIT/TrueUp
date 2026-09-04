"""API integration tests for TrueUp FastAPI endpoints.

Tests all API endpoints against the live pipeline data.
No LLM API key required — only deterministic pipeline tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure trueup is importable
_TRUEUP_ROOT = Path(__file__).resolve().parent.parent.parent / "trueup"
if str(_TRUEUP_ROOT) not in sys.path:
    sys.path.insert(0, str(_TRUEUP_ROOT))

from api_server.app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

class TestRoot:
    def test_root_returns_info(self):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "TrueUp API"
        assert data["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["pipeline_loaded"] is True
        assert data["match_rate"] == "87.50%"

    def test_health_has_version(self):
        resp = client.get("/api/v1/health")
        assert resp.json()["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_returns_stats(self):
        resp = client.get("/api/v1/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gateway_total"] == 80
        assert data["bank_total"] == 75
        assert data["ledger_total"] == 78

    def test_summary_deterministic_rate(self):
        resp = client.get("/api/v1/summary")
        data = resp.json()
        assert data["deterministic_pass"]["rate"] == "73.75%"
        assert data["deterministic_pass"]["matched"] == 59

    def test_summary_final_rate(self):
        resp = client.get("/api/v1/summary")
        data = resp.json()
        assert data["final"]["rate"] == "87.50%"
        assert data["final"]["matched"] == 70

    def test_summary_improvement(self):
        resp = client.get("/api/v1/summary")
        data = resp.json()
        assert data["improvement_pp"] == "+13.75pp"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class TestPipeline:
    def test_pipeline_returns_data(self):
        resp = client.get("/api/v1/pipeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gateway_total"] == 80
        assert data["deterministic_matched"] == 59
        assert data["total_matched"] == 70

    def test_pipeline_exception_types(self):
        resp = client.get("/api/v1/pipeline")
        data = resp.json()
        assert "MISSING_SETTLEMENT" in data["exception_types"]
        assert "BATCH_SETTLEMENT" in data["exception_types"]
        assert "ORPHAN_LEDGER" in data["exception_types"]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TestExceptions:
    def test_exceptions_all(self):
        resp = client.get("/api/v1/exceptions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 24
        assert data["filter_applied"] == "all"

    def test_exceptions_by_type(self):
        resp = client.get("/api/v1/exceptions")
        data = resp.json()
        assert "BATCH_SETTLEMENT" in data["by_type"]
        assert "MISSING_SETTLEMENT" in data["by_type"]
        assert "ORPHAN_LEDGER" in data["by_type"]

    def test_exceptions_filter_type(self):
        resp = client.get("/api/v1/exceptions?filter=MISSING_SETTLEMENT")
        data = resp.json()
        assert data["filter_applied"] == "type=MISSING_SETTLEMENT"
        assert all(e["type"] == "MISSING_SETTLEMENT" for e in data["exceptions"])

    def test_exceptions_filter_source(self):
        resp = client.get("/api/v1/exceptions?filter=gateway")
        data = resp.json()
        assert data["filter_applied"] == "source=gateway"
        assert all(e["source"] == "gateway" for e in data["exceptions"])

    def test_exceptions_invalid_filter(self):
        resp = client.get("/api/v1/exceptions?filter=INVALID")
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data
        assert "error" in data["detail"]


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class TestTransactions:
    def test_explain_matched(self):
        resp = client.get("/api/v1/transactions/ORD-10001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "MATCHED"
        assert data["txn_id"] == "ORD-10001"

    def test_explain_exception(self):
        resp = client.get("/api/v1/transactions/ORD-10071")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "EXCEPTION"
        assert data["exception_type"] == "MISSING_SETTLEMENT"

    def test_explain_not_found(self):
        resp = client.get("/api/v1/transactions/ORD-99999")
        assert resp.status_code == 404

    def test_matched_has_bank_settlement(self):
        resp = client.get("/api/v1/transactions/ORD-10001")
        data = resp.json()
        assert data["bank_settlement"] is not None
        assert "utr" in data["bank_settlement"]

    def test_exception_has_evidence(self):
        resp = client.get("/api/v1/transactions/ORD-10071")
        data = resp.json()
        assert "evidence" in data
        assert "reason" in data


# ---------------------------------------------------------------------------
# Cash Position
# ---------------------------------------------------------------------------

class TestCashPosition:
    def test_cash_position_returns(self):
        resp = client.get("/api/v1/cash-position")
        assert resp.status_code == 200
        data = resp.json()
        assert "missing_settlement" in data
        assert "orphan_ledger" in data
        assert "total_unreconciled_inr" in data

    def test_cash_position_has_components(self):
        resp = client.get("/api/v1/cash-position")
        data = resp.json()
        assert data["missing_settlement"]["count"] > 0
        assert data["orphan_ledger"]["count"] > 0


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

class TestForecast:
    def test_forecast_returns(self):
        resp = client.get("/api/v1/forecast")
        assert resp.status_code == 200
        data = resp.json()
        assert data["horizon_days"] == 14
        assert "total_forecast_inr" in data
        assert "entries" in data

    def test_forecast_custom_horizon(self):
        resp = client.get("/api/v1/forecast?horizon_days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert data["horizon_days"] == 7

    def test_forecast_has_by_type(self):
        resp = client.get("/api/v1/forecast")
        data = resp.json()
        assert "by_exception_type" in data


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class TestReports:
    def test_reconciliation_report(self):
        resp = client.get("/api/v1/reports/reconciliation")
        assert resp.status_code == 200
        data = resp.json()
        assert "match_rates" in data
        assert "record_counts" in data
        assert "ground_truth_comparison" in data

    def test_report_match_rates(self):
        resp = client.get("/api/v1/reports/reconciliation")
        data = resp.json()
        mr = data["match_rates"]
        assert mr["deterministic"]["rate_pct"] == "73.75%"
        assert mr["final"]["rate_pct"] == "87.50%"
        assert mr["improvement_pp"] == "+13.75pp"


# ---------------------------------------------------------------------------
# Runs (demo)
# ---------------------------------------------------------------------------

class TestRuns:
    def test_runs_demo(self):
        resp = client.post("/api/v1/runs/demo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["match_rate"] == "87.50%"
        assert data["exceptions"] == 24


# ---------------------------------------------------------------------------
# Chat (without LLM — verifies endpoint structure)
# ---------------------------------------------------------------------------

class TestChat:
    def test_chat_no_question(self):
        resp = client.post("/api/v1/chat", json={})
        assert resp.status_code == 422  # validation error

    def test_chat_empty_question(self):
        resp = client.post("/api/v1/chat", json={"question": ""})
        assert resp.status_code == 422  # min_length=1

    def test_chat_no_provider_configured(self, monkeypatch):
        # Without API keys, this should return 503
        monkeypatch.setenv("GROQ_API_KEY", "")
        monkeypatch.setenv("GEMINI_API_KEY", "")
        resp = client.post("/api/v1/chat", json={"question": "What is the match rate?"})
        assert resp.status_code == 503
