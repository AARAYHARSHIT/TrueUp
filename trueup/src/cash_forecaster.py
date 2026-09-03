"""Cash flow forecaster for TrueUp (stretch goal).

Projects near-term inflows from unsettled transactions by learning settlement
lag patterns from matched transactions and applying them to exceptions.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

from src.data_generator import DATA_DIR
from src.deterministic_matcher import load_sources, match_exact, build_summary
from src.fuzzy_matcher import match_fuzzy
from src.schemas import MatchPass, RecordSource, MatchResult
from src.exception_classifier import (
    classify_exceptions,
    build_exceptions_report,
    ExceptionRecord,
    ExceptionType,
)


logger = logging.getLogger(__name__)

FORECAST_HORIZON_DAYS = 14

# ---------------------------------------------------------------------------
# Pipeline data loader (lazy, cached per-process)
# ---------------------------------------------------------------------------
_PIPELINE_CACHE: Optional[dict] = None


def _load_pipeline() -> dict:
    """Run the full pipeline once and cache the results for the forecaster."""
    global _PIPELINE_CACHE
    if _PIPELINE_CACHE is not None:
        return _PIPELINE_CACHE

    gateway, bank, ledger = load_sources(DATA_DIR)
    det_matched, det_unmatched = match_exact(gateway, bank, ledger)

    by_src: dict = defaultdict(list)
    for u in det_unmatched:
        by_src[u.source].append(u)

    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    all_matched = det_matched + fuzzy_matched
    exceptions = classify_exceptions(fuzzy_unmatched, gateway, bank, ledger)
    exc_report = build_exceptions_report(
        exceptions, len(gateway), len(bank), len(ledger))

    _PIPELINE_CACHE = {
        "gateway": gateway,
        "bank": bank,
        "ledger": ledger,
        "all_matched": all_matched,
        "exc_report": exc_report,
    }
    return _PIPELINE_CACHE


@dataclass
class ForecastEntry:
    forecast_date: date
    order_id: str
    amount: Decimal
    confidence: float
    reason: str
    source_exception_type: str


@dataclass
class CashForecast:
    generated_at: str
    horizon_days: int
    total_forecast_inr: Decimal
    entries: list[ForecastEntry]
    by_date: dict[str, Decimal]
    by_exception_type: dict[str, Decimal]


def _learn_settlement_patterns(matched: list[MatchResult]) -> dict[int, float]:
    """Learn settlement lag distribution from matched transactions.
    
    Returns a mapping of lag_days -> probability (normalized).
    """
    lag_counts: dict[int, int] = defaultdict(int)
    total = 0
    
    for m in matched:
        if m.date_lag_days is not None and m.date_lag_days >= 0:
            lag_counts[m.date_lag_days] += 1
            total += 1
    
    if total == 0:
        return {0: 0.4, 1: 0.3, 2: 0.2, 3: 0.1}
    
    return {lag: count / total for lag, count in lag_counts.items()}


def _get_unreconciled_exceptions() -> list[ExceptionRecord]:
    """Load exceptions from the pipeline cache."""
    pipeline = _load_pipeline()
    exceptions = pipeline["exc_report"]["exceptions"]
    
    result = []
    for exc_dict in exceptions:
        er = ExceptionRecord(
            exception_id=exc_dict["exception_id"],
            type=exc_dict["type"],
            source=exc_dict["source"],
            record_id=exc_dict["record_id"],
            amount=exc_dict.get("amount"),
            date=exc_dict.get("date"),
            reason=exc_dict["reason"],
            evidence=exc_dict.get("evidence", {}),
            linked_record_ids=exc_dict.get("linked_record_ids", []),
            event_key=exc_dict.get("event_key", ""),
            method=exc_dict.get("method", "exception_classifier"),
        )
        result.append(er)
    return result


def _forecast_missing_settlement(
    exc: ExceptionRecord,
    lag_dist: dict[int, float],
    base_date: date,
) -> list[ForecastEntry]:
    """Forecast cash inflow for a MISSING_SETTLEMENT exception.
    
    These are gateway transactions that were captured but never settled.
    We use the learned settlement lag distribution to project when the
    bank settlement might arrive.
    """
    if exc.amount is None:
        return []
    
    amount = Decimal(exc.amount)
    txn_date = date.fromisoformat(exc.date) if exc.date else base_date
    
    entries = []
    for lag_days, prob in sorted(lag_dist.items()):
        forecast_date = txn_date + timedelta(days=lag_days)
        if (forecast_date - base_date).days < 0:
            continue
        if (forecast_date - base_date).days > FORECAST_HORIZON_DAYS:
            continue
        
        confidence = prob * 0.7
        entries.append(ForecastEntry(
            forecast_date=forecast_date,
            order_id=exc.record_id,
            amount=amount,
            confidence=round(confidence, 3),
            reason=f"MISSING_SETTLEMENT: gateway captured, projecting {lag_days}-day lag (p={prob:.1%})",
            source_exception_type=exc.type,
        ))
    return entries


def _forecast_batch_settlement(
    exc: ExceptionRecord,
    lag_dist: dict[int, float],
    base_date: date,
) -> list[ForecastEntry]:
    """Forecast cash inflow for a BATCH_SETTLEMENT exception.
    
    These are gateway transactions that are part of a batch payout.
    The batch may settle as a unit. We project based on the batch payout date
    if known, or use the general lag distribution.
    """
    if exc.amount is None:
        return []
    
    amount = Decimal(exc.amount)
    txn_date = date.fromisoformat(exc.date) if exc.date else base_date
    
    batch_utr = exc.evidence.get("batch_utr")
    payout_amount = exc.evidence.get("payout")
    
    entries = []
    if batch_utr:
        for lag_days, prob in sorted(lag_dist.items()):
            forecast_date = txn_date + timedelta(days=lag_days)
            if (forecast_date - base_date).days < 0:
                continue
            if (forecast_date - base_date).days > FORECAST_HORIZON_DAYS:
                continue
            
            confidence = prob * 0.5
            entries.append(ForecastEntry(
                forecast_date=forecast_date,
                order_id=exc.record_id,
                amount=amount,
                confidence=round(confidence, 3),
                reason=f"BATCH_SETTLEMENT: member of batch {batch_utr}, projecting {lag_days}-day lag",
                source_exception_type=exc.type,
            ))
    else:
        for lag_days, prob in sorted(lag_dist.items()):
            forecast_date = txn_date + timedelta(days=lag_days)
            if (forecast_date - base_date).days < 0:
                continue
            if (forecast_date - base_date).days > FORECAST_HORIZON_DAYS:
                continue
            
            confidence = prob * 0.4
            entries.append(ForecastEntry(
                forecast_date=forecast_date,
                order_id=exc.record_id,
                amount=amount,
                confidence=round(confidence, 3),
                reason=f"BATCH_SETTLEMENT: batch member, projecting {lag_days}-day lag",
                source_exception_type=exc.type,
            ))
    return entries


def _forecast_orphan_ledger(
    exc: ExceptionRecord,
    lag_dist: dict[int, float],
    base_date: date,
) -> list[ForecastEntry]:
    """Forecast cash inflow for an ORPHAN_LEDGER exception.
    
    These are ledger entries with no matching payment. Low confidence
    since there's no gateway transaction to anchor the forecast.
    """
    if exc.amount is None:
        return []
    
    amount = Decimal(exc.amount)
    entry_date = date.fromisoformat(exc.date) if exc.date else base_date
    
    entries = []
    for lag_days, prob in sorted(lag_dist.items()):
        forecast_date = entry_date + timedelta(days=lag_days)
        if (forecast_date - base_date).days < 0:
            continue
        if (forecast_date - base_date).days > FORECAST_HORIZON_DAYS:
            continue
        
        confidence = prob * 0.2
        entries.append(ForecastEntry(
            forecast_date=forecast_date,
            order_id=exc.record_id,
            amount=amount,
            confidence=round(confidence, 3),
            reason=f"ORPHAN_LEDGER: no payment trail, speculative {lag_days}-day lag",
            source_exception_type=exc.type,
        ))
    return entries


def generate_cash_forecast(horizon_days: int = FORECAST_HORIZON_DAYS) -> CashForecast:
    """Generate a cash flow forecast from unreconciled transactions.
    
    Args:
        horizon_days: How many days forward to forecast (default 14).
        
    Returns:
        CashForecast with projected inflows by date and exception type.
    """
    pipeline = _load_pipeline()
    matched = pipeline["all_matched"]
    exceptions = _get_unreconciled_exceptions()

    # Use the earliest exception date as base_date so all forecast dates
    # (txn_date + lag) are >= base_date. This makes the forecaster work
    # on historical synthetic data for demos.
    exc_dates: list[date] = []
    for exc in exceptions:
        if exc.date:
            try:
                exc_dates.append(date.fromisoformat(exc.date))
            except (ValueError, TypeError):
                pass
    base_date = min(exc_dates) if exc_dates else date.today()

    lag_dist = _learn_settlement_patterns(matched)
    
    all_entries: list[ForecastEntry] = []
    
    for exc in exceptions:
        if exc.type == ExceptionType.MISSING_SETTLEMENT:
            all_entries.extend(_forecast_missing_settlement(exc, lag_dist, base_date))
        elif exc.type == ExceptionType.BATCH_SETTLEMENT:
            all_entries.extend(_forecast_batch_settlement(exc, lag_dist, base_date))
        elif exc.type == ExceptionType.ORPHAN_LEDGER:
            all_entries.extend(_forecast_orphan_ledger(exc, lag_dist, base_date))
    
    all_entries.sort(key=lambda e: (e.forecast_date, -e.confidence))
    
    by_date: dict[str, Decimal] = defaultdict(Decimal)
    by_type: dict[str, Decimal] = defaultdict(Decimal)
    total = Decimal("0")
    
    for entry in all_entries:
        date_key = entry.forecast_date.isoformat()
        by_date[date_key] += entry.amount
        by_type[entry.source_exception_type] += entry.amount
        total += entry.amount
    
    return CashForecast(
        generated_at=base_date.isoformat(),
        horizon_days=horizon_days,
        total_forecast_inr=total,
        entries=all_entries,
        by_date=dict(by_date),
        by_exception_type=dict(by_type),
    )


def format_forecast(forecast: CashForecast) -> str:
    """Format forecast as a human-readable string."""
    lines = []
    lines.append(f"Cash Flow Forecast (next {forecast.horizon_days} days)")
    lines.append(f"Generated: {forecast.generated_at}")
    lines.append(f"Total projected inflow: INR {forecast.total_forecast_inr:,.2f}")
    lines.append("")
    
    lines.append("By date:")
    for d in sorted(forecast.by_date.keys()):
        lines.append(f"  {d}: INR {forecast.by_date[d]:,.2f}")
    lines.append("")
    
    lines.append("By exception type:")
    for t, amt in sorted(forecast.by_exception_type.items(), key=lambda x: -x[1]):
        lines.append(f"  {t}: INR {amt:,.2f}")
    lines.append("")
    
    lines.append("Detail (top 20):")
    for entry in forecast.entries[:20]:
        lines.append(
            f"  {entry.forecast_date} | {entry.order_id} | "
            f"INR {entry.amount:,.2f} | conf={entry.confidence:.2f} | "
            f"[{entry.source_exception_type}]"
        )
    
    return "\n".join(lines)


def main() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    
    forecast = generate_cash_forecast()
    print(format_forecast(forecast))


if __name__ == "__main__":
    main()