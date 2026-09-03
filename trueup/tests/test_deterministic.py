"""Tests for the deterministic matcher: micro-fixtures + full generated run."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.data_generator import build_dataset, write_dataset
from src.deterministic_matcher import (
    REASON_AMBIGUOUS_BANK,
    REASON_NO_BANK_MATCH,
    REASON_NO_GATEWAY_MATCH,
    REASON_NO_PAYMENT_FOUND,
    build_summary,
    load_sources,
    match_exact,
)
from src.schemas import (
    BankSettlement,
    GatewayTransaction,
    MatchPass,
    MerchantLedger,
    RecordSource,
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


def sources_by_key(gateway, bank, ledger):
    matched, unmatched = match_exact(gateway, bank, ledger)
    return matched, {(u.source, u.key): u for u in unmatched}


def test_clean_triple_matches_fully():
    matched, _ = sources_by_key([gw("ORD-1")], [bk("ORD-1")], [ld("ORD-1")])
    assert len(matched) == 1
    m = matched[0]
    assert m.match_pass is MatchPass.DETERMINISTIC
    assert m.method == "exact_order_id"
    assert m.confidence == 1.0
    assert m.amount_agrees is True
    assert m.date_lag_days == 0
    assert m.is_full_triple() is True


def test_fee_case_matches_but_amount_flagged():
    matched, _ = sources_by_key(
        [gw("ORD-1", amount="1000.00", fee="25.00")],
        [bk("ORD-1", amount="975.00")],
        [ld("ORD-1", amount="1000.00")])
    assert len(matched) == 1
    assert matched[0].amount_agrees is False


def test_rounding_diff_matches_with_paise_delta():
    matched, _ = sources_by_key(
        [gw("ORD-1", amount="100.00")],
        [bk("ORD-1", amount="100.02")],
        [ld("ORD-1", amount="100.00")])
    assert len(matched) == 1
    assert matched[0].amount_agrees is False


def test_date_drift_recorded_in_lag():
    matched, _ = sources_by_key(
        [gw("ORD-1", day="2026-08-05")],
        [bk("ORD-1", day="2026-08-08")],
        [ld("ORD-1", day="2026-08-05")])
    assert matched[0].date_lag_days == 3


def test_split_leaves_every_side_unmatched():
    matched, unmatched = sources_by_key(
        [gw("ORD-1", amount="100.00")],
        [bk("ORD-1", utr="UTR-A", amount="60.00"),
         bk("ORD-1", utr="UTR-B", amount="40.00")],
        [ld("ORD-1", amount="100.00")])
    assert matched == []
    g = unmatched[(RecordSource.GATEWAY, "ORD-1")]
    assert g.reason_hint == REASON_AMBIGUOUS_BANK
    assert sorted(g.candidates) == ["UTR-A", "UTR-B"]
    assert (RecordSource.BANK, "UTR-A") in unmatched
    assert (RecordSource.BANK, "UTR-B") in unmatched


def test_batch_members_and_credit_all_unmatched():
    matched, unmatched = sources_by_key(
        [gw("ORD-1"), gw("ORD-2"), gw("ORD-3")],
        [bk("N/A-BATCH-1", utr="UTR-X", amount="300.00")],
        [ld("ORD-1"), ld("ORD-2"), ld("ORD-3")])
    assert matched == []
    for oid in ("ORD-1", "ORD-2", "ORD-3"):
        assert unmatched[(RecordSource.GATEWAY, oid)].reason_hint \
            == REASON_NO_BANK_MATCH
    assert unmatched[(RecordSource.BANK, "UTR-X")].reason_hint \
        == REASON_NO_GATEWAY_MATCH


def test_case_only_garble_resolves_via_normalization():
    matched, unmatched = sources_by_key(
        [gw("ORD-10060")],
        [bk(" ord-10060 ", utr="UTR-Z")],
        [])
    assert len(matched) == 1
    assert matched[0].bank_settlement.utr == "UTR-Z"
    assert matched[0].merchant_ledger is None
    assert unmatched == {}


def test_hard_garbled_ref_has_no_candidate():
    _, unmatched = sources_by_key([gw("ORD-1057")], [bk("ORD-10")], [])
    u = unmatched[(RecordSource.GATEWAY, "ORD-1057")]
    assert u.reason_hint == REASON_NO_BANK_MATCH
    assert u.candidates == []


def test_colliding_duplicate_refs_stay_ambiguous():
    _, unmatched = sources_by_key(
        [gw("ORD-62")],
        [bk("ORD-62", utr="UTR-REAL"),
         bk("ORD-62", utr="UTR-GARBLED-DUP")],
        [])
    g = unmatched[(RecordSource.GATEWAY, "ORD-62")]
    assert g.reason_hint == REASON_AMBIGUOUS_BANK
    assert set(g.candidates) == {"UTR-REAL", "UTR-GARBLED-DUP"}
    assert (RecordSource.BANK, "UTR-REAL") in unmatched
    assert (RecordSource.BANK, "UTR-GARBLED-DUP") in unmatched


def test_no_record_consumed_twice():
    matched, unmatched_list = match_exact(
        [gw("ORD-1"), gw("ORD-2"), gw("ORD-3")],
        [bk("ORD-1", utr="UTR-A"), bk("ORD-2", utr="UTR-B"),
         bk("ORD-2", utr="UTR-C")],
        [ld("ORD-1"), ld("ORD-2"), ld("ORD-9")])
    utrs = [m.bank_settlement.utr for m in matched if m.bank_settlement]
    utrs += [u.record.utr for u in unmatched_list if u.source is RecordSource.BANK]
    oids = [m.gateway_txn.order_id for m in matched]
    oids += [u.key for u in unmatched_list if u.source is RecordSource.GATEWAY]
    led = [m.merchant_ledger.order_id for m in matched if m.merchant_ledger]
    led += [u.key for u in unmatched_list if u.source is RecordSource.LEDGER]
    assert len(set(utrs)) == len(utrs)
    assert len(set(oids)) == len(oids)
    assert len(set(led)) == len(led)


def test_missing_settlement_and_orphan_ledger_reasons():
    matched, unmatched = sources_by_key(
        [gw("ORD-M")], [], [ld("ORD-O")])
    assert matched == []
    assert unmatched[(RecordSource.GATEWAY, "ORD-M")].reason_hint \
        == REASON_NO_BANK_MATCH
    assert unmatched[(RecordSource.LEDGER, "ORD-O")].reason_hint \
        == REASON_NO_PAYMENT_FOUND


def test_malformed_amount_fails_fast_with_row_and_field(tmp_path: Path):
    path = tmp_path / "gateway_log.csv"
    path.write_text(
        "order_id,amount,txn_date,status,gateway_fee\n"
        "ORD-1,12.34,2026-08-05,success,0.00\n"
        "ORD-2,not-a-number,2026-08-05,success,0.00\n",
        encoding="utf-8")
    from src.deterministic_matcher import load_gateway
    with pytest.raises(ValueError) as excinfo:
        load_gateway(path)
    message = str(excinfo.value)
    assert "line 3" in message and "amount" in message


def test_duplicate_order_id_raises_at_load(tmp_path: Path):
    path = tmp_path / "gateway_log.csv"
    path.write_text(
        "order_id,amount,txn_date,status,gateway_fee\n"
        "ORD-1,12.34,2026-08-05,success,0.00\n"
        "ORD-1,10.00,2026-08-06,success,0.00\n",
        encoding="utf-8")
    from src.deterministic_matcher import load_gateway
    with pytest.raises(ValueError, match="duplicate order_id"):
        load_gateway(path)


@pytest.fixture(scope="module")
def generated(tmp_path_factory) -> dict:
    data_dir = tmp_path_factory.mktemp("data")
    write_dataset(build_dataset(), data_dir)
    return {"records": load_sources(data_dir), "dir": data_dir}


def test_generated_dataset_baseline_counts(generated):
    gateway, bank, ledger = generated["records"]
    matched, unmatched = match_exact(gateway, bank, ledger)
    summary = build_summary(matched, unmatched,
                            len(gateway), len(bank), len(ledger))
    assert summary["gateway_matched"] == 59
    assert summary["gateway_total"] == 80
    assert summary["match_rate"] == pytest.approx(59 / 80)
    assert summary["full_triples"] == 58
    assert summary["unmatched_gateway"] == 21
    assert summary["unmatched_bank"] == 16
    assert summary["unmatched_ledger"] == 20
    assert summary["amount_disagreements"] == 16


def test_generated_dataset_known_interactions(generated):
    gateway, bank, ledger = generated["records"]
    matched, unmatched = match_exact(gateway, bank, ledger)

    dup_collision = next(u for u in unmatched
                         if u.source is RecordSource.GATEWAY
                         and u.key == "ORD-10062")
    assert dup_collision.reason_hint == REASON_AMBIGUOUS_BANK
    assert set(dup_collision.candidates) == {"UTR-50059", "UTR-50060"}

    split_case = next(u for u in unmatched
                      if u.source is RecordSource.GATEWAY
                      and u.key == "ORD-10044")
    assert split_case.reason_hint == REASON_AMBIGUOUS_BANK
    assert set(split_case.candidates) == {"UTR-50044", "UTR-50045"}

    keys = [(u.source, u.key) for u in unmatched]
    assert (RecordSource.BANK, "UTR-50059") in keys
    assert (RecordSource.BANK, "UTR-50060") in keys
    for utr in ("UTR-50055", "UTR-50056", "UTR-50057"):
        assert (RecordSource.BANK, utr) in keys
    for utr in ("UTR-50052", "UTR-50053", "UTR-50054"):
        assert (RecordSource.BANK, utr) in keys

    by_order = {m.order_id: m for m in matched}
    assert by_order["ORD-10060"].bank_settlement.utr == "UTR-50058"
    assert by_order["ORD-10034"].date_lag_days == 2
    assert by_order["ORD-10026"].amount_agrees is False
    assert by_order["ORD-10001"].amount_agrees is True
