"""Tests for the full TrueUp reconciliation pipeline (end-to-end).

Verifies the entire chain: data generation -> deterministic -> fuzzy ->
exception classification -> LLM resolver -> reporter. Tests both
micro-generated fixtures and the full generated dataset.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

from src.data_generator import build_dataset, write_dataset
from src.deterministic_matcher import load_sources, match_exact, build_summary
from src.fuzzy_matcher import match_fuzzy
from src.schemas import RecordSource
from src.exception_classifier import (
    ExceptionType,
    classify_exceptions,
    build_exceptions_report,
)
from src.llm_resolver import resolve_exceptions
from src.reporter import (
    run_full_pipeline,
    build_reconciliation_report,
    write_report,
    REPORT_PATH,
)


def test_full_pipeline_end_to_end(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    assert result["gateway_total"] == 80
    assert result["bank_total"] == 75
    assert result["ledger_total"] == 78
    assert result["det_matched"] == 59
    assert result["total_matched"] >= 70
    assert result["total_exceptions"] == 24


def test_pipeline_deterministic_to_fuzzy_handoff(generated_data_dir):
    gateway, bank, ledger = load_sources(generated_data_dir)
    det_matched, det_unmatched = match_exact(gateway, bank, ledger)

    by_src = defaultdict(list)
    for u in det_unmatched:
        by_src[u.source].append(u)

    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    total_matched = len(det_matched) + len(fuzzy_matched)
    assert total_matched >= 70
    assert len(fuzzy_unmatched) == 24


def test_pipeline_fuzzy_to_classifier_handoff(generated_data_dir):
    gateway, bank, ledger = load_sources(generated_data_dir)
    det_matched, det_unmatched = match_exact(gateway, bank, ledger)

    by_src = defaultdict(list)
    for u in det_unmatched:
        by_src[u.source].append(u)

    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    exceptions = classify_exceptions(fuzzy_unmatched, gateway, bank, ledger)
    assert len(exceptions) == len(fuzzy_unmatched)
    assert len(exceptions) == 24


def test_pipeline_classifier_to_llm_handoff(generated_data_dir):
    gateway, bank, ledger = load_sources(generated_data_dir)
    det_matched, det_unmatched = match_exact(gateway, bank, ledger)

    by_src = defaultdict(list)
    for u in det_unmatched:
        by_src[u.source].append(u)

    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    exceptions = classify_exceptions(fuzzy_unmatched, gateway, bank, ledger)
    report = build_exceptions_report(exceptions, len(gateway), len(bank), len(ledger))

    raw_exceptions = []
    for exc_dict in report["exceptions"]:
        from src.exception_classifier import ExceptionRecord
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

    resolved, llm_logs = resolve_exceptions(raw_exceptions, dry_run=True)
    assert len(resolved) == 24
    assert len(llm_logs) == 0


def test_pipeline_no_record_consumed_twice(generated_data_dir):
    gateway, bank, ledger = load_sources(generated_data_dir)
    det_matched, det_unmatched = match_exact(gateway, bank, ledger)

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

    gw_ids = [m.gateway_txn.order_id for m in all_matched]
    gw_leftover = [u.key for u in fuzzy_unmatched if u.source == RecordSource.GATEWAY]
    assert len(set(gw_ids)) == len(gw_ids)
    assert len(set(gw_leftover)) == len(gw_leftover)
    assert not set(gw_ids) & set(gw_leftover)

    utrs = [m.bank_settlement.utr for m in all_matched if m.bank_settlement]
    bank_leftover = [u.key for u in fuzzy_unmatched if u.source == RecordSource.BANK]
    assert len(set(utrs)) == len(utrs)
    assert not set(utrs) & set(bank_leftover)


def test_pipeline_all_gateway_records_accounted_for(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    accounted = result["total_matched"] + result["total_unmatched_gateway"]
    assert accounted == result["gateway_total"]


def test_pipeline_all_bank_records_accounted_for(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    accounted = result["fuzzy_summary"]["bank_consumed"] + result["total_unmatched_bank"]
    assert accounted == result["bank_total"]


def test_pipeline_all_ledger_records_accounted_for(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    accounted = result["fuzzy_summary"]["ledger_linked"] + result["total_unmatched_ledger"]
    assert accounted == result["ledger_total"]


def test_pipeline_exception_type_coverage(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    by_type = result["exception_types"]
    assert by_type["BATCH_SETTLEMENT"] == 15
    assert by_type["MISSING_SETTLEMENT"] == 6
    assert by_type["ORPHAN_LEDGER"] == 3
    zero_types = [
        ExceptionType.SPLIT_SETTLEMENT, ExceptionType.ROUNDING_DIFF,
        ExceptionType.AMOUNT_MISMATCH, ExceptionType.MISSING_TXN,
        ExceptionType.DATE_MISMATCH, ExceptionType.UNRESOLVED_AMBIGUOUS,
    ]
    for zt in zero_types:
        assert by_type[zt] == 0


def test_pipeline_full_triples_count(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    assert result["det_summary"]["full_triples"] == 58


def test_pipeline_fuzzy_split_and_batch(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    assert result["fuzzy_summary"]["split_detected"] == 4
    assert result["fuzzy_summary"]["batch_detected"] >= 2
    assert result["fuzzy_summary"]["fuzzy_matches"] >= 3


def test_pipeline_reconciliation_report_writable(generated_data_dir, tmp_path):
    gt_report_path = tmp_path / "ground_truth.json"
    gt_src = generated_data_dir / "ground_truth.json"
    gt_report_path.write_bytes(gt_src.read_bytes())

    result = run_full_pipeline(generated_data_dir)
    gt = json.loads(gt_report_path.read_text(encoding="utf-8"))
    report = build_reconciliation_report(result, gt)

    out_path = tmp_path / "reconciliation_report.json"
    write_report(report, out_path)
    assert out_path.exists()
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded["match_rates"]["deterministic"]["matched"] == 59
    assert loaded["match_rates"]["final"]["matched"] >= 70


def test_pipeline_ground_truth_verification(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    gt = json.loads(
        (generated_data_dir / "ground_truth.json").read_text(encoding="utf-8"))

    assert result["gateway_total"] == gt["totals"]["gateway"]
    assert result["bank_total"] == gt["totals"]["bank"]
    assert result["ledger_total"] == gt["totals"]["ledger"]

    total_cases = len(gt["cases"])
    clean = gt["category_counts"]["CLEAN_MATCH"]
    assert total_cases == 73
    assert clean == 25


def test_pipeline_match_rate_vs_ground_truth_expectations(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)

    clean_rate = 25 / 80
    fee_rate = 8 / 80
    drift_rate = 10 / 80
    rounding_rate = 5 / 80
    refund_rate = 3 / 80
    split_rate = 4 / 80
    garbled_rate = 5 / 80

    min_expected_rate = clean_rate + fee_rate + drift_rate + rounding_rate + refund_rate
    actual_rate = result["fuzzy_summary"]["match_rate"]
    assert actual_rate >= min_expected_rate


def test_pipeline_deterministic_baseline_is_73_75(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    assert result["det_summary"]["match_rate"] == pytest.approx(0.7375)


def test_pipeline_final_rate_is_at_least_87_5(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    assert result["fuzzy_summary"]["match_rate"] == pytest.approx(0.875)


def test_pipeline_exceptions_are_distinct_events(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    events = result["exception_events"]
    assert events == 9


def test_pipeline_report_has_improvement(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    improvement = result["fuzzy_summary"]["match_rate"] - result["det_summary"]["match_rate"]
    assert improvement > 0
    assert improvement == pytest.approx(0.1375)
