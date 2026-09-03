"""Tests for the synthetic data generator: counts, uniqueness, determinism."""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from decimal import Decimal

import pytest

from src.data_generator import (
    DATA_MD,
    DATE_MAX_ALL,
    DATE_MIN,
    EXPECTED_CATEGORY_COUNTS,
    EXPECTED_TOTALS,
    GARBLED_COUNT,
    GATEWAY_CSV,
    GROUND_TRUTH_JSON,
    OUTPUT_FILES,
    SEED,
    build_dataset,
    write_dataset,
)


@pytest.fixture(scope="module")
def dataset():
    return build_dataset()


def test_row_counts_match_expected_totals(dataset):
    for source in ("gateway", "bank", "ledger"):
        assert len(dataset[source]) == EXPECTED_TOTALS[source]


def test_category_counts_are_exact(dataset):
    counts = Counter(c.category for c in dataset["cases"])
    assert dict(counts) == dict(EXPECTED_CATEGORY_COUNTS)


def test_order_ids_unique_within_each_source(dataset):
    for source in ("gateway", "ledger"):
        ids = [row["order_id"] for row in dataset[source]]
        assert len(set(ids)) == len(ids)
    utrs = [row["utr"] for row in dataset["bank"]]
    assert len(set(utrs)) == len(utrs)


def test_orphan_ids_absent_from_other_sources(dataset):
    orphans = {c.order_ids[0] for c in dataset["cases"]
               if c.category == "ORPHAN_LEDGER"}
    gateway_ids = {row["order_id"] for row in dataset["gateway"]}
    bank_refs = {row["order_id_ref"] for row in dataset["bank"]}
    assert not orphans & gateway_ids
    assert not orphans & bank_refs


def test_all_dates_inside_declared_window(dataset):
    date_fields = {"gateway": ("txn_date",), "bank": ("settlement_date",),
                   "ledger": ("entry_date",)}
    for source, fields in date_fields.items():
        for row in dataset[source]:
            for fld in fields:
                day = date.fromisoformat(row[fld])
                assert DATE_MIN <= day <= DATE_MAX_ALL


def test_amounts_have_paise_precision(dataset):
    amount_fields = {"gateway": ("amount", "gateway_fee"),
                     "bank": ("settlement_amount",),
                     "ledger": ("expected_amount",)}
    for source, fields in amount_fields.items():
        for row in dataset[source]:
            for fld in fields:
                value = Decimal(row[fld])
                assert value == value.quantize(Decimal("0.01"))
                assert value >= 0


def test_split_parts_sum_to_gateway_amount(dataset):
    bank_by_ref = {}
    for row in dataset["bank"]:
        bank_by_ref.setdefault(row["order_id_ref"], []).append(
            Decimal(row["settlement_amount"]))
    gateway_by_id = {row["order_id"]: Decimal(row["amount"])
                     for row in dataset["gateway"]}
    splits = [c for c in dataset["cases"] if c.category == "SPLIT_SETTLEMENT"]
    assert len(splits) == EXPECTED_CATEGORY_COUNTS["SPLIT_SETTLEMENT"]
    for case in splits:
        oid = case.order_ids[0]
        parts = [money for ref, amounts in bank_by_ref.items()
                 if ref == oid for money in amounts]
        assert len(parts) == 2
        assert sum(parts) == gateway_by_id[oid]


def test_batch_credit_equals_sum_of_members(dataset):
    gateway_by_id = {row["order_id"]: Decimal(row["amount"])
                     for row in dataset["gateway"]}
    bank_by_utr = {row["utr"]: Decimal(row["settlement_amount"])
                   for row in dataset["bank"]}
    batches = [c for c in dataset["cases"] if c.category == "BATCH_SETTLEMENT"]
    for case in batches:
        member_total = sum(gateway_by_id[oid] for oid in case.order_ids)
        credit = bank_by_utr[case.utrs[0]]
        assert credit == member_total


def test_garbled_refs_differ_from_true_id_and_stay_nonempty(dataset):
    garbled_cases = [c for c in dataset["cases"]
                     if c.category == "GARBLED_REFERENCE"]
    assert len(garbled_cases) == GARBLED_COUNT
    refs = {row["order_id_ref"] for row in dataset["bank"]}
    for case in garbled_cases:
        true_id = case.order_ids[0]
        corrupted = [r for r in refs if r != true_id and true_id[:-3] in r
                     or r.lower() in true_id.lower()]
        assert any(corrupted), f"no corrupted variant found near {true_id}"


def test_fee_and_refund_settlements_reduce_amount(dataset):
    gateway_by_id = {row["order_id"]: Decimal(row["amount"])
                     for row in dataset["gateway"]}
    bank_rows = {row["utr"]: row for row in dataset["bank"]}
    fee_cases = [c for c in dataset["cases"] if c.category == "GATEWAY_FEE"]
    refund_cases = [c for c in dataset["cases"] if c.category == "PARTIAL_REFUND"]
    for case in fee_cases + refund_cases:
        settled = Decimal(bank_rows[case.utrs[0]]["settlement_amount"])
        assert settled < gateway_by_id[case.order_ids[0]]


def test_write_is_byte_deterministic(tmp_path):
    dir_a = tmp_path / "run_a"
    dir_b = tmp_path / "run_b"
    write_dataset(build_dataset(), dir_a)
    write_dataset(build_dataset(), dir_b)
    for name in OUTPUT_FILES:
        assert (dir_a / name).read_bytes() == (dir_b / name).read_bytes(), name


def test_ground_truth_json_structure(tmp_path):
    write_dataset(build_dataset(), tmp_path)
    payload = json.loads((tmp_path / GROUND_TRUTH_JSON).read_text(encoding="utf-8"))
    assert payload["seed"] == SEED
    assert payload["totals"] == dict(EXPECTED_TOTALS)
    assert payload["category_counts"] == dict(EXPECTED_CATEGORY_COUNTS)
    assert len(payload["cases"]) == sum(EXPECTED_CATEGORY_COUNTS.values())
    required = {"case_id", "category", "order_ids", "utrs",
                "expected_outcome", "detail"}
    for case in payload["cases"]:
        assert required <= set(case)


def test_data_md_generated_and_self_describing(tmp_path):
    write_dataset(build_dataset(), tmp_path)
    text = (tmp_path / DATA_MD).read_text(encoding="utf-8")
    assert GATEWAY_CSV in text
    assert "DO NOT EDIT BY HAND" in text
    assert str(SEED) in text
