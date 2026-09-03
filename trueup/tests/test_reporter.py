"""Tests for src/reporter.py: reconciliation report generation."""
from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from src.data_generator import build_dataset, write_dataset
from src.deterministic_matcher import load_sources, match_exact, build_summary
from src.fuzzy_matcher import match_fuzzy
from src.schemas import RecordSource
from src.reporter import (
    compare_with_ground_truth,
    build_reconciliation_report,
    load_ground_truth,
    run_full_pipeline,
    write_report,
    _build_combined_summary,
)


def test_load_ground_truth_returns_dict(gt_path):
    gt = load_ground_truth(gt_path)
    assert "totals" in gt
    assert "category_counts" in gt
    assert "cases" in gt
    assert gt["seed"] == 42


def test_ground_truth_has_expected_totals(gt_path):
    gt = load_ground_truth(gt_path)
    assert gt["totals"]["gateway"] == 80
    assert gt["totals"]["bank"] == 75
    assert gt["totals"]["ledger"] == 78


def test_ground_truth_has_all_categories(gt_path):
    gt = load_ground_truth(gt_path)
    cats = gt["category_counts"]
    expected = {
        "CLEAN_MATCH": 25, "GATEWAY_FEE": 8, "DATE_DRIFT": 10,
        "SPLIT_SETTLEMENT": 4, "BATCH_SETTLEMENT": 3, "GARBLED_REFERENCE": 5,
        "DUPLICATE_NEAR_MATCH": 4, "MISSING_SETTLEMENT": 3, "ORPHAN_LEDGER": 3,
        "ROUNDING_DIFF": 5, "PARTIAL_REFUND": 3,
    }
    assert cats == expected


def test_run_full_pipeline_returns_expected_keys(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    assert "gateway_total" in result
    assert "bank_total" in result
    assert "ledger_total" in result
    assert "det_matched" in result
    assert "det_summary" in result
    assert "fuzzy_matched" in result
    assert "fuzzy_summary" in result
    assert "total_matched" in result
    assert "total_exceptions" in result
    assert "exception_types" in result
    assert "llm_summary" in result


def test_run_full_pipeline_match_rates(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    assert result["gateway_total"] == 80
    assert result["bank_total"] == 75
    assert result["ledger_total"] == 78
    det_rate = result["det_summary"]["match_rate"]
    final_rate = result["fuzzy_summary"]["match_rate"]
    assert det_rate == pytest.approx(59 / 80)
    assert final_rate > det_rate
    assert final_rate >= 0.85


def test_run_full_pipeline_deterministic_counts(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    assert result["det_matched"] == 59
    assert result["det_summary"]["full_triples"] == 58


def test_run_full_pipeline_fuzzy_gains(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    assert result["fuzzy_matched"] > 0
    assert result["fuzzy_summary"]["split_detected"] == 4
    assert result["fuzzy_summary"]["batch_detected"] >= 2


def test_run_full_pipeline_exceptions(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    assert result["total_exceptions"] == 24
    assert result["exception_events"] == 9
    by_type = result["exception_types"]
    assert by_type["BATCH_SETTLEMENT"] == 15
    assert by_type["MISSING_SETTLEMENT"] == 6
    assert by_type["ORPHAN_LEDGER"] == 3


def test_compare_with_ground_truth_no_discrepancies(generated_data_dir):
    gt = load_ground_truth(generated_data_dir)
    result = run_full_pipeline(generated_data_dir)
    comp = compare_with_ground_truth(result, gt)
    assert comp["record_counts_match"] is True
    assert comp["record_count_discrepancies"] == []


def test_compare_ground_truth_rates(generated_data_dir):
    gt = load_ground_truth(generated_data_dir)
    result = run_full_pipeline(generated_data_dir)
    comp = compare_with_ground_truth(result, gt)
    assert comp["deterministic_match_rate"] == pytest.approx(59 / 80)
    assert comp["final_match_rate"] >= 0.85
    assert comp["ground_truth_total_cases"] == 73
    assert comp["ground_truth_clean_triples"] == 25


def test_build_reconciliation_report_structure(generated_data_dir):
    gt = load_ground_truth(generated_data_dir)
    result = run_full_pipeline(generated_data_dir)
    report = build_reconciliation_report(result, gt)
    assert "generated_at" in report
    assert "pipeline" in report
    assert "record_counts" in report
    assert "match_rates" in report
    assert "pass_details" in report
    assert "leftover_records" in report
    assert "exceptions" in report
    assert "llm_summary" in report
    assert "ground_truth_comparison" in report


def test_build_reconciliation_report_match_rates(generated_data_dir):
    gt = load_ground_truth(generated_data_dir)
    result = run_full_pipeline(generated_data_dir)
    report = build_reconciliation_report(result, gt)
    mr = report["match_rates"]
    assert mr["deterministic"]["matched"] == 59
    assert mr["deterministic"]["total"] == 80
    assert "59/80" not in mr["deterministic"]["rate_pct"] or "%" in mr["deterministic"]["rate_pct"]
    assert mr["final"]["matched"] >= 70
    assert "+" in mr["improvement_pp"] or "-" in mr["improvement_pp"]


def test_build_reconciliation_report_leftovers(generated_data_dir):
    gt = load_ground_truth(generated_data_dir)
    result = run_full_pipeline(generated_data_dir)
    report = build_reconciliation_report(result, gt)
    lr = report["leftover_records"]
    assert lr["total"] == lr["gateway"] + lr["bank"] + lr["ledger"]
    assert lr["total"] == 24


def test_write_report_creates_file(tmp_path):
    report = {"generated_at": "2026-08-28T12:00:00", "test": True}
    out_path = tmp_path / "reports" / "reconciliation_report.json"
    write_report(report, out_path)
    assert out_path.exists()
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded["test"] is True


def test_write_report_creates_parent_dirs(tmp_path):
    report = {"test": True}
    out_path = tmp_path / "a" / "b" / "c" / "report.json"
    write_report(report, out_path)
    assert out_path.exists()


def test_build_combined_summary_field_count(generated_data_dir):
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
    summary = _build_combined_summary(
        all_matched, fuzzy_unmatched, len(gateway), len(bank), len(ledger))
    assert summary["gateway_matched"] == 70
    assert summary["gateway_total"] == 80
    assert summary["unmatched_total"] == 24


def test_compare_ground_truth_exceptions(generated_data_dir):
    gt = load_ground_truth(generated_data_dir)
    result = run_full_pipeline(generated_data_dir)
    comp = compare_with_ground_truth(result, gt)
    assert "BATCH_SETTLEMENT" in comp["pipeline_exceptions_by_type"]
    assert "MISSING_SETTLEMENT" in comp["pipeline_exceptions_by_type"]
    assert "ORPHAN_LEDGER" in comp["pipeline_exceptions_by_type"]


def test_report_deterministic_summary_fields(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    ds = result["det_summary"]
    assert "gateway_matched" in ds
    assert "gateway_total" in ds
    assert "match_rate" in ds
    assert "bank_consumed" in ds
    assert "full_triples" in ds
    assert "amount_disagreements" in ds
    assert "date_drifts" in ds
    assert "unmatched_gateway" in ds
    assert "unmatched_bank" in ds
    assert "unmatched_ledger" in ds


def test_report_pipeline_result_total_unmatched_equals_exceptions(generated_data_dir):
    result = run_full_pipeline(generated_data_dir)
    total_leftover = (result["total_unmatched_gateway"]
                      + result["total_unmatched_bank"]
                      + result["total_unmatched_ledger"])
    assert total_leftover == result["total_exceptions"]
