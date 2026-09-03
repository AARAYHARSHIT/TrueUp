"""Pass 1 deterministic matcher for TrueUp.

Exact-key matching on the primary key: normalized order_id (gateway/ledger)
<-> order_id_ref (bank). Keys are compared after strip().upper() so case-only
corruption resolves here, while real garbles/splits/batches stay unmatched for
the fuzzy pass. The matching core is pure; CSV loading fails fast with row
number + field name. Run: python -m src.deterministic_matcher
"""
from __future__ import annotations

import csv
import logging
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from src.data_generator import BANK_CSV, GATEWAY_CSV, LEDGER_CSV
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

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

MATCH_PASS = MatchPass.DETERMINISTIC
METHOD = "exact_order_id"
CONFIDENCE = 1.0

REASON_NO_BANK_MATCH = "no_exact_bank_match"
REASON_AMBIGUOUS_BANK = "ambiguous_bank_candidates"
REASON_NO_GATEWAY_MATCH = "no_gateway_match"
REASON_NO_PAYMENT_FOUND = "no_payment_found"


def normalize_key(value: str) -> str:
    return value.strip().upper()


def _fail(path: Path, line_num: int, message: str) -> None:
    raise ValueError(f"{path.name}: line {line_num}: {message}")


def _require_fields(row: dict[str, str], fields: tuple[str, ...],
                    path: Path, line_num: int) -> None:
    for fld in fields:
        if row.get(fld) is None or row.get(fld, "").strip() == "":
            _fail(path, line_num, f"missing or empty field {fld!r}")


def _to_decimal(raw: str, field: str, path: Path, line_num: int) -> Decimal:
    try:
        return Decimal(raw.strip())
    except InvalidOperation:
        _fail(path, line_num, f"field {field!r} is not a valid amount: {raw!r}")


def _to_date(raw: str, field: str, path: Path, line_num: int) -> date:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        _fail(path, line_num, f"field {field!r} is not an ISO date: {raw!r}")


def load_gateway(path: Path) -> list[GatewayTransaction]:
    records: list[GatewayTransaction] = []
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            _require_fields(
                row, ("order_id", "amount", "txn_date", "status", "gateway_fee"),
                path, reader.line_num)
            oid = row["order_id"].strip()
            key = normalize_key(oid)
            if key in seen:
                _fail(path, reader.line_num, f"duplicate order_id {oid!r}")
            seen.add(key)
            records.append(GatewayTransaction(
                order_id=oid,
                amount=_to_decimal(row["amount"], "amount", path, reader.line_num),
                txn_date=_to_date(row["txn_date"], "txn_date", path, reader.line_num),
                status=row["status"].strip(),
                gateway_fee=_to_decimal(
                    row["gateway_fee"], "gateway_fee", path, reader.line_num),
            ))
    return records


def load_bank(path: Path) -> list[BankSettlement]:
    records: list[BankSettlement] = []
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            _require_fields(
                row, ("utr", "settlement_amount", "settlement_date", "order_id_ref"),
                path, reader.line_num)
            utr = row["utr"].strip()
            if utr in seen:
                _fail(path, reader.line_num, f"duplicate utr {utr!r}")
            seen.add(utr)
            records.append(BankSettlement(
                utr=utr,
                settlement_amount=_to_decimal(
                    row["settlement_amount"], "settlement_amount",
                    path, reader.line_num),
                settlement_date=_to_date(
                    row["settlement_date"], "settlement_date",
                    path, reader.line_num),
                order_id_ref=row["order_id_ref"].strip(),
            ))
    return records


def load_ledger(path: Path) -> list[MerchantLedger]:
    records: list[MerchantLedger] = []
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            _require_fields(
                row, ("order_id", "expected_amount", "entry_date", "notes"),
                path, reader.line_num)
            oid = row["order_id"].strip()
            key = normalize_key(oid)
            if key in seen:
                _fail(path, reader.line_num, f"duplicate order_id {oid!r}")
            seen.add(key)
            records.append(MerchantLedger(
                order_id=oid,
                expected_amount=_to_decimal(
                    row["expected_amount"], "expected_amount",
                    path, reader.line_num),
                entry_date=_to_date(
                    row["entry_date"], "entry_date", path, reader.line_num),
                notes=row["notes"].strip(),
            ))
    return records


def load_sources(data_dir: Path = DATA_DIR
                 ) -> tuple[list[GatewayTransaction], list[BankSettlement],
                            list[MerchantLedger]]:
    return (load_gateway(data_dir / GATEWAY_CSV),
            load_bank(data_dir / BANK_CSV),
            load_ledger(data_dir / LEDGER_CSV))


def match_exact(gateway: list[GatewayTransaction],
                bank: list[BankSettlement],
                ledger: list[MerchantLedger]
                ) -> tuple[list[MatchResult], list[UnmatchedRecord]]:
    bank_by_ref: dict[str, list[BankSettlement]] = defaultdict(list)
    for b in bank:
        bank_by_ref[normalize_key(b.order_id_ref)].append(b)
    ledger_by_id: dict[str, MerchantLedger] = {
        normalize_key(entry.order_id): entry for entry in ledger}

    matched: list[MatchResult] = []
    unmatched: list[UnmatchedRecord] = []
    consumed_utrs: set[str] = set()
    consumed_ledger_ids: set[str] = set()

    for g in gateway:
        candidates = bank_by_ref.get(normalize_key(g.order_id), [])
        if not candidates:
            unmatched.append(UnmatchedRecord(
                RecordSource.GATEWAY, g, REASON_NO_BANK_MATCH))
            continue
        if len(candidates) > 1:
            unmatched.append(UnmatchedRecord(
                RecordSource.GATEWAY, g, REASON_AMBIGUOUS_BANK,
                [c.utr for c in candidates]))
            continue

        settled = candidates[0]
        entry = ledger_by_id.get(normalize_key(g.order_id))
        amount_agrees = g.amount == settled.settlement_amount and (
            entry is None or g.amount == entry.expected_amount)
        date_lag_days = (settled.settlement_date - g.txn_date).days
        matched.append(MatchResult(
            gateway_txn=g,
            bank_settlement=settled,
            merchant_ledger=entry,
            match_pass=MATCH_PASS,
            method=METHOD,
            confidence=CONFIDENCE,
            amount_agrees=amount_agrees,
            date_lag_days=date_lag_days,
        ))
        consumed_utrs.add(settled.utr)
        if entry is not None:
            consumed_ledger_ids.add(normalize_key(entry.order_id))

    for b in bank:
        if b.utr not in consumed_utrs:
            unmatched.append(UnmatchedRecord(
                RecordSource.BANK, b, REASON_NO_GATEWAY_MATCH))
    for entry in ledger:
        if normalize_key(entry.order_id) not in consumed_ledger_ids:
            unmatched.append(UnmatchedRecord(
                RecordSource.LEDGER, entry, REASON_NO_PAYMENT_FOUND))

    logger.info("deterministic pass: %d matched, %d unmatched records",
                len(matched), len(unmatched))
    return matched, unmatched


def build_summary(matched: list[MatchResult],
                  unmatched: list[UnmatchedRecord],
                  gateway_total: int, bank_total: int,
                  ledger_total: int) -> dict[str, object]:
    by_source = {source: 0 for source in RecordSource}
    for u in unmatched:
        by_source[u.source] += 1
    bank_consumed = sum(1 for m in matched if m.bank_settlement is not None)
    ledger_linked = sum(1 for m in matched if m.merchant_ledger is not None)
    full_triples = sum(1 for m in matched if m.is_full_triple())
    amount_flags = sum(1 for m in matched if not m.amount_agrees)
    date_drifts = sum(1 for m in matched if m.date_lag_days and m.date_lag_days > 1)
    return {
        "gateway_matched": len(matched),
        "gateway_total": gateway_total,
        "match_rate": len(matched) / gateway_total if gateway_total else 0.0,
        "bank_consumed": bank_consumed,
        "bank_total": bank_total,
        "ledger_linked": ledger_linked,
        "ledger_total": ledger_total,
        "full_triples": full_triples,
        "amount_disagreements": amount_flags,
        "date_drifts": date_drifts,
        "unmatched_gateway": by_source[RecordSource.GATEWAY],
        "unmatched_bank": by_source[RecordSource.BANK],
        "unmatched_ledger": by_source[RecordSource.LEDGER],
        "unmatched_total": len(unmatched),
    }


def _print_summary(s: dict[str, object]) -> None:
    rate_pct = float(s["match_rate"]) * 100
    print(f"{'─' * 3} Pass 1: Deterministic Matcher {'─' * 39}")
    print(
        f"✓ matched {s['gateway_matched']}/{s['gateway_total']} ({rate_pct:.2f})   "
        f"⚠ flagged {s['amount_disagreements']} + {s['date_drifts']}   "
        f"✗ unmatched {s['unmatched_total']}"
    )
    print(f"  gateway side ....... {s['gateway_matched']}/{s['gateway_total']} matched")
    print(f"  bank side .......... {s['bank_consumed']}/{s['bank_total']} consumed")
    print(f"  ledger side ........ {s['ledger_linked']}/{s['ledger_total']} linked")
    print(f"  full triples ....... {s['full_triples']} (gateway+bank+ledger)")
    print(f"  leftover records ... {s['unmatched_gateway']} gateway, "
          f"{s['unmatched_bank']} bank, {s['unmatched_ledger']} ledger")
    print(f"  baseline match rate: {rate_pct:.2f}% "
          f"(gateway-side; flagged amounts need fee/refund/rounding review)")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    gateway, bank, ledger = load_sources(DATA_DIR)
    matched, unmatched = match_exact(gateway, bank, ledger)
    summary = build_summary(matched, unmatched, len(gateway), len(bank), len(ledger))
    _print_summary(summary)


if __name__ == "__main__":
    main()
