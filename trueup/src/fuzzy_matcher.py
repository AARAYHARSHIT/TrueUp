"""Pass 2 fuzzy matcher for TrueUp.

Second pass on unmatched records from deterministic pass.
Strategies: amount tolerance (<=5 Rs), date window (5 days), edit distance
(rapidfuzz >= 80%), split settlement detection, batch settlement detection,
duplicate near-match flagging. Each match gets a confidence score.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from src.data_generator import BANK_CSV, GATEWAY_CSV, LEDGER_CSV
from src.deterministic_matcher import (
    load_sources,
    match_exact,
    normalize_key,
    DATA_DIR,
)
from src.schemas import (
    BankSettlement,
    GatewayTransaction,
    MatchPass,
    MatchResult,
    MerchantLedger,
    RecordSource,
    UnmatchedRecord,
)

logger = logging.getLogger(__name__)

MATCH_PASS = MatchPass.FUZZY

AMOUNT_TOLERANCE = Decimal("5.00")
DATE_WINDOW_DAYS = 5
EDIT_DISTANCE_THRESHOLD = 80

REASON_AMOUNT_MISMATCH = "amount_outside_tolerance"
REASON_DATE_MISMATCH = "date_outside_window"
REASON_SPLIT_DETECTED = "split_settlement_detected"
REASON_BATCH_DETECTED = "batch_settlement_detected"
REASON_DUPLICATE_AMBIGUOUS = "duplicate_near_match"
REASON_NO_FUZZY_MATCH = "no_fuzzy_match"
REASON_MULTIPLE_CANDIDATES = "multiple_fuzzy_candidates"


def _amount_score(gateway_amt: Decimal, bank_amt: Decimal) -> float:
    diff = abs(gateway_amt - bank_amt)
    if diff <= AMOUNT_TOLERANCE:
        return 1.0 - float(diff / AMOUNT_TOLERANCE) * 0.2
    return 0.0


def _date_score(txn_date: date, settlement_date: date) -> float:
    lag = abs((settlement_date - txn_date).days)
    if lag <= DATE_WINDOW_DAYS:
        return 1.0 - (lag / DATE_WINDOW_DAYS) * 0.15
    return 0.0


def _edit_distance_score(ref1: str, ref2: str) -> float:
    score = fuzz.ratio(ref1.upper(), ref2.upper())
    if score >= EDIT_DISTANCE_THRESHOLD:
        return score / 100.0 * 0.35
    return 0.0


def _calculate_confidence(
    amount_sc: float,
    date_sc: float,
    edit_sc: float,
    has_ledger: bool,
) -> float:
    base = amount_sc + date_sc + edit_sc
    if has_ledger:
        base += 0.15
    return min(base, 1.0)


def find_split_candidates(
    gateway_txn: GatewayTransaction,
    bank_records: list[BankSettlement],
) -> list[tuple[list[BankSettlement], float]]:
    """Find combinations of 2 bank settlements that sum to gateway amount."""
    candidates = []
    target = gateway_txn.amount
    for i, b1 in enumerate(bank_records):
        for b2 in bank_records[i + 1 :]:
            total = b1.settlement_amount + b2.settlement_amount
            if total == target:
                avg_date = b1.settlement_date + (b2.settlement_date - b1.settlement_date) / 2
                amt_sc = 1.0
                date_sc = _date_score(gateway_txn.txn_date, avg_date)
                edit_sc = max(
                    _edit_distance_score(gateway_txn.order_id, b1.order_id_ref),
                    _edit_distance_score(gateway_txn.order_id, b2.order_id_ref),
                )
                conf = _calculate_confidence(amt_sc, date_sc, edit_sc, False)
                candidates.append(([b1, b2], conf))
    return candidates


def find_batch_candidates(
    gateway_txns: list[GatewayTransaction],
    bank_record: BankSettlement,
) -> list[tuple[list[GatewayTransaction], float]]:
    """Find groups of gateway txns that sum to a single bank settlement (2-4 items)."""
    candidates = []
    target = bank_record.settlement_amount
    n = min(len(gateway_txns), 6)
    for size in range(2, 5):
        for idxs in _combinations(range(n), size):
            subset = [gateway_txns[i] for i in idxs]
            total = sum(g.amount for g in subset)
            if total == target:
                min_date = min(g.txn_date for g in subset)
                date_sc = _date_score(min_date, bank_record.settlement_date)
                edit_sc = max(
                    _edit_distance_score(g.order_id, bank_record.order_id_ref)
                    for g in subset
                )
                conf = _calculate_confidence(1.0, date_sc, edit_sc, False)
                candidates.append((subset, conf))
    return candidates


def _combinations(items: list[int], k: int) -> list[tuple[int, ...]]:
    if k == 0:
        return [()]
    if k > len(items):
        return []
    result = []
    for i in range(len(items) - k + 1):
        for rest in _combinations(items[i + 1:], k - 1):
            result.append((items[i],) + rest)
    return result


def match_fuzzy(
    unmatched_gateway: list[UnmatchedRecord],
    unmatched_bank: list[UnmatchedRecord],
    unmatched_ledger: list[UnmatchedRecord],
    all_gateway: list[GatewayTransaction],
    all_bank: list[BankSettlement],
    all_ledger: list[MerchantLedger],
) -> tuple[list[MatchResult], list[UnmatchedRecord]]:
    gateway_records = [u.record for u in unmatched_gateway if u.source == RecordSource.GATEWAY]
    bank_records = [u.record for u in unmatched_bank if u.source == RecordSource.BANK]
    ledger_records = [u.record for u in unmatched_ledger if u.source == RecordSource.LEDGER]

    bank_by_utr = {b.utr: b for b in bank_records}
    ledger_by_id = {normalize_key(l.order_id): l for l in ledger_records}

    matched: list[MatchResult] = []
    new_unmatched: list[UnmatchedRecord] = []
    consumed_utrs: set[str] = set()
    consumed_gateway_ids: set[str] = set()
    consumed_ledger_ids: set[str] = set()

    for g in gateway_records:
        if normalize_key(g.order_id) in consumed_gateway_ids:
            continue

        split_cands = find_split_candidates(g, bank_records)
        if split_cands:
            best_split = max(split_cands, key=lambda x: x[1])
            settlements, conf = best_split
            if conf >= 0.6:
                for b in settlements:
                    consumed_utrs.add(b.utr)
                consumed_gateway_ids.add(normalize_key(g.order_id))
                entry = ledger_by_id.get(normalize_key(g.order_id))
                if entry:
                    consumed_ledger_ids.add(normalize_key(entry.order_id))
                date_lag = (settlements[0].settlement_date - g.txn_date).days
                matched.append(MatchResult(
                    gateway_txn=g,
                    bank_settlement=settlements[0],
                    merchant_ledger=entry,
                    match_pass=MATCH_PASS,
                    method="split_settlement",
                    confidence=conf,
                    amount_agrees=True,
                    date_lag_days=date_lag,
                ))
                continue

        batch_matched = False
        batch_related = [b for b in bank_records if b.utr not in consumed_utrs]
        for b in batch_related:
            other_gateway = [g2 for g2 in gateway_records
                           if normalize_key(g2.order_id) not in consumed_gateway_ids
                           and g2 != g]
            batch_cands = find_batch_candidates([g] + other_gateway, b)
            if batch_cands:
                best_batch = max(batch_cands, key=lambda x: x[1])
                members, conf = best_batch
                if conf >= 0.6 and len(members) >= 2:
                    consumed_utrs.add(b.utr)
                    for m in members:
                        consumed_gateway_ids.add(normalize_key(m.order_id))
                    entry = ledger_by_id.get(normalize_key(g.order_id))
                    if entry:
                        consumed_ledger_ids.add(normalize_key(entry.order_id))
                    date_lag = (b.settlement_date - g.txn_date).days
                    matched.append(MatchResult(
                        gateway_txn=g,
                        bank_settlement=b,
                        merchant_ledger=entry,
                        match_pass=MATCH_PASS,
                        method="batch_settlement",
                        confidence=conf,
                        amount_agrees=True,
                        date_lag_days=date_lag,
                    ))
                    batch_matched = True
                    break
        if batch_matched:
            continue

        best_match: Optional[BankSettlement] = None
        best_score = 0.0
        best_conf = 0.0
        ambiguous = False
        candidate_utrs: list[str] = []

        for b in bank_records:
            if b.utr in consumed_utrs:
                continue
            amt_sc = _amount_score(g.amount, b.settlement_amount)
            if amt_sc == 0.0:
                continue
            date_sc = _date_score(g.txn_date, b.settlement_date)
            if date_sc == 0.0:
                continue
            edit_sc = _edit_distance_score(g.order_id, b.order_id_ref)
            if edit_sc == 0.0:
                continue

            has_ledger = normalize_key(g.order_id) in ledger_by_id
            conf = _calculate_confidence(amt_sc, date_sc, edit_sc, has_ledger)

            if conf > best_conf:
                if best_match is not None:
                    ambiguous = True
                best_match = b
                best_conf = conf
                candidate_utrs = [b.utr]
            elif conf == best_conf and conf > 0:
                ambiguous = True
                candidate_utrs.append(b.utr)

        if best_match and not ambiguous and best_conf >= 0.5:
            consumed_utrs.add(best_match.utr)
            consumed_gateway_ids.add(normalize_key(g.order_id))
            entry = ledger_by_id.get(normalize_key(g.order_id))
            if entry:
                consumed_ledger_ids.add(normalize_key(entry.order_id))
            date_lag = (best_match.settlement_date - g.txn_date).days
            amount_agrees = abs(g.amount - best_match.settlement_amount) <= AMOUNT_TOLERANCE
            matched.append(MatchResult(
                gateway_txn=g,
                bank_settlement=best_match,
                merchant_ledger=entry,
                match_pass=MATCH_PASS,
                method="fuzzy_amount_date_edit",
                confidence=best_conf,
                amount_agrees=amount_agrees,
                date_lag_days=date_lag,
            ))
        elif best_match and ambiguous:
            new_unmatched.append(UnmatchedRecord(
                RecordSource.GATEWAY, g, REASON_DUPLICATE_AMBIGUOUS, candidate_utrs))
        else:
            new_unmatched.append(UnmatchedRecord(
                RecordSource.GATEWAY, g, REASON_NO_FUZZY_MATCH))

    for b in bank_records:
        if b.utr not in consumed_utrs:
            new_unmatched.append(UnmatchedRecord(
                RecordSource.BANK, b, REASON_NO_FUZZY_MATCH))

    for entry in ledger_records:
        if normalize_key(entry.order_id) not in consumed_ledger_ids:
            new_unmatched.append(UnmatchedRecord(
                RecordSource.LEDGER, entry, REASON_NO_FUZZY_MATCH))

    logger.info("fuzzy pass: %d matched, %d unmatched records",
                len(matched), len(new_unmatched))
    return matched, new_unmatched


def build_fuzzy_summary(
    matched: list[MatchResult],
    unmatched: list[UnmatchedRecord],
    gateway_total: int,
    bank_total: int,
    ledger_total: int,
) -> dict[str, object]:
    by_source = {source: 0 for source in RecordSource}
    for u in unmatched:
        by_source[u.source] += 1
    split_count = sum(1 for m in matched if m.method == "split_settlement")
    batch_count = sum(1 for m in matched if m.method == "batch_settlement")
    fuzzy_count = sum(1 for m in matched if m.method == "fuzzy_amount_date_edit")
    dup_flags = sum(1 for u in unmatched if u.reason_hint == REASON_DUPLICATE_AMBIGUOUS)
    return {
        "gateway_matched": len(matched),
        "gateway_total": gateway_total,
        "match_rate": len(matched) / gateway_total if gateway_total else 0.0,
        "split_detected": split_count,
        "batch_detected": batch_count,
        "fuzzy_matches": fuzzy_count,
        "duplicate_flagged": dup_flags,
        "unmatched_gateway": by_source[RecordSource.GATEWAY],
        "unmatched_bank": by_source[RecordSource.BANK],
        "unmatched_ledger": by_source[RecordSource.LEDGER],
        "unmatched_total": len(unmatched),
    }


def _print_fuzzy_summary(s: dict[str, object]) -> None:
    rate_pct = float(s["match_rate"]) * 100
    print(f"{'─' * 3} Pass 2: Fuzzy Matcher {'─' * 45}")
    print(
        f"✓ matched {s['gateway_matched']}/{s['gateway_total']} ({rate_pct:.2f})   "
        f"split={s['split_detected']} batch={s['batch_detected']} fuzzy={s['fuzzy_matches']}   "
        f"⚠ dup_flagged={s['duplicate_flagged']}   ✗ unmatched {s['unmatched_total']}"
    )
    print(f"  gateway side ....... {s['gateway_matched']}/{s['gateway_total']} matched")
    print(f"  leftover records ... {s['unmatched_gateway']} gateway, "
          f"{s['unmatched_bank']} bank, {s['unmatched_ledger']} ledger")
    print(f"  fuzzy match rate ... {rate_pct:.2f}% "
          f"(amount<=5, date<=5d, edit>=80%, split/batch detection)")


def main() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    gateway, bank, ledger = load_sources(DATA_DIR)
    det_matched, det_unmatched = match_exact(gateway, bank, ledger)

    unmatched_by_source = defaultdict(list)
    for u in det_unmatched:
        unmatched_by_source[u.source].append(u)

    fuzzy_matched, fuzzy_unmatched = match_fuzzy(
        unmatched_by_source[RecordSource.GATEWAY],
        unmatched_by_source[RecordSource.BANK],
        unmatched_by_source[RecordSource.LEDGER],
        gateway, bank, ledger,
    )

    all_matched = det_matched + fuzzy_matched
    all_unmatched = fuzzy_unmatched

    summary = build_fuzzy_summary(
        all_matched, all_unmatched,
        len(gateway), len(bank), len(ledger),
    )
    _print_fuzzy_summary(summary)

    det_rate = len(det_matched) / len(gateway) * 100
    fuzzy_rate = summary["match_rate"] * 100
    print(f"\nBaseline (deterministic): {det_rate:.2f}%")
    print(f"After fuzzy pass:         {fuzzy_rate:.2f}%")
    print(f"Improvement:              {fuzzy_rate - det_rate:+.2f}pp")


if __name__ == "__main__":
    main()