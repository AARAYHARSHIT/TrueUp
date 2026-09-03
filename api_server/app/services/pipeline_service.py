"""Pipeline service for TrueUp API.

Wraps the existing trueup.src reconciliation engine and exposes it
through a service layer for the FastAPI routes. All business logic
comes from the existing engine -- no duplication.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Add trueup to path so we can import its modules
_TRUEUP_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "trueup"
if str(_TRUEUP_ROOT) not in sys.path:
    sys.path.insert(0, str(_TRUEUP_ROOT))

from src.deterministic_matcher import DATA_DIR, load_sources, match_exact, build_summary
from src.fuzzy_matcher import match_fuzzy
from src.schemas import RecordSource
from src.exception_classifier import (
    ExceptionRecord,
    ExceptionType,
    classify_exceptions,
    build_exceptions_report,
)
from src.cash_forecaster import generate_cash_forecast

# ---------------------------------------------------------------------------
# Pipeline cache (lazy, thread-safe)
# ---------------------------------------------------------------------------
_pipeline_lock = threading.Lock()
_PIPELINE_CACHE: Optional[dict] = None


def _load_pipeline() -> dict:
    """Run the full pipeline once and cache the results."""
    global _PIPELINE_CACHE
    if _PIPELINE_CACHE is not None:
        return _PIPELINE_CACHE

    with _pipeline_lock:
        if _PIPELINE_CACHE is not None:
            return _PIPELINE_CACHE

        gateway, bank, ledger = load_sources(DATA_DIR)
        det_matched, det_unmatched = match_exact(gateway, bank, ledger)
        det_summary = build_summary(
            det_matched, det_unmatched, len(gateway), len(bank), len(ledger)
        )

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
            exceptions, len(gateway), len(bank), len(ledger)
        )

        raw_exceptions: list[ExceptionRecord] = []
        for exc_dict in exc_report["exceptions"]:
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
            raw_exceptions.append(er)

        _PIPELINE_CACHE = {
            "gateway": gateway,
            "bank": bank,
            "ledger": ledger,
            "det_matched": det_matched,
            "det_unmatched": det_unmatched,
            "det_summary": det_summary,
            "fuzzy_matched": fuzzy_matched,
            "fuzzy_unmatched": fuzzy_unmatched,
            "all_matched": all_matched,
            "exceptions": raw_exceptions,
            "exc_report": exc_report,
        }
        return _PIPELINE_CACHE


def get_pipeline_data() -> dict:
    """Public accessor for the cached pipeline data."""
    return _load_pipeline()


def reload_pipeline() -> dict:
    """Force a pipeline reload (for /runs/demo)."""
    global _PIPELINE_CACHE
    with _pipeline_lock:
        _PIPELINE_CACHE = None
    return _load_pipeline()


# ---------------------------------------------------------------------------
# Tool implementations (mirror qa_agent.py exactly)
# ---------------------------------------------------------------------------

def get_match_rate() -> dict:
    """Return overall and per-pass match statistics."""
    p = _load_pipeline()
    gw_total = len(p["gateway"])
    det_n = len(p["det_matched"])
    final_n = len(p["all_matched"])
    det_rate = det_n / gw_total if gw_total else 0.0
    final_rate = final_n / gw_total if gw_total else 0.0
    improvement = final_rate - det_rate

    fuzzy_n = len(p["fuzzy_matched"])
    split_count = sum(1 for m in p["fuzzy_matched"] if m.method == "split_settlement")
    batch_count = sum(1 for m in p["fuzzy_matched"] if m.method == "batch_settlement")
    fuzzy_count = sum(1 for m in p["fuzzy_matched"] if m.method == "fuzzy_amount_date_edit")

    return {
        "gateway_total": gw_total,
        "bank_total": len(p["bank"]),
        "ledger_total": len(p["ledger"]),
        "deterministic_pass": {
            "matched": det_n,
            "rate": f"{det_rate * 100:.2f}%",
            "full_triples": p["det_summary"]["full_triples"],
            "amount_disagreements": p["det_summary"]["amount_disagreements"],
            "date_drifts": p["det_summary"]["date_drifts"],
        },
        "fuzzy_pass": {
            "additional_matched": fuzzy_n,
            "split_detected": split_count,
            "batch_detected": batch_count,
            "fuzzy_amount_date_edit": fuzzy_count,
        },
        "final": {
            "matched": final_n,
            "rate": f"{final_rate * 100:.2f}%",
        },
        "improvement_pp": f"{improvement * 100:+.2f}pp",
        "unmatched": {
            "gateway": gw_total - final_n,
            "exceptions_total": len(p["exceptions"]),
        },
    }


def list_exceptions(filter: str = "all") -> dict:
    """List exceptions with optional type or source filter."""
    p = _load_pipeline()
    raw = p["exc_report"]["exceptions"]
    filt = (filter or "all").strip().upper()

    valid_types = {t.upper() for t in ExceptionType.ALL}
    valid_sources = {"GATEWAY", "BANK", "LEDGER"}

    if filt in ("ALL", ""):
        filtered = raw
        filter_applied = "all"
    elif filt in valid_types:
        filtered = [e for e in raw if e["type"].upper() == filt]
        filter_applied = f"type={filt}"
    elif filt in valid_sources:
        filtered = [e for e in raw if e["source"].upper() == filt]
        filter_applied = f"source={filt.lower()}"
    else:
        return {
            "error": f"Unknown filter '{filter}'. Use an exception type, 'gateway', 'bank', 'ledger', or 'all'.",
            "valid_types": list(ExceptionType.ALL),
        }

    summary: dict[str, int] = {}
    for exc in filtered:
        summary[exc["type"]] = summary.get(exc["type"], 0) + 1

    return {
        "filter_applied": filter_applied,
        "total": len(filtered),
        "by_type": summary,
        "exceptions": [
            {
                "exception_id": e["exception_id"],
                "type": e["type"],
                "source": e["source"],
                "record_id": e["record_id"],
                "amount": e.get("amount"),
                "date": e.get("date"),
                "reason": e["reason"],
            }
            for e in filtered
        ],
    }


def explain_match(txn_id: str) -> dict:
    """Explain what happened to a specific gateway transaction."""
    p = _load_pipeline()
    tid = txn_id.strip().upper()

    # Check matched records first
    for m in p["all_matched"]:
        if m.gateway_txn.order_id.upper() == tid:
            result: dict = {
                "txn_id": m.gateway_txn.order_id,
                "status": "MATCHED",
                "match_pass": m.match_pass.value,
                "method": m.method,
                "confidence": m.confidence,
                "gateway_amount": str(m.gateway_txn.amount),
                "gateway_date": str(m.gateway_txn.txn_date),
                "gateway_fee": str(m.gateway_txn.gateway_fee),
                "amount_agrees": m.amount_agrees,
                "date_lag_days": m.date_lag_days,
                "bank_settlement": None,
                "merchant_ledger": None,
            }
            if m.bank_settlement:
                result["bank_settlement"] = {
                    "utr": m.bank_settlement.utr,
                    "settlement_amount": str(m.bank_settlement.settlement_amount),
                    "settlement_date": str(m.bank_settlement.settlement_date),
                }
            if m.merchant_ledger:
                result["merchant_ledger"] = {
                    "order_id": m.merchant_ledger.order_id,
                    "expected_amount": str(m.merchant_ledger.expected_amount),
                    "entry_date": str(m.merchant_ledger.entry_date),
                    "notes": m.merchant_ledger.notes,
                }
            return result

    # Check exception records
    for exc in p["exc_report"]["exceptions"]:
        if exc["record_id"].upper() == tid:
            return {
                "txn_id": tid,
                "status": "EXCEPTION",
                "exception_id": exc["exception_id"],
                "exception_type": exc["type"],
                "source": exc["source"],
                "amount": exc.get("amount"),
                "date": exc.get("date"),
                "reason": exc["reason"],
                "evidence": exc.get("evidence", {}),
                "linked_record_ids": exc.get("linked_record_ids", []),
            }

    # Not found at all
    all_gw_ids_upper = {g.order_id.upper() for g in p["gateway"]}
    if tid in all_gw_ids_upper:
        return {
            "txn_id": tid,
            "status": "ERROR",
            "error": "Transaction exists but was not indexed -- pipeline bug.",
        }
    return {
        "txn_id": tid,
        "status": "NOT_FOUND",
        "error": f"No gateway transaction with order_id '{txn_id}' found in the dataset.",
        "hint": "Valid IDs are ORD-10001 through ORD-10080.",
    }


def summarize(period: str = "all") -> dict:
    """Summarize reconciliation results for a date range or period label."""
    import calendar
    from datetime import date

    p = _load_pipeline()
    period = (period or "all").strip()

    start_date = None
    end_date = None

    if period.lower() != "all":
        try:
            if ":" in period:
                parts = period.split(":")
                start_date = date.fromisoformat(parts[0].strip())
                end_date = date.fromisoformat(parts[1].strip())
            elif len(period) == 7:
                year, month = int(period[:4]), int(period[5:7])
                start_date = date(year, month, 1)
                last_day = calendar.monthrange(year, month)[1]
                end_date = date(year, month, last_day)
            elif len(period) == 10:
                start_date = date.fromisoformat(period)
                end_date = start_date
            else:
                return {
                    "error": (
                        f"Unrecognised period format '{period}'. "
                        "Use 'all', 'YYYY-MM', 'YYYY-MM-DD', or 'YYYY-MM-DD:YYYY-MM-DD'."
                    )
                }
        except (ValueError, IndexError):
            return {"error": f"Invalid period '{period}'."}

    def in_range(d) -> bool:
        if start_date is None:
            return True
        if d is None:
            return False
        try:
            dt = date.fromisoformat(str(d))
            return start_date <= dt <= end_date
        except ValueError:
            return False

    matched_in = [m for m in p["all_matched"] if in_range(str(m.gateway_txn.txn_date))]
    exc_in = [e for e in p["exc_report"]["exceptions"] if in_range(e.get("date"))]
    gw_in = [g for g in p["gateway"] if in_range(str(g.txn_date))]
    from decimal import Decimal
    gw_vol = sum(g.amount for g in gw_in)
    matched_rate = len(matched_in) / len(gw_in) if gw_in else 0.0

    exc_by_type: dict[str, int] = {}
    for e in exc_in:
        exc_by_type[e["type"]] = exc_by_type.get(e["type"], 0) + 1

    missing_amt = sum(
        Decimal(str(e.get("amount", "0") or "0"))
        for e in exc_in
        if e["type"] == ExceptionType.MISSING_SETTLEMENT and e["source"] == "gateway"
    )

    return {
        "period": period,
        "period_start": str(start_date) if start_date else "dataset start",
        "period_end": str(end_date) if end_date else "dataset end",
        "gateway_transactions": len(gw_in),
        "gateway_volume_inr": str(gw_vol),
        "matched": len(matched_in),
        "match_rate": f"{matched_rate * 100:.2f}%",
        "exceptions": len(exc_in),
        "exceptions_by_type": exc_by_type,
        "missing_settlement_exposure_inr": str(missing_amt),
    }


def get_cash_position() -> dict:
    """Return unreconciled cash exposure from MISSING_SETTLEMENT exceptions."""
    p = _load_pipeline()
    from decimal import Decimal
    exceptions = p["exc_report"]["exceptions"]

    missing_gw = [
        e for e in exceptions
        if e["type"] == ExceptionType.MISSING_SETTLEMENT and e["source"] == "gateway"
    ]
    orphan_ledger = [
        e for e in exceptions
        if e["type"] == ExceptionType.ORPHAN_LEDGER
    ]
    batch_exc = [e for e in exceptions if e["type"] == ExceptionType.BATCH_SETTLEMENT]

    def _total(items: list[dict]) -> Decimal:
        return sum(
            Decimal(str(e.get("amount", "0") or "0")) for e in items
        )

    missing_gw_amt = _total(missing_gw)
    orphan_amt = _total(orphan_ledger)
    batch_gw_amt = _total([e for e in batch_exc if e["source"] == "gateway"])

    return {
        "as_of": "current reconciliation run",
        "missing_settlement": {
            "description": "Gateway captured funds with no bank settlement received",
            "count": len(missing_gw),
            "order_ids": [e["record_id"] for e in missing_gw],
            "exposure_inr": str(missing_gw_amt),
        },
        "orphan_ledger": {
            "description": "Ledger entries with no gateway or bank match",
            "count": len(orphan_ledger),
            "order_ids": [e["record_id"] for e in orphan_ledger],
            "exposure_inr": str(orphan_amt),
        },
        "batch_settlement_pending": {
            "description": "Gateway txns part of batch payout not yet individually reconciled",
            "count": len([e for e in batch_exc if e["source"] == "gateway"]),
            "exposure_inr": str(batch_gw_amt),
        },
        "total_unreconciled_inr": str(missing_gw_amt + orphan_amt + batch_gw_amt),
    }


def get_cash_forecast(horizon_days: int = 14) -> dict:
    """Return a cash flow forecast for unreconciled funds."""
    forecast = generate_cash_forecast(horizon_days=horizon_days)

    entries_serialized = []
    for entry in forecast.entries:
        entries_serialized.append({
            "forecast_date": entry.forecast_date.isoformat(),
            "order_id": entry.order_id,
            "amount_inr": str(entry.amount),
            "confidence": entry.confidence,
            "reason": entry.reason,
            "source_exception_type": entry.source_exception_type,
        })

    return {
        "generated_at": forecast.generated_at,
        "horizon_days": forecast.horizon_days,
        "total_forecast_inr": str(forecast.total_forecast_inr),
        "by_date": {k: str(v) for k, v in forecast.by_date.items()},
        "by_exception_type": {k: str(v) for k, v in forecast.by_exception_type.items()},
        "entries": entries_serialized,
    }


def get_reconciliation_report() -> dict:
    """Load and return the reconciliation report from disk."""
    report_path = DATA_DIR.parent / "reports" / "reconciliation_report.json"
    if not report_path.exists():
        return {"error": "No reconciliation report found. Run the pipeline first."}
    with report_path.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Q&A Agent tool dispatch (used by /chat endpoint)
# ---------------------------------------------------------------------------

TOOL_MAP = {
    "get_match_rate": lambda inp: get_match_rate(),
    "list_exceptions": lambda inp: list_exceptions(inp.get("filter", "all")),
    "explain_match": lambda inp: explain_match(inp["txn_id"]),
    "summarize": lambda inp: summarize(inp.get("period", "all")),
    "get_cash_position": lambda inp: get_cash_position(),
    "get_cash_forecast": lambda inp: get_cash_forecast(inp.get("horizon_days", 14)),
}


def dispatch_tool(name: str, inputs: dict) -> str:
    """Call the named tool and return its JSON result string."""
    fn = TOOL_MAP.get(name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = fn(inputs)
        return json.dumps(result, indent=2, default=str)
    except Exception as exc:
        logger.exception("Tool '%s' raised an exception", name)
        return json.dumps({"error": str(exc)})


# Tool schemas for LLM (OpenAI-compatible format)
TOOLS = [
    {
        "name": "get_match_rate",
        "description": (
            "Return the overall match statistics for the current reconciliation run, "
            "including deterministic-pass rate, final rate after fuzzy matching, "
            "improvement in percentage points, and per-pass detail counts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_exceptions",
        "description": (
            "List reconciliation exceptions, optionally filtered. "
            "Returns exception_id, type, source, record_id, amount, date, and reason."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": (
                        "Optional filter string. Accepted values:\n"
                        "  - exception type: MISSING_SETTLEMENT, ORPHAN_LEDGER, "
                        "BATCH_SETTLEMENT, AMOUNT_MISMATCH, DATE_MISMATCH, "
                        "SPLIT_SETTLEMENT, ROUNDING_DIFF, UNRESOLVED_AMBIGUOUS, MISSING_TXN\n"
                        "  - source: 'gateway', 'bank', 'ledger'\n"
                        "  - 'all' or empty string for all exceptions"
                    ),
                }
            },
            "required": [],
        },
    },
    {
        "name": "explain_match",
        "description": (
            "Explain what happened to a specific gateway transaction identified by "
            "its order_id (e.g. ORD-10001). Returns match pass, method, confidence, "
            "bank UTR, amount agreement, date lag, and ledger link -- or exception "
            "details if the transaction is unmatched."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "txn_id": {
                    "type": "string",
                    "description": "Gateway order_id, e.g. 'ORD-10001'.",
                }
            },
            "required": ["txn_id"],
        },
    },
    {
        "name": "summarize",
        "description": (
            "Return a structured summary for a date range or period label. "
            "Includes transaction counts, match rates, exception breakdown, "
            "and cash exposure for records within the period."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": (
                        "Period to summarize. Accepted values:\n"
                        "  - 'all'         : entire dataset (default)\n"
                        "  - 'YYYY-MM'     : specific month, e.g. '2026-08'\n"
                        "  - 'YYYY-MM-DD'  : specific day\n"
                        "  - ISO date range: 'YYYY-MM-DD:YYYY-MM-DD'"
                    ),
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_cash_position",
        "description": (
            "Return the unreconciled cash position: total amount stuck in "
            "MISSING_SETTLEMENT exceptions (money captured at gateway but not "
            "settled by the bank). Also reports orphan ledger exposure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_cash_forecast",
        "description": (
            "Return a cash flow forecast projecting when unreconciled funds "
            "might settle. Uses learned settlement lag patterns from matched "
            "transactions to forecast inflows from MISSING_SETTLEMENT, "
            "BATCH_SETTLEMENT, and ORPHAN_LEDGER exceptions over the next "
            "14 days."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "horizon_days": {
                    "type": "integer",
                    "description": "Forecast horizon in days (default 14).",
                }
            },
            "required": [],
        },
    },
]

SYSTEM_PROMPT = """\
You are TrueUp Settlement Assistant, an expert Q&A agent for payment reconciliation.

You MUST use the provided tools to retrieve every number you quote.
You MUST NEVER invent, estimate, or hallucinate amounts, counts, percentages,
transaction IDs, dates, or exception types.

Workflow:
  1. Identify which tool(s) answer the question.
  2. Call the tool(s) and wait for results.
  3. Compose a concise, factual answer citing the numbers from tool results.
  4. If a question cannot be answered with the available tools, say so clearly.

Data context:
  - Three sources: gateway_log.csv (80 txns), bank_settlement.csv (75 settlements),
    merchant_ledger.csv (78 ledger entries).
  - Pipeline: deterministic -> fuzzy -> exception_classifier -> llm_resolver.
  - All figures are from the current reconciliation run (August 2026, seed=42).

Tone: precise, professional, brief. Avoid hedging language like "approximately"
or "around" when tool results give exact numbers.
"""
