"""Reconciliation reporter for TrueUp.

Runs the full 4-pass pipeline, loads ground_truth.json, compares actual
results against expected, computes match rates, and writes
reports/reconciliation_report.json.

Run: python -m src.reporter
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from src.data_generator import GROUND_TRUTH_JSON
from src.deterministic_matcher import (
    DATA_DIR,
    load_sources,
    match_exact,
    build_summary,
)
from src.fuzzy_matcher import match_fuzzy
from src.schemas import MatchPass, RecordSource
from src.exception_classifier import (
    ExceptionRecord,
    ExceptionType,
    classify_exceptions,
    build_exceptions_report,
)
from src.llm_resolver import resolve_exceptions

logger = logging.getLogger(__name__)

REPORTS_DIR = DATA_DIR.parent / "reports"
REPORT_PATH = REPORTS_DIR / "reconciliation_report.json"


def load_ground_truth(data_dir: Path = DATA_DIR) -> dict:
    path = data_dir / GROUND_TRUTH_JSON
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def run_full_pipeline(data_dir: Path = DATA_DIR) -> dict:
    gateway, bank, ledger = load_sources(data_dir)

    det_matched, det_unmatched = match_exact(gateway, bank, ledger)
    det_summary = build_summary(
        det_matched, det_unmatched, len(gateway), len(bank), len(ledger))

    by_src = defaultdict(list)
    for u in det_unmatched:
        by_src[u.source].append(u)

    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    all_matched = det_matched + fuzzy_matched
    fuzzy_summary = _build_combined_summary(
        all_matched, fuzzy_unmatched, len(gateway), len(bank), len(ledger))

    exceptions = classify_exceptions(fuzzy_unmatched, gateway, bank, ledger)
    exc_report = build_exceptions_report(
        exceptions, len(gateway), len(bank), len(ledger))

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

    resolved_exceptions, llm_logs = resolve_exceptions(raw_exceptions, dry_run=True)

    from src.llm_resolver import _llm_summary
    llm_summary = _llm_summary(llm_logs)

    return {
        "gateway_total": len(gateway),
        "bank_total": len(bank),
        "ledger_total": len(ledger),
        "det_matched": len(det_matched),
        "det_summary": det_summary,
        "fuzzy_matched": len(fuzzy_matched),
        "fuzzy_summary": fuzzy_summary,
        "total_matched": len(all_matched),
        "total_unmatched_gateway": fuzzy_summary["unmatched_gateway"],
        "total_unmatched_bank": fuzzy_summary["unmatched_bank"],
        "total_unmatched_ledger": fuzzy_summary["unmatched_ledger"],
        "total_exceptions": len(exceptions),
        "exception_types": exc_report["summary"]["by_type"],
        "exception_events": exc_report["summary"]["distinct_events"],
        "llm_summary": llm_summary,
    }


def _build_combined_summary(
    matched, unmatched, gateway_total, bank_total, ledger_total
) -> dict:
    by_source = {source: 0 for source in RecordSource}
    for u in unmatched:
        by_source[u.source] += 1
    split_count = sum(1 for m in matched if m.match_pass is MatchPass.FUZZY
                      and m.method == "split_settlement")
    batch_count = sum(1 for m in matched if m.match_pass is MatchPass.FUZZY
                      and m.method == "batch_settlement")
    fuzzy_count = sum(1 for m in matched if m.match_pass is MatchPass.FUZZY
                      and m.method == "fuzzy_amount_date_edit")
    return {
        "gateway_matched": len(matched),
        "gateway_total": gateway_total,
        "match_rate": len(matched) / gateway_total if gateway_total else 0.0,
        "bank_consumed": bank_total - by_source[RecordSource.BANK],
        "bank_total": bank_total,
        "ledger_linked": ledger_total - by_source[RecordSource.LEDGER],
        "ledger_total": ledger_total,
        "full_triples": sum(1 for m in matched if m.is_full_triple()),
        "split_detected": split_count,
        "batch_detected": batch_count,
        "fuzzy_matches": fuzzy_count,
        "unmatched_gateway": by_source[RecordSource.GATEWAY],
        "unmatched_bank": by_source[RecordSource.BANK],
        "unmatched_ledger": by_source[RecordSource.LEDGER],
        "unmatched_total": len(unmatched),
    }


def compare_with_ground_truth(pipeline_result: dict, ground_truth: dict) -> dict:
    gt_totals = ground_truth["totals"]
    gt_categories = ground_truth["category_counts"]

    det_rate = pipeline_result["det_summary"]["match_rate"]
    final_rate = pipeline_result["fuzzy_summary"]["match_rate"]

    exc_by_type = pipeline_result["exception_types"]

    resolved_categories = {
        "CLEAN_MATCH": 25,
        "GATEWAY_FEE": 8,
        "DATE_DRIFT": 10,
        "SPLIT_SETTLEMENT": 4,
        "BATCH_SETTLEMENT": 3,
        "GARBLED_REFERENCE": 5,
        "DUPLICATE_NEAR_MATCH": 4,
        "MISSING_SETTLEMENT": 3,
        "ORPHAN_LEDGER": 3,
        "ROUNDING_DIFF": 5,
        "PARTIAL_REFUND": 3,
    }

    discrepancies = []

    if pipeline_result["gateway_total"] != gt_totals["gateway"]:
        discrepancies.append({
            "field": "gateway_total",
            "expected": gt_totals["gateway"],
            "actual": pipeline_result["gateway_total"],
        })
    if pipeline_result["bank_total"] != gt_totals["bank"]:
        discrepancies.append({
            "field": "bank_total",
            "expected": gt_totals["bank"],
            "actual": pipeline_result["bank_total"],
        })
    if pipeline_result["ledger_total"] != gt_totals["ledger"]:
        discrepancies.append({
            "field": "ledger_total",
            "expected": gt_totals["ledger"],
            "actual": pipeline_result["ledger_total"],
        })

    return {
        "record_counts_match": len(discrepancies) == 0,
        "record_count_discrepancies": discrepancies,
        "deterministic_match_rate": det_rate,
        "deterministic_match_rate_pct": f"{det_rate * 100:.2f}%",
        "final_match_rate": final_rate,
        "final_match_rate_pct": f"{final_rate * 100:.2f}%",
        "improvement_pp": f"{(final_rate - det_rate) * 100:+.2f}pp",
        "ground_truth_total_cases": len(ground_truth["cases"]),
        "ground_truth_clean_triples": ground_truth["clean_triples"],
        "ground_truth_categories": gt_categories,
        "pipeline_exceptions_by_type": {k: v for k, v in exc_by_type.items() if v > 0},
        "pipeline_exception_events": pipeline_result["exception_events"],
    }


def build_reconciliation_report(pipeline_result: dict, ground_truth: dict) -> dict:
    comparison = compare_with_ground_truth(pipeline_result, ground_truth)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pipeline": "deterministic -> fuzzy -> exception_classifier -> llm_resolver",
        "record_counts": {
            "gateway": pipeline_result["gateway_total"],
            "bank": pipeline_result["bank_total"],
            "ledger": pipeline_result["ledger_total"],
        },
        "match_rates": {
            "deterministic": {
                "matched": pipeline_result["det_matched"],
                "total": pipeline_result["gateway_total"],
                "rate": pipeline_result["det_summary"]["match_rate"],
                "rate_pct": comparison["deterministic_match_rate_pct"],
            },
            "final": {
                "matched": pipeline_result["total_matched"],
                "total": pipeline_result["gateway_total"],
                "rate": pipeline_result["fuzzy_summary"]["match_rate"],
                "rate_pct": comparison["final_match_rate_pct"],
            },
            "improvement_pp": comparison["improvement_pp"],
        },
        "pass_details": {
            "deterministic": {
                "matched": pipeline_result["det_matched"],
                "amount_disagreements": pipeline_result["det_summary"]["amount_disagreements"],
                "date_drifts": pipeline_result["det_summary"]["date_drifts"],
                "full_triples": pipeline_result["det_summary"]["full_triples"],
            },
            "fuzzy": {
                "additional_matched": pipeline_result["fuzzy_matched"],
                "split_detected": pipeline_result["fuzzy_summary"]["split_detected"],
                "batch_detected": pipeline_result["fuzzy_summary"]["batch_detected"],
                "fuzzy_amount_date_edit": pipeline_result["fuzzy_summary"]["fuzzy_matches"],
            },
        },
        "leftover_records": {
            "gateway": pipeline_result["total_unmatched_gateway"],
            "bank": pipeline_result["total_unmatched_bank"],
            "ledger": pipeline_result["total_unmatched_ledger"],
            "total": (pipeline_result["total_unmatched_gateway"]
                      + pipeline_result["total_unmatched_bank"]
                      + pipeline_result["total_unmatched_ledger"]),
        },
        "exceptions": {
            "total": pipeline_result["total_exceptions"],
            "distinct_events": pipeline_result["exception_events"],
            "by_type": {k: v for k, v in pipeline_result["exception_types"].items()
                        if v > 0},
        },
        "llm_summary": pipeline_result["llm_summary"],
        "ground_truth_comparison": comparison,
    }


def write_report(report: dict, path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _print_report(report: dict) -> None:
    mr = report["match_rates"]
    comp = report["ground_truth_comparison"]
    exc = report["exceptions"]
    lr = report["leftover_records"]

    print(f"{'═' * 64}")
    print(f"  TrueUp Reconciliation Report")
    print(f"  {report['generated_at']}")
    print(f"{'═' * 64}")
    print()
    print(f"  Record counts: gateway {report['record_counts']['gateway']}, "
          f"bank {report['record_counts']['bank']}, "
          f"ledger {report['record_counts']['ledger']}")
    print()
    print(f"  Match rates:")
    print(f"    Deterministic (Pass 1): {mr['deterministic']['matched']}/"
          f"{mr['deterministic']['total']} = {mr['deterministic']['rate_pct']}")
    print(f"    Final (after fuzzy):    {mr['final']['matched']}/"
          f"{mr['final']['total']} = {mr['final']['rate_pct']}")
    print(f"    Improvement:            {mr['improvement_pp']}")
    print()
    print(f"  Pass 1 details:")
    pd = report["pass_details"]["deterministic"]
    print(f"    Full triples:     {pd['full_triples']}")
    print(f"    Amount flagged:   {pd['amount_disagreements']}")
    print(f"    Date drifts:      {pd['date_drifts']}")
    print()
    print(f"  Pass 2 (fuzzy) gains:")
    pf = report["pass_details"]["fuzzy"]
    print(f"    Additional matched: {pf['additional_matched']}")
    print(f"    Split detected:     {pf['split_detected']}")
    print(f"    Batch detected:     {pf['batch_detected']}")
    print(f"    Fuzzy amt/date/edit:{pf['fuzzy_amount_date_edit']}")
    print()
    print(f"  Leftover records: {lr['total']} "
          f"({lr['gateway']} gw + {lr['bank']} bank + {lr['ledger']} ledger)")
    print()
    print(f"  Exceptions: {exc['total']} across {exc['distinct_events']} events")
    for etype, count in sorted(exc["by_type"].items()):
        print(f"    {etype:<24} {count}")
    print()
    print(f"  LLM resolver: {report['llm_summary']['total_llm_calls']} calls")
    print()
    print(f"  Ground truth comparison:")
    print(f"    Record counts match: {comp['record_counts_match']}")
    if comp["record_count_discrepancies"]:
        for d in comp["record_count_discrepancies"]:
            print(f"      DISCREPANCY: {d['field']} expected={d['expected']} actual={d['actual']}")
    print(f"    Total GT cases: {comp['ground_truth_total_cases']}")
    print(f"    Clean triples:  {comp['ground_truth_clean_triples']}")
    print()
    print(f"  Wrote: {REPORT_PATH}")
    print(f"{'═' * 64}")


def main() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    ground_truth = load_ground_truth(DATA_DIR)
    pipeline_result = run_full_pipeline(DATA_DIR)
    report = build_reconciliation_report(pipeline_result, ground_truth)
    write_report(report)
    _print_report(report)


if __name__ == "__main__":
    main()
