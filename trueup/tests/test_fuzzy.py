"""Tests for the fuzzy matcher: micro-fixtures + full generated run."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.data_generator import build_dataset, write_dataset
from src.deterministic_matcher import load_sources, match_exact
from src.fuzzy_matcher import (
    REASON_DUPLICATE_AMBIGUOUS,
    REASON_NO_FUZZY_MATCH,
    build_fuzzy_summary,
    find_batch_candidates,
    find_split_candidates,
    match_fuzzy,
)
from src.schemas import (
    BankSettlement,
    GatewayTransaction,
    MatchPass,
    MerchantLedger,
    RecordSource,
    UnmatchedRecord,
)


def gw(oid: str, amount: str = "100.00", day: str = "2026-08-05",
       fee: str = "0.00") -> GatewayTransaction:
    return GatewayTransaction(oid, Decimal(amount), date.fromisoformat(day),
                              "success", Decimal(fee))


def bk(ref: str, utr: str = "UTR-1", amount: str = "100.00",
       day: str = "2026-08-05") -> BankSettlement:
    return BankSettlement(utr, Decimal(amount), date.fromisoformat(day), ref)


def ld(oid: str, amount: str = "100.00", day: str = "2026-08-05") -> MerchantLedger:
    return MerchantLedger(oid, Decimal(amount), date.fromisoformat(day), "sale")


def unmatched_by_source(gateway, bank, ledger):
    matched, unmatched = match_exact(gateway, bank, ledger)
    by_src = {s: [] for s in RecordSource}
    for u in unmatched:
        by_src[u.source].append(u)
    return by_src


def test_split_detection_finds_two_parts_summing_to_gateway():
    gateway = [gw("ORD-1", amount="100.00")]
    bank = [
        bk("ORD-1", utr="UTR-A", amount="60.00"),
        bk("ORD-1", utr="UTR-B", amount="40.00"),
    ]
    ledger = [ld("ORD-1", amount="100.00")]

    by_src = unmatched_by_source(gateway, bank, ledger)
    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    assert len(fuzzy_matched) == 1
    m = fuzzy_matched[0]
    assert m.match_pass is MatchPass.FUZZY
    assert m.method == "split_settlement"
    assert m.confidence >= 0.6
    assert m.amount_agrees is True
    assert m.bank_settlement is not None


def test_split_detection_requires_exact_sum():
    gateway = [gw("ORD-1", amount="100.00")]
    bank = [
        bk("ORD-1", utr="UTR-A", amount="60.00"),
        bk("ORD-1", utr="UTR-B", amount="39.00"),
    ]
    ledger = [ld("ORD-1", amount="100.00")]

    by_src = unmatched_by_source(gateway, bank, ledger)
    fuzzy_matched, _ = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )
    assert fuzzy_matched == []


def test_batch_detection_finds_multiple_gateway_summing_to_one_bank():
    gateway = [
        gw("ORD-1", amount="100.00"),
        gw("ORD-2", amount="200.00"),
        gw("ORD-3", amount="50.00"),
    ]
    bank = [bk("N/A-BATCH-1", utr="UTR-X", amount="350.00")]
    ledger = [ld("ORD-1"), ld("ORD-2"), ld("ORD-3")]

    by_src = unmatched_by_source(gateway, bank, ledger)
    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    assert len(fuzzy_matched) >= 1
    batch_matches = [m for m in fuzzy_matched if m.method == "batch_settlement"]
    assert len(batch_matches) >= 1


def test_batch_detection_requires_exact_sum():
    gateway = [
        gw("ORD-1", amount="100.00"),
        gw("ORD-2", amount="200.00"),
    ]
    bank = [bk("N/A-BATCH-1", utr="UTR-X", amount="350.00")]
    ledger = [ld("ORD-1"), ld("ORD-2")]

    by_src = unmatched_by_source(gateway, bank, ledger)
    fuzzy_matched, _ = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )
    batch_matches = [m for m in fuzzy_matched if m.method == "batch_settlement"]
    assert batch_matches == []


def test_fuzzy_amount_date_edit_match_within_tolerance():
    gateway = [gw("ORD-100", amount="1000.00", day="2026-08-10")]
    bank = [bk("ORD-100-X", utr="UTR-1", amount="1003.00", day="2026-08-12")]
    ledger = [ld("ORD-100", amount="1000.00")]

    by_src = unmatched_by_source(gateway, bank, ledger)
    fuzzy_matched, _ = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    assert len(fuzzy_matched) == 1
    m = fuzzy_matched[0]
    assert m.method == "fuzzy_amount_date_edit"
    assert m.confidence >= 0.5
    assert m.amount_agrees is True
    assert m.date_lag_days == 2


def test_fuzzy_rejects_amount_outside_tolerance():
    gateway = [gw("ORD-100", amount="1000.00")]
    bank = [bk("ORD-100-X", utr="UTR-1", amount="1010.00")]
    ledger = [ld("ORD-100")]

    by_src = unmatched_by_source(gateway, bank, ledger)
    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    assert fuzzy_matched == []
    u = next(u for u in fuzzy_unmatched if u.source == RecordSource.GATEWAY)
    assert u.reason_hint == REASON_NO_FUZZY_MATCH


def test_fuzzy_rejects_date_outside_window():
    gateway = [gw("ORD-100", amount="1000.00", day="2026-08-01")]
    bank = [bk("ORD-100-X", utr="UTR-1", amount="1000.00", day="2026-08-10")]
    ledger = [ld("ORD-100")]

    by_src = unmatched_by_source(gateway, bank, ledger)
    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    assert fuzzy_matched == []
    u = next(u for u in fuzzy_unmatched if u.source == RecordSource.GATEWAY)
    assert u.reason_hint == REASON_NO_FUZZY_MATCH


def test_fuzzy_rejects_edit_distance_below_threshold():
    gateway = [gw("ORD-100", amount="1000.00")]
    bank = [bk("XYZ-999", utr="UTR-1", amount="1000.00")]
    ledger = [ld("ORD-100")]

    by_src = unmatched_by_source(gateway, bank, ledger)
    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    assert fuzzy_matched == []
    u = next(u for u in fuzzy_unmatched if u.source == RecordSource.GATEWAY)
    assert u.reason_hint == REASON_NO_FUZZY_MATCH


def test_duplicate_near_match_flagged():
    gateway = [
        gw("ORD-A", amount="500.00", day="2026-08-10"),
        gw("ORD-B", amount="500.00", day="2026-08-11"),
    ]
    bank = [
        bk("ORD-A", utr="UTR-1", amount="500.00", day="2026-08-10"),
        bk("ORD-B", utr="UTR-2", amount="500.00", day="2026-08-11"),
        bk("ORD-A", utr="UTR-3", amount="500.00", day="2026-08-10"),
    ]
    ledger = [ld("ORD-A"), ld("ORD-B")]

    by_src = unmatched_by_source(gateway, bank, ledger)
    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    ambig = [u for u in fuzzy_unmatched
             if u.reason_hint == REASON_DUPLICATE_AMBIGUOUS]
    assert len(ambig) >= 1


def test_no_record_consumed_twice_in_fuzzy():
    gateway = [gw("ORD-1"), gw("ORD-2"), gw("ORD-3")]
    bank = [bk("ORD-1", utr="UTR-A"), bk("ORD-2", utr="UTR-B")]
    ledger = [ld("ORD-1"), ld("ORD-2")]

    by_src = unmatched_by_source(gateway, bank, ledger)
    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    utrs = [m.bank_settlement.utr for m in fuzzy_matched if m.bank_settlement]
    utrs += [u.record.utr for u in fuzzy_unmatched if u.source == RecordSource.BANK]
    oids = [m.gateway_txn.order_id for m in fuzzy_matched]
    oids += [u.key for u in fuzzy_unmatched if u.source == RecordSource.GATEWAY]

    assert len(set(utrs)) == len(utrs)
    assert len(set(oids)) == len(oids)


def test_find_split_candidates_returns_correct_combinations():
    gateway_txn = gw("ORD-1", amount="100.00")
    bank_records = [
        bk("ORD-1", utr="UTR-A", amount="60.00"),
        bk("ORD-1", utr="UTR-B", amount="40.00"),
        bk("ORD-1", utr="UTR-C", amount="30.00"),
    ]
    candidates = find_split_candidates(gateway_txn, bank_records)
    assert len(candidates) == 1
    settlements, conf = candidates[0]
    assert len(settlements) == 2
    assert settlements[0].settlement_amount + settlements[1].settlement_amount == Decimal("100.00")


def test_find_batch_candidates_returns_correct_combinations():
    gateway_txns = [
        gw("ORD-1", amount="100.00"),
        gw("ORD-2", amount="200.00"),
        gw("ORD-3", amount="50.00"),
    ]
    bank_record = bk("N/A-BATCH-1", utr="UTR-X", amount="350.00")
    candidates = find_batch_candidates(gateway_txns, bank_record)
    assert len(candidates) >= 1
    for members, conf in candidates:
        assert sum(g.amount for g in members) == Decimal("350.00")
        assert len(members) >= 2


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    write_dataset(build_dataset(), data_dir)
    return {"records": load_sources(data_dir), "dir": data_dir}


def test_generated_dataset_fuzzy_improves_match_rate(generated):
    gateway, bank, ledger = generated["records"]
    det_matched, det_unmatched = match_exact(gateway, bank, ledger)
    det_rate = len(det_matched) / len(gateway)

    by_src = {s: [] for s in RecordSource}
    for u in det_unmatched:
        by_src[u.source].append(u)

    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    all_matched = det_matched + fuzzy_matched
    fuzzy_rate = len(all_matched) / len(gateway)

    assert fuzzy_rate > det_rate
    assert fuzzy_rate >= 0.85

    summary = build_fuzzy_summary(
        all_matched, fuzzy_unmatched,
        len(gateway), len(bank), len(ledger),
    )
    assert summary["split_detected"] == 4
    assert summary["batch_detected"] >= 2


def test_generated_dataset_no_duplicate_consumption(generated):
    gateway, bank, ledger = generated["records"]
    det_matched, det_unmatched = match_exact(gateway, bank, ledger)

    by_src = {s: [] for s in RecordSource}
    for u in det_unmatched:
        by_src[u.source].append(u)

    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        by_src[RecordSource.GATEWAY],
        by_src[RecordSource.BANK],
        by_src[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    all_matched = det_matched + fuzzy_matched
    all_unmatched = fuzzy_unmatched

    utrs = [m.bank_settlement.utr for m in all_matched if m.bank_settlement]
    utrs += [u.record.utr for u in all_unmatched if u.source == RecordSource.BANK]
    oids = [m.gateway_txn.order_id for m in all_matched]
    oids += [u.key for u in all_unmatched if u.source == RecordSource.GATEWAY]
    led_ids = [m.merchant_ledger.order_id for m in all_matched if m.merchant_ledger]
    led_ids += [u.key for u in all_unmatched if u.source == RecordSource.LEDGER]

    assert len(set(utrs)) == len(utrs)
    assert len(set(oids)) == len(oids)
    assert len(set(led_ids)) == len(led_ids)