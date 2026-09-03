"""Tests for cash_forecaster.py."""

from decimal import Decimal
from datetime import date, timedelta

import pytest

from src.cash_forecaster import (
    generate_cash_forecast,
    _learn_settlement_patterns,
    _forecast_missing_settlement,
    _forecast_batch_settlement,
    _forecast_orphan_ledger,
    CashForecast,
    ForecastEntry,
)
from src.schemas import MatchResult, MatchPass, GatewayTransaction, BankSettlement, MerchantLedger


class TestLearnSettlementPatterns:
    def test_empty_matched_returns_defaults(self):
        dist = _learn_settlement_patterns([])
        assert dist == {0: 0.4, 1: 0.3, 2: 0.2, 3: 0.1}

    def test_learns_from_matched_data(self):
        gw = GatewayTransaction(
            order_id="ORD-10001",
            amount=Decimal("1000.00"),
            txn_date=date(2026, 8, 1),
            status="CAPTURED",
            gateway_fee=Decimal("0"),
        )
        matched = [
            MatchResult(
                gateway_txn=gw,
                bank_settlement=BankSettlement(
                    utr="UTR-50001",
                    settlement_amount=Decimal("1000.00"),
                    settlement_date=date(2026, 8, 1),
                    order_id_ref="ORD-10001",
                ),
                merchant_ledger=None,
                match_pass=MatchPass.DETERMINISTIC,
                method="exact_order_id",
                confidence=1.0,
                amount_agrees=True,
                date_lag_days=0,
            ),
            MatchResult(
                gateway_txn=gw,
                bank_settlement=BankSettlement(
                    utr="UTR-50002",
                    settlement_amount=Decimal("1000.00"),
                    settlement_date=date(2026, 8, 2),
                    order_id_ref="ORD-10002",
                ),
                merchant_ledger=None,
                match_pass=MatchPass.DETERMINISTIC,
                method="exact_order_id",
                confidence=1.0,
                amount_agrees=True,
                date_lag_days=1,
            ),
            MatchResult(
                gateway_txn=gw,
                bank_settlement=BankSettlement(
                    utr="UTR-50003",
                    settlement_amount=Decimal("1000.00"),
                    settlement_date=date(2026, 8, 3),
                    order_id_ref="ORD-10003",
                ),
                merchant_ledger=None,
                match_pass=MatchPass.DETERMINISTIC,
                method="exact_order_id",
                confidence=1.0,
                amount_agrees=True,
                date_lag_days=2,
            ),
        ]
        dist = _learn_settlement_patterns(matched)
        assert dist[0] == pytest.approx(1/3)
        assert dist[1] == pytest.approx(1/3)
        assert dist[2] == pytest.approx(1/3)


class TestForecastMissingSettlement:
    def test_returns_entries_for_valid_exception(self):
        from src.exception_classifier import ExceptionRecord, ExceptionType
        
        exc = ExceptionRecord(
            exception_id="EXC-0001",
            type=ExceptionType.MISSING_SETTLEMENT,
            source="gateway",
            record_id="ORD-10070",
            amount="1000.00",
            date="2026-08-15",
            reason="missing settlement",
            evidence={},
            linked_record_ids=[],
            event_key="MISS-01",
        )
        lag_dist = {0: 0.4, 1: 0.3, 2: 0.2, 3: 0.1}
        base_date = date(2026, 8, 16)
        
        entries = _forecast_missing_settlement(exc, lag_dist, base_date)

        # lag=0 gives forecast_date=Aug 15 which is before base_date=Aug 16 -> skipped
        assert len(entries) == 3
        for e in entries:
            assert e.order_id == "ORD-10070"
            assert e.amount == Decimal("1000.00")
            assert e.confidence > 0
            assert e.source_exception_type == "MISSING_SETTLEMENT"

    def test_skips_past_dates(self):
        from src.exception_classifier import ExceptionRecord, ExceptionType
        
        exc = ExceptionRecord(
            exception_id="EXC-0001",
            type=ExceptionType.MISSING_SETTLEMENT,
            source="gateway",
            record_id="ORD-10070",
            amount="1000.00",
            date="2026-08-01",
            reason="missing settlement",
            evidence={},
            linked_record_ids=[],
            event_key="MISS-01",
        )
        lag_dist = {0: 0.4, 1: 0.3, 2: 0.2, 3: 0.1}
        base_date = date(2026, 8, 20)
        
        entries = _forecast_missing_settlement(exc, lag_dist, base_date)
        
        for e in entries:
            assert e.forecast_date >= base_date


class TestForecastBatchSettlement:
    def test_returns_entries_with_batch_info(self):
        from src.exception_classifier import ExceptionRecord, ExceptionType
        
        exc = ExceptionRecord(
            exception_id="EXC-0001",
            type=ExceptionType.BATCH_SETTLEMENT,
            source="gateway",
            record_id="ORD-10048",
            amount="24033.62",
            date="2026-08-15",
            reason="batch settlement",
            evidence={"batch_utr": "UTR-50052", "payout": "53265.14"},
            linked_record_ids=["UTR-50052"],
            event_key="BATCH-01",
        )
        lag_dist = {0: 0.4, 1: 0.3, 2: 0.2, 3: 0.1}
        base_date = date(2026, 8, 16)
        
        entries = _forecast_batch_settlement(exc, lag_dist, base_date)

        # lag=0 gives forecast_date=Aug 15 which is before base_date=Aug 16 -> skipped
        assert len(entries) == 3
        for e in entries:
            assert e.order_id == "ORD-10048"
            assert "batch" in e.reason.lower()


class TestForecastOrphanLedger:
    def test_returns_entries_with_low_confidence(self):
        from src.exception_classifier import ExceptionRecord, ExceptionType
        
        exc = ExceptionRecord(
            exception_id="EXC-0001",
            type=ExceptionType.ORPHAN_LEDGER,
            source="ledger",
            record_id="ORD-10073",
            amount="23940.06",
            date="2026-08-15",
            reason="orphan ledger",
            evidence={},
            linked_record_ids=[],
            event_key="ORPHAN-01",
        )
        lag_dist = {0: 0.4, 1: 0.3, 2: 0.2, 3: 0.1}
        base_date = date(2026, 8, 16)
        
        entries = _forecast_orphan_ledger(exc, lag_dist, base_date)

        # lag=0 gives forecast_date=Aug 15 which is before base_date=Aug 16 -> skipped
        assert len(entries) == 3
        for e in entries:
            assert e.order_id == "ORD-10073"
            assert e.confidence < 0.3
            assert "orphan" in e.reason.lower()


class TestGenerateCashForecast:
    def test_generates_forecast(self):
        forecast = generate_cash_forecast(horizon_days=14)
        
        assert isinstance(forecast, CashForecast)
        assert forecast.horizon_days == 14
        assert forecast.total_forecast_inr >= Decimal("0")
        assert isinstance(forecast.entries, list)
        assert isinstance(forecast.by_date, dict)
        assert isinstance(forecast.by_exception_type, dict)
        assert "MISSING_SETTLEMENT" in forecast.by_exception_type or len(forecast.by_exception_type) == 0

    def test_forecast_entries_sorted_by_date_and_confidence(self):
        forecast = generate_cash_forecast(horizon_days=14)
        
        if len(forecast.entries) >= 2:
            for i in range(len(forecast.entries) - 1):
                e1 = forecast.entries[i]
                e2 = forecast.entries[i + 1]
                assert e1.forecast_date <= e2.forecast_date
                if e1.forecast_date == e2.forecast_date:
                    assert e1.confidence >= e2.confidence


class TestCashForecastTool:
    def test_tool_returns_valid_structure(self):
        from src.qa_agent import get_cash_forecast
        
        result = get_cash_forecast(horizon_days=7)
        
        assert "generated_at" in result
        assert "horizon_days" in result
        assert "total_forecast_inr" in result
        assert "by_date" in result
        assert "by_exception_type" in result
        assert "entries" in result
        assert result["horizon_days"] == 7
        assert isinstance(result["entries"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])