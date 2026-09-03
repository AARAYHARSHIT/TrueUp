"""Tests for the exception classifier (Pass 3).

Micro-fixtures assert each of the 9 named types fires on a hand-crafted case
(suggestions.txt #16/#23), plus a full-generated-data test that the classifier
consumes every leftover record and the breakdown matches DATA.md categories.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from src.deterministic_matcher import load_sources, match_exact
from src.fuzzy_matcher import match_fuzzy
from src.schemas import (
    BankSettlement,
    GatewayTransaction,
    MerchantLedger,
    RecordSource,
    UnmatchedRecord,
)
from src.exception_classifier import (
    ExceptionType,
    classify_exceptions,
    build_exceptions_report,
)

D = date.fromisoformat


def gw(oid, amount="100.00", day="2026-08-05", fee="0.00"):
    return GatewayTransaction(oid, Decimal(amount), D(day), "success", Decimal(fee))


def bk(ref, utr="UTR-1", amount="100.00", day="2026-08-05"):
    return BankSettlement(utr, Decimal(amount), D(day), ref)


def ld(oid, amount="100.00", day="2026-08-05"):
    return MerchantLedger(oid, Decimal(amount), D(day), "sale")


def classify_one(unmatched, gateway, bank, ledger):
    recs = classify_exceptions(unmatched, gateway, bank, ledger)
    assert len(recs) == len(unmatched), "every record must get exactly one exception"
    return recs[0]


# --- the nine named types (micro-fixtures) ------------------------------------

def test_missing_settlement():
    g = gw("ORD-1", "100.00", "2026-08-05")
    l = ld("ORD-1", "100.00", "2026-08-05")
    u = UnmatchedRecord(RecordSource.GATEWAY, g, "no_fuzzy_match")
    rec = classify_one([u], [g], [], [l])
    assert rec.type == ExceptionType.MISSING_SETTLEMENT


def test_orphan_ledger():
    l = ld("ORD-9", "100.00", "2026-08-05")
    u = UnmatchedRecord(RecordSource.LEDGER, l, "no_payment_found")
    rec = classify_one([u], [], [], [l])
    assert rec.type == ExceptionType.ORPHAN_LEDGER


def test_batch_settlement_gateway_member():
    g2 = gw("ORD-2", "60.00", "2026-08-05")
    g3 = gw("ORD-3", "30.00", "2026-08-05")
    g4 = gw("ORD-4", "10.00", "2026-08-05")
    pay = bk("N/A-BATCH", "UTR-B", "100.00", "2026-08-06")
    u = UnmatchedRecord(RecordSource.GATEWAY, g2, "no_fuzzy_match")
    rec = classify_one([u], [g2, g3, g4], [pay], [])
    assert rec.type == ExceptionType.BATCH_SETTLEMENT
    assert rec.event_key == "UTR-B"


def test_batch_settlement_bank_payout():
    g2 = gw("ORD-2", "60.00", "2026-08-05")
    g3 = gw("ORD-3", "30.00", "2026-08-05")
    g4 = gw("ORD-4", "10.00", "2026-08-05")
    pay = bk("N/A-BATCH", "UTR-B", "100.00", "2026-08-06")
    u = UnmatchedRecord(RecordSource.BANK, pay, "no_fuzzy_match")
    rec = classify_one([u], [g2, g3, g4], [pay], [])
    assert rec.type == ExceptionType.BATCH_SETTLEMENT


def test_missing_txn():
    b = bk("ZZ-NOWHERE", "UTR-X", "50.00", "2026-08-05")
    u = UnmatchedRecord(RecordSource.BANK, b, "no_gateway_match")
    rec = classify_one([u], [], [b], [])
    assert rec.type == ExceptionType.MISSING_TXN


def test_amount_mismatch_gateway():
    # near-ref bank (95% similarity on a 20-char id) within amount band, wrong figure
    g = gw("ORDER-10000000000001", "100.00", "2026-08-05")
    b = bk("ORDER-1000000000000X", "UTR-A", "102.00", "2026-08-05")
    u = UnmatchedRecord(RecordSource.GATEWAY, g, "no_fuzzy_match")
    rec = classify_one([u], [g], [b], [])
    assert rec.type == ExceptionType.AMOUNT_MISMATCH


def test_amount_mismatch_bank():
    g = gw("ORD-1", "100.00", "2026-08-05")
    b = bk("ORD-1", "UTR-A", "107.00", "2026-08-05")  # ref matches, amount off
    u = UnmatchedRecord(RecordSource.BANK, b, "no_fuzzy_match")
    rec = classify_one([u], [g], [b], [])
    assert rec.type == ExceptionType.AMOUNT_MISMATCH


def test_date_mismatch_gateway():
    g = gw("ORD-1", "100.00", "2026-08-05")
    b = bk("ORD-1", "UTR-A", "100.00", "2026-08-20")  # same amount, far date
    u = UnmatchedRecord(RecordSource.GATEWAY, g, "no_fuzzy_match")
    rec = classify_one([u], [g], [b], [])
    assert rec.type == ExceptionType.DATE_MISMATCH


def test_rounding_diff_gateway():
    g = gw("ORD-1", "100.00", "2026-08-05")
    b = bk("ORD-1", "UTR-A", "100.01", "2026-08-05")  # 1 paise off
    u = UnmatchedRecord(RecordSource.GATEWAY, g, "no_fuzzy_match")
    rec = classify_one([u], [g], [b], [])
    assert rec.type == ExceptionType.ROUNDING_DIFF


def test_split_settlement_gateway():
    g = gw("ORD-S", "100.00", "2026-08-05")
    b1 = bk("ORD-S", "UTR-S1", "60.00", "2026-08-05")
    b2 = bk("ORD-S", "UTR-S2", "40.00", "2026-08-05")
    u = UnmatchedRecord(RecordSource.GATEWAY, g, "no_fuzzy_match")
    rec = classify_one([u], [g], [b1, b2], [])
    assert rec.type == ExceptionType.SPLIT_SETTLEMENT


def test_split_settlement_bank():
    g = gw("ORD-S", "100.00", "2026-08-05")
    b1 = bk("ORD-S", "UTR-S1", "60.00", "2026-08-05")
    b2 = bk("ORD-S", "UTR-S2", "40.00", "2026-08-05")
    u = UnmatchedRecord(RecordSource.BANK, b1, "no_fuzzy_match")
    rec = classify_one([u], [g], [b1, b2], [])
    assert rec.type == ExceptionType.SPLIT_SETTLEMENT


def test_unresolved_ambiguous():
    g = gw("ORD-0", "100.00", "2026-08-05")  # no counterpart anywhere
    u = UnmatchedRecord(RecordSource.GATEWAY, g, "no_fuzzy_match")
    rec = classify_one([u], [g], [], [])
    assert rec.type == ExceptionType.UNRESOLVED_AMBIGUOUS


# --- full generated-data integration ------------------------------------------

def test_full_pipeline_classification():
    gateway, bank, ledger = load_sources(Path(__file__).resolve().parent.parent / "data")
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
    exceptions = classify_exceptions(fuzzy_unmatched, gateway, bank, ledger)
    report = build_exceptions_report(exceptions, len(gateway), len(bank), len(ledger))

    # nothing dropped: every leftover record gets exactly one exception
    assert report["summary"]["total_exceptions"] == len(fuzzy_unmatched)
    assert report["summary"]["total_exceptions"] == 24

    by_type = report["summary"]["by_type"]
    # all nine types present as keys
    assert set(by_type.keys()) == set(ExceptionType.ALL)
    # the three categories that survive as genuine leftover exceptions
    assert by_type[ExceptionType.MISSING_SETTLEMENT] == 6
    assert by_type[ExceptionType.ORPHAN_LEDGER] == 3
    assert by_type[ExceptionType.BATCH_SETTLEMENT] == 15
    # the resolved edge-case categories produce zero exceptions (they matched)
    assert by_type[ExceptionType.SPLIT_SETTLEMENT] == 0
    assert by_type[ExceptionType.ROUNDING_DIFF] == 0
    assert by_type[ExceptionType.AMOUNT_MISMATCH] == 0
    # 9 distinct economic events: 3 missing + 3 orphan + 3 batch
    assert report["summary"]["distinct_events"] == 9

    # well-structured: every exception carries the required fields
    for e in report["exceptions"]:
        assert e["exception_id"].startswith("EXC-")
        assert e["type"] in ExceptionType.ALL
        assert e["source"] in ("gateway", "bank", "ledger")
        assert isinstance(e["evidence"], dict)
