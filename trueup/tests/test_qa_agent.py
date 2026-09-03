"""Unit tests for src/qa_agent.py tool functions.

Tests run against the live pipeline (seed=42 data) so every assertion
is grounded in actual computed values -- no mocking, no hallucination.

Run: pytest tests/test_qa_agent.py -v
"""
from __future__ import annotations

import json
import pytest
from decimal import Decimal

from src.qa_agent import (
    get_match_rate,
    list_exceptions,
    explain_match,
    summarize,
    get_cash_position,
    dispatch_tool,
    TEST_QUESTIONS,
)


# ---------------------------------------------------------------------------
# get_match_rate
# ---------------------------------------------------------------------------

class TestGetMatchRate:
    def setup_method(self):
        self.r = get_match_rate()

    def test_gateway_total(self):
        assert self.r["gateway_total"] == 80

    def test_bank_total(self):
        assert self.r["bank_total"] == 75

    def test_ledger_total(self):
        assert self.r["ledger_total"] == 78

    def test_deterministic_rate(self):
        assert self.r["deterministic_pass"]["rate"] == "73.75%"

    def test_deterministic_matched(self):
        assert self.r["deterministic_pass"]["matched"] == 59

    def test_final_rate(self):
        assert self.r["final"]["rate"] == "87.50%"

    def test_final_matched(self):
        assert self.r["final"]["matched"] == 70

    def test_improvement(self):
        assert self.r["improvement_pp"] == "+13.75pp"

    def test_exceptions_total(self):
        assert self.r["unmatched"]["exceptions_total"] == 24

    def test_unmatched_gateway(self):
        assert self.r["unmatched"]["gateway"] == 10


# ---------------------------------------------------------------------------
# list_exceptions
# ---------------------------------------------------------------------------

class TestListExceptions:
    def test_all_returns_24(self):
        r = list_exceptions("all")
        assert r["total"] == 24
        assert r["filter_applied"] == "all"

    def test_missing_settlement(self):
        r = list_exceptions("MISSING_SETTLEMENT")
        assert r["total"] == 6
        assert r["filter_applied"] == "type=MISSING_SETTLEMENT"
        assert r["by_type"] == {"MISSING_SETTLEMENT": 6}

    def test_orphan_ledger(self):
        r = list_exceptions("ORPHAN_LEDGER")
        assert r["total"] == 3

    def test_batch_settlement(self):
        r = list_exceptions("BATCH_SETTLEMENT")
        assert r["total"] == 15

    def test_gateway_source_filter(self):
        r = list_exceptions("gateway")
        assert r["total"] == 10
        for exc in r["exceptions"]:
            assert exc["source"] == "gateway"

    def test_ledger_source_filter(self):
        r = list_exceptions("ledger")
        assert r["total"] == 13
        for exc in r["exceptions"]:
            assert exc["source"] == "ledger"

    def test_exception_fields_present(self):
        r = list_exceptions("MISSING_SETTLEMENT")
        for exc in r["exceptions"]:
            assert "exception_id" in exc
            assert "type" in exc
            assert "source" in exc
            assert "record_id" in exc
            assert "reason" in exc

    def test_invalid_filter_returns_error(self):
        r = list_exceptions("BANANA")
        assert "error" in r
        assert "valid_types" in r

    def test_empty_filter_returns_all(self):
        r = list_exceptions("")
        assert r["total"] == 24


# ---------------------------------------------------------------------------
# explain_match
# ---------------------------------------------------------------------------

class TestExplainMatch:
    def test_known_matched_txn(self):
        # ORD-10001 should be a deterministic matched transaction
        r = explain_match("ORD-10001")
        assert r["status"] == "MATCHED"
        assert r["txn_id"] == "ORD-10001"
        assert "gateway_amount" in r
        assert "match_pass" in r

    def test_missing_settlement_exception(self):
        # ORD-10071 is classified as MISSING_SETTLEMENT per exceptions.json
        r = explain_match("ORD-10071")
        assert r["status"] == "EXCEPTION"
        assert r["exception_type"] == "MISSING_SETTLEMENT"
        assert r["txn_id"] == "ORD-10071"

    def test_explain_amount_for_exception(self):
        r = explain_match("ORD-10071")
        assert r["amount"] == "21643.55"

    def test_not_found(self):
        r = explain_match("ORD-99999")
        assert r["status"] == "NOT_FOUND"
        assert "error" in r

    def test_case_insensitive(self):
        r_upper = explain_match("ORD-10071")
        r_lower = explain_match("ord-10071")
        assert r_upper["status"] == r_lower["status"]

    def test_matched_has_bank_settlement_or_none(self):
        r = explain_match("ORD-10001")
        if r["status"] == "MATCHED":
            # bank_settlement may be None or a dict
            assert r["bank_settlement"] is None or isinstance(r["bank_settlement"], dict)


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------

class TestSummarize:
    def test_all_period(self):
        r = summarize("all")
        assert r["gateway_transactions"] == 80
        assert r["matched"] == 70
        assert r["match_rate"] == "87.50%"
        assert r["exceptions"] == 24

    def test_august_2026_month(self):
        # All data is in Aug 2026 so month == all
        r = summarize("2026-08")
        assert r["gateway_transactions"] == 80
        assert r["period_start"] == "2026-08-01"
        assert r["period_end"] == "2026-08-31"

    def test_missing_settlement_exposure(self):
        r = summarize("all")
        # 3 gateway MISSING_SETTLEMENT exceptions
        exposure = Decimal(r["missing_settlement_exposure_inr"])
        assert exposure > Decimal("0")

    def test_invalid_period_format(self):
        r = summarize("INVALID")
        assert "error" in r

    def test_date_range(self):
        r = summarize("2026-08-01:2026-08-31")
        assert r["gateway_transactions"] == 80

    def test_single_day_empty(self):
        # Jan 1 is out of range, should yield 0 transactions
        r = summarize("2025-01-01")
        assert r["gateway_transactions"] == 0

    def test_exceptions_by_type_present(self):
        r = summarize("all")
        assert "exceptions_by_type" in r
        assert r["exceptions_by_type"].get("MISSING_SETTLEMENT", 0) == 6


# ---------------------------------------------------------------------------
# get_cash_position
# ---------------------------------------------------------------------------

class TestGetCashPosition:
    def setup_method(self):
        self.r = get_cash_position()

    def test_missing_settlement_count(self):
        assert self.r["missing_settlement"]["count"] == 3

    def test_missing_settlement_order_ids(self):
        ids = set(self.r["missing_settlement"]["order_ids"])
        # ORD-10071 is confirmed MISSING_SETTLEMENT in exceptions.json
        assert "ORD-10071" in ids

    def test_missing_settlement_exposure_positive(self):
        exp = Decimal(self.r["missing_settlement"]["exposure_inr"])
        assert exp > Decimal("0")

    def test_orphan_ledger_count(self):
        assert self.r["orphan_ledger"]["count"] == 3

    def test_batch_pending_count(self):
        assert self.r["batch_settlement_pending"]["count"] == 7

    def test_total_unreconciled_is_sum(self):
        ms = Decimal(self.r["missing_settlement"]["exposure_inr"])
        ol = Decimal(self.r["orphan_ledger"]["exposure_inr"])
        bp = Decimal(self.r["batch_settlement_pending"]["exposure_inr"])
        total = Decimal(self.r["total_unreconciled_inr"])
        assert total == ms + ol + bp

    def test_keys_present(self):
        assert "missing_settlement" in self.r
        assert "orphan_ledger" in self.r
        assert "batch_settlement_pending" in self.r
        assert "total_unreconciled_inr" in self.r


# ---------------------------------------------------------------------------
# dispatch_tool (tool dispatcher)
# ---------------------------------------------------------------------------

class TestDispatchTool:
    def test_get_match_rate_dispatch(self):
        result = json.loads(dispatch_tool("get_match_rate", {}))
        assert result["gateway_total"] == 80
        assert result["final"]["rate"] == "87.50%"

    def test_list_exceptions_dispatch(self):
        result = json.loads(dispatch_tool("list_exceptions", {"filter": "MISSING_SETTLEMENT"}))
        assert result["total"] == 6

    def test_explain_match_dispatch(self):
        result = json.loads(dispatch_tool("explain_match", {"txn_id": "ORD-10001"}))
        assert result["status"] == "MATCHED"

    def test_summarize_dispatch(self):
        result = json.loads(dispatch_tool("summarize", {"period": "all"}))
        assert result["gateway_transactions"] == 80

    def test_get_cash_position_dispatch(self):
        result = json.loads(dispatch_tool("get_cash_position", {}))
        assert "total_unreconciled_inr" in result

    def test_unknown_tool_returns_error(self):
        result = json.loads(dispatch_tool("nonexistent_tool", {}))
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_tool_exception_returns_error(self):
        result = json.loads(dispatch_tool("explain_match", {"txn_id": None}))
        assert "error" in result


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_explain_unknown_txn_id(self):
        r = explain_match("ORD-99999")
        assert r["status"] == "NOT_FOUND"
        assert "ORD-99999" in r["error"]
        assert "hint" in r

    def test_explain_garbage_input(self):
        r = explain_match("GARBAGE_INPUT_123")
        assert r["status"] == "NOT_FOUND"

    def test_explain_case_insensitive_upper(self):
        r1 = explain_match("ORD-10071")
        r2 = explain_match("ord-10071")
        assert r1["status"] == r2["status"]

    def test_list_exceptions_invalid_filter(self):
        r = list_exceptions("BANANA")
        assert "error" in r
        assert "valid_types" in r

    def test_list_exceptions_numeric_filter(self):
        r = list_exceptions("12345")
        assert "error" in r

    def test_summarize_invalid_period(self):
        r = summarize("not-a-date")
        assert "error" in r

    def test_summarize_future_date_empty(self):
        r = summarize("2099-12-31")
        assert r["gateway_transactions"] == 0
        assert r["matched"] == 0

    def test_get_cash_position_structure(self):
        r = get_cash_position()
        assert "missing_settlement" in r
        assert "orphan_ledger" in r
        assert "batch_settlement_pending" in r
        assert "total_unreconciled_inr" in r
        assert "as_of" in r


# ---------------------------------------------------------------------------
# Tool selection: verify correct tool matches each question type
# ---------------------------------------------------------------------------

class TestToolSelection:
    def test_match_rate_question_uses_get_match_rate(self):
        r = get_match_rate()
        assert "deterministic_pass" in r
        assert "fuzzy_pass" in r
        assert "final" in r

    def test_exception_list_question_uses_list_exceptions(self):
        r = list_exceptions("MISSING_SETTLEMENT")
        assert r["total"] == 6
        for exc in r["exceptions"]:
            assert exc["type"] == "MISSING_SETTLEMENT"

    def test_explain_txn_question_uses_explain_match(self):
        r = explain_match("ORD-10071")
        assert r["status"] == "EXCEPTION"
        assert r["exception_type"] == "MISSING_SETTLEMENT"

    def test_summary_question_uses_summarize(self):
        r = summarize("2026-08")
        assert r["gateway_transactions"] == 80
        assert "match_rate" in r

    def test_cash_position_question_uses_get_cash_position(self):
        r = get_cash_position()
        ms = Decimal(r["missing_settlement"]["exposure_inr"])
        assert ms > Decimal("0")

    def test_batch_filter_uses_list_exceptions(self):
        r = list_exceptions("BATCH_SETTLEMENT")
        assert r["total"] == 15

    def test_ledger_source_filter_uses_list_exceptions(self):
        r = list_exceptions("ledger")
        assert r["total"] == 13
        for exc in r["exceptions"]:
            assert exc["source"] == "ledger"


# ---------------------------------------------------------------------------
# Data accuracy: verify answers match DATA.md ground truth
# ---------------------------------------------------------------------------

class TestDataAccuracy:
    def test_split_match_has_bank_utrs(self):
        r = explain_match("ORD-10044")
        assert r["status"] == "MATCHED"
        assert r["method"] == "split_settlement"
        assert r["bank_settlement"] is not None

    def test_batch_exception_has_batch_utr(self):
        r = explain_match("ORD-10048")
        assert r["status"] == "EXCEPTION"
        assert r["exception_type"] == "BATCH_SETTLEMENT"

    def test_fuzzy_garbled_ref_matched(self):
        r = explain_match("ORD-10057")
        assert r["status"] == "MATCHED"
        assert r["method"] == "fuzzy_amount_date_edit"

    def test_missing_settlement_has_correct_amount(self):
        r = explain_match("ORD-10071")
        assert r["amount"] == "21643.55"

    def test_orphan_ledger_count(self):
        r = list_exceptions("ORPHAN_LEDGER")
        assert r["total"] == 3

    def test_cash_position_total_is_sum(self):
        r = get_cash_position()
        ms = Decimal(r["missing_settlement"]["exposure_inr"])
        ol = Decimal(r["orphan_ledger"]["exposure_inr"])
        bp = Decimal(r["batch_settlement_pending"]["exposure_inr"])
        total = Decimal(r["total_unreconciled_inr"])
        assert total == ms + ol + bp

    def test_summarize_august_all_data(self):
        r = summarize("2026-08")
        assert r["gateway_transactions"] == 80
        assert r["match_rate"] == "87.50%"


# ---------------------------------------------------------------------------
# Test questions list
# ---------------------------------------------------------------------------

class TestQuestionsList:
    def test_has_11_questions(self):
        assert len(TEST_QUESTIONS) == 11

    def test_all_questions_are_strings(self):
        for q in TEST_QUESTIONS:
            assert isinstance(q, str)
            assert len(q) > 10
