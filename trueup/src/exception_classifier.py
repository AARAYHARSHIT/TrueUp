"""Pass 3 exception classifier for TrueUp.

Takes the still-unmatched records after the deterministic + fuzzy passes and
names exactly one exception type for every one of them -- nothing is dropped.
Classification is a pure, precedence-ordered rule engine (suggestions.txt #15):
each unmatched record is cross-referenced against ALL three sources (not just
its own row) so the *nature* of the gap is named, then assigned the single
best type.

The nine closed-set types live in the ExceptionType namespace (rules.md: enums
for closed sets). Every emitted exception carries evidence (candidates
considered, scores, why rejected) so the Day-6 LLM resolver has structured
input (suggestions.txt #17).

Run: python -m src.exception_classifier   (writes reports/exceptions.json)
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from src.data_generator import BANK_CSV, GATEWAY_CSV, LEDGER_CSV
from src.deterministic_matcher import (
    DATA_DIR,
    load_sources,
    match_exact,
    normalize_key,
)
from src.fuzzy_matcher import match_fuzzy
from src.schemas import (
    BankSettlement,
    GatewayTransaction,
    MerchantLedger,
    RecordSource,
    UnmatchedRecord,
)

logger = logging.getLogger(__name__)

METHOD = "exception_classifier"

ROUNDING_TOLERANCE = Decimal("0.02")   # 1-2 paise
AMOUNT_TOLERANCE = Decimal("5.00")     # same band the fuzzy pass used
DATE_WINDOW_DAYS = 5
AMOUNT_EDIT_THRESHOLD = 95             # tighter than fuzzy: ORD-100XX ids are alike
BATCH_MEMBER_WINDOW_DAYS = 30
BATCH_MAX_MEMBERS = 4
BATCH_MAX_CANDIDATES = 80


class ExceptionType:
    MISSING_SETTLEMENT = "MISSING_SETTLEMENT"
    MISSING_TXN = "MISSING_TXN"
    ORPHAN_LEDGER = "ORPHAN_LEDGER"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DATE_MISMATCH = "DATE_MISMATCH"
    SPLIT_SETTLEMENT = "SPLIT_SETTLEMENT"
    BATCH_SETTLEMENT = "BATCH_SETTLEMENT"
    ROUNDING_DIFF = "ROUNDING_DIFF"
    UNRESOLVED_AMBIGUOUS = "UNRESOLVED_AMBIGUOUS"

    ALL = (
        MISSING_SETTLEMENT, MISSING_TXN, ORPHAN_LEDGER, AMOUNT_MISMATCH,
        DATE_MISMATCH, SPLIT_SETTLEMENT, BATCH_SETTLEMENT, ROUNDING_DIFF,
        UNRESOLVED_AMBIGUOUS,
    )


@dataclass
class _Context:
    gateway_all: list[GatewayTransaction]
    bank_all: list[BankSettlement]
    ledger_all: list[MerchantLedger]
    gateway_by_id: dict[str, GatewayTransaction] = field(default_factory=dict)
    ledger_by_id: dict[str, MerchantLedger] = field(default_factory=dict)
    bank_by_utr: dict[str, BankSettlement] = field(default_factory=dict)
    bank_by_ref: dict[str, list[BankSettlement]] = field(
        default_factory=lambda: defaultdict(list))


@dataclass
class ExceptionRecord:
    exception_id: str
    type: str
    source: str
    record_id: str
    amount: Optional[str]
    date: Optional[str]
    reason: str
    evidence: dict
    linked_record_ids: list[str]
    event_key: str
    method: str = METHOD


def _build_context(
    gateway: list[GatewayTransaction],
    bank: list[BankSettlement],
    ledger: list[MerchantLedger],
) -> _Context:
    ctx = _Context(gateway_all=gateway, bank_all=bank, ledger_all=ledger)
    for g in gateway:
        ctx.gateway_by_id[normalize_key(g.order_id)] = g
    for l in ledger:
        ctx.ledger_by_id[normalize_key(l.order_id)] = l
    for b in bank:
        ctx.bank_by_utr[b.utr] = b
        ctx.bank_by_ref[normalize_key(b.order_id_ref)].append(b)
    return ctx


def _combos(items: list, k: int):
    if k == 0:
        yield ()
        return
    if k > len(items):
        return
    for i in range(len(items) - k + 1):
        for rest in _combos(items[i + 1:], k - 1):
            yield (items[i],) + rest


def _edit(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return fuzz.ratio(a.upper(), b.upper())


# --- split / batch detection (precomputed once from full data) ----------------

def _detect_splits(ctx: _Context):
    """gateway_key -> list[utr]; utr -> gateway_key (parent)."""
    split_by_gateway: dict[str, list[str]] = {}
    split_bank_to_gateway: dict[str, str] = {}
    for g in ctx.gateway_all:
        key = normalize_key(g.order_id)
        parts = ctx.bank_by_ref.get(key, [])
        if len(parts) >= 2:
            for c in _combos(parts, 2):
                if c[0].settlement_amount + c[1].settlement_amount == g.amount:
                    utrs = [c[0].utr, c[1].utr]
                    split_by_gateway[key] = utrs
                    for u in utrs:
                        split_bank_to_gateway[u] = key
                    break
    return split_by_gateway, split_bank_to_gateway


def _detect_batches(ctx: _Context):
    """batch_utr -> list[gateway_key]; gateway_key -> batch_utr."""
    batch_by_gateway: dict[str, str] = {}
    batch_members: dict[str, list[str]] = {}
    for b in ctx.bank_all:
        if ctx.gateway_by_id.get(normalize_key(b.order_id_ref)) is not None:
            continue  # directly references a single gateway -> not a batch
        # Candidate members: any gateway whose amount could combine into the
        # payout. The exact-sum check is the strong signal, so we don't filter
        # by date here (classification only). Bounded by BATCH_MAX_CANDIDATES.
        pool = [
            x for x in ctx.gateway_all if x.amount <= b.settlement_amount
        ][:BATCH_MAX_CANDIDATES]
        for size in range(2, BATCH_MAX_MEMBERS + 1):
            found = False
            for combo in _combos(pool, size):
                if sum(m.amount for m in combo) == b.settlement_amount:
                    members = [normalize_key(m.order_id) for m in combo]
                    batch_members[b.utr] = members
                    for mk in members:
                        batch_by_gateway[mk] = b.utr
                    found = True
                    break
            if found:
                break
    return batch_by_gateway, batch_members


# --- per-record classifiers (precedence per suggestions.txt #15) --------------

def _classify_gateway(
    g: GatewayTransaction, ctx: _Context, ledger: Optional[MerchantLedger],
    split_by_gateway: dict[str, list[str]],
    batch_by_gateway: dict[str, str],
) -> tuple[str, str, dict, list[str]]:
    ident = g.order_id
    key = normalize_key(ident)

    if key in split_by_gateway:
        utrs = split_by_gateway[key]
        return (ExceptionType.SPLIT_SETTLEMENT,
                f"gateway {ident} splits into {len(utrs)} bank credits summing to "
                f"{g.amount}",
                {"bank_utrs": utrs,
                 "sum": str(sum(ctx.bank_by_utr[u].settlement_amount for u in utrs))},
                utrs, key)

    if key in batch_by_gateway:
        utr = batch_by_gateway[key]
        return (ExceptionType.BATCH_SETTLEMENT,
                f"gateway {ident} is a member of batch payout {utr} "
                f"({ctx.bank_by_utr[utr].settlement_amount})",
                {"batch_utr": utr,
                 "payout": str(ctx.bank_by_utr[utr].settlement_amount)},
                [utr], utr)

    # ROUNDING_DIFF: a related bank credit off by only 1-2 paise.
    for b in ctx.bank_by_ref.get(key, []):
        diff = abs(b.settlement_amount - g.amount)
        if Decimal("0") < diff <= ROUNDING_TOLERANCE:
            return (ExceptionType.ROUNDING_DIFF,
                    f"bank {b.utr} references {ident} but amount off by {diff} (paise)",
                    {"bank_utr": b.utr, "bank_amount": str(b.settlement_amount),
                     "delta": str(diff)},
                    [b.utr], key)

    # AMOUNT_MISMATCH: a near-ref bank credit, same amount band, wrong figure.
    best_bank: Optional[BankSettlement] = None
    best_score = 0.0
    for b in ctx.bank_all:
        if normalize_key(b.order_id_ref) == key:
            continue
        score = _edit(b.order_id_ref, ident)
        if score >= AMOUNT_EDIT_THRESHOLD and score > best_score:
            best_score = score
            best_bank = b
    if best_bank is not None:
        diff = abs(best_bank.settlement_amount - g.amount)
        if diff <= AMOUNT_TOLERANCE and diff > ROUNDING_TOLERANCE:
            return (ExceptionType.AMOUNT_MISMATCH,
                    f"bank {best_bank.utr} references {ident} (sim {best_score:.0f}%) "
                    f"but amount differs by {diff}",
                    {"bank_utr": best_bank.utr, "edit_score": round(best_score, 1),
                     "bank_amount": str(best_bank.settlement_amount),
                     "delta": str(diff)},
                    [best_bank.utr], key)

    # DATE_MISMATCH: same-amount band bank credit settled far outside window.
    for b in ctx.bank_by_ref.get(key, []):
        if abs(b.settlement_amount - g.amount) <= AMOUNT_TOLERANCE:
            lag = (b.settlement_date - g.txn_date).days
            if abs(lag) > DATE_WINDOW_DAYS:
                return (ExceptionType.DATE_MISMATCH,
                        f"bank {b.utr} references {ident} at same amount but settled "
                        f"{lag} days out (window +/-{DATE_WINDOW_DAYS})",
                        {"bank_utr": b.utr, "lag_days": lag},
                        [b.utr], key)

    if ledger is not None:
        return (ExceptionType.MISSING_SETTLEMENT,
                f"gateway {ident} captured {g.amount} on {g.txn_date} but no bank "
                f"settlement landed (ledger also expects it)",
                {"ledger_expected": str(ledger.expected_amount)},
                [ledger.order_id], key)

    return (ExceptionType.UNRESOLVED_AMBIGUOUS,
            f"gateway {ident} has no resolvable counterpart in any source",
            {}, [], key)


def _classify_bank(
    b: BankSettlement, ctx: _Context,
    split_bank_to_gateway: dict[str, str],
    batch_members: dict[str, list[str]],
) -> tuple[str, str, dict, list[str]]:
    ident = b.utr

    if ident in split_bank_to_gateway:
        gk = split_bank_to_gateway[ident]
        return (ExceptionType.SPLIT_SETTLEMENT,
                f"bank {ident} is one credit of a split for gateway {ctx.gateway_by_id[gk].order_id}",
                {"gateway_order_id": ctx.gateway_by_id[gk].order_id},
                [ctx.gateway_by_id[gk].order_id], ctx.gateway_by_id[gk].order_id)

    if ident in batch_members:
        members = batch_members[ident]
        return (ExceptionType.BATCH_SETTLEMENT,
                f"bank {ident} is a batch payout of {len(members)} gateway txns "
                f"summing to {b.settlement_amount}",
                {"members": [ctx.gateway_by_id[m].order_id for m in members],
                 "payout": str(b.settlement_amount)},
                [ctx.gateway_by_id[m].order_id for m in members] + [ident], ident)

    g = ctx.gateway_by_id.get(normalize_key(b.order_id_ref))
    if g is not None and abs(g.amount - b.settlement_amount) > ROUNDING_TOLERANCE:
        return (ExceptionType.AMOUNT_MISMATCH,
                f"bank {ident} references {g.order_id} but amount differs by "
                f"{abs(g.amount - b.settlement_amount)}",
                {"gateway_order_id": g.order_id,
                 "gateway_amount": str(g.amount),
                 "bank_amount": str(b.settlement_amount)},
                [g.order_id], g.order_id)

    refs_gateway = ctx.gateway_by_id.get(normalize_key(b.order_id_ref)) is not None
    amount_match = any(
        abs(x.amount - b.settlement_amount) <= AMOUNT_TOLERANCE
        for x in ctx.gateway_all)
    date_near = any(
        abs((x.txn_date - b.settlement_date).days) <= DATE_WINDOW_DAYS
        for x in ctx.gateway_all)
    if not refs_gateway and not (amount_match and date_near):
        return (ExceptionType.MISSING_TXN,
                f"bank {ident} paid out {b.settlement_amount} but no gateway txn "
                f"references it",
                {"order_id_ref": b.order_id_ref},
                [], ident)

    return (ExceptionType.UNRESOLVED_AMBIGUOUS,
            f"bank {ident} could not be confidently tied to a gateway txn",
            {}, [], ident)


def _classify_ledger(
    l: MerchantLedger, ctx: _Context,
    gateway_types: dict[str, str], gateway_event: dict[str, str],
) -> tuple[str, str, dict, list[str], str]:
    ident = l.order_id
    key = normalize_key(ident)
    g = ctx.gateway_by_id.get(key)

    if g is not None:
        gtype = gateway_types.get(key)
        if gtype is not None:
            ev_key = gateway_event.get(key, ident)
            return (gtype,
                    f"ledger {ident} is the merchant side of a {gtype} event",
                    {"gateway_order_id": ident},
                    [ident], ev_key)
        return (ExceptionType.ORPHAN_LEDGER,
                f"ledger {ident} has a gateway txn but no settlement reached it",
                {}, [ident], ident)

    bank_refs = ctx.bank_by_ref.get(key, [])
    if bank_refs:
        return (ExceptionType.MISSING_TXN,
                f"ledger {ident} expects {l.expected_amount} but only a bank credit "
                f"exists, no gateway sale",
                {"bank_utrs": [b.utr for b in bank_refs]},
                [b.utr for b in bank_refs], ident)
    return (ExceptionType.ORPHAN_LEDGER,
            f"ledger {ident} expects {l.expected_amount} with no payment anywhere",
            {}, [ident], ident)


# --- orchestration -------------------------------------------------------------

def classify_exceptions(
    unmatched: list[UnmatchedRecord],
    gateway: list[GatewayTransaction],
    bank: list[BankSettlement],
    ledger: list[MerchantLedger],
) -> list[ExceptionRecord]:
    """Pure: classify every unmatched record into exactly one exception type."""
    ctx = _build_context(gateway, bank, ledger)
    split_by_gateway, split_bank_to_gateway = _detect_splits(ctx)
    batch_by_gateway, batch_members = _detect_batches(ctx)

    gateway_types: dict[str, str] = {}
    gateway_event: dict[str, str] = {}
    pending: list[UnmatchedRecord] = []
    records: list[ExceptionRecord] = []

    for u in unmatched:
        rec = u.record
        if u.source == RecordSource.GATEWAY:
            g = rec
            ld = ctx.ledger_by_id.get(normalize_key(g.order_id))
            etype, reason, ev, linked, ekey = _classify_gateway(
                g, ctx, ld, split_by_gateway, batch_by_gateway)
            gateway_types[normalize_key(g.order_id)] = etype
            gateway_event[normalize_key(g.order_id)] = ekey
            records.append(_to_record(u, rec, etype, reason, ev, linked, ekey))
        elif u.source == RecordSource.BANK:
            b = rec
            etype, reason, ev, linked, ekey = _classify_bank(
                b, ctx, split_bank_to_gateway, batch_members)
            records.append(_to_record(u, rec, etype, reason, ev, linked, ekey))
        else:
            pending.append(u)

    for u in pending:
        l = u.record
        etype, reason, ev, linked, ekey = _classify_ledger(
            l, ctx, gateway_types, gateway_event)
        records.append(_to_record(u, l, etype, reason, ev, linked, ekey))

    logger.info("classified %d unmatched records into %d exception entries",
                len(unmatched), len(records))
    return records


def _to_record(u: UnmatchedRecord, rec, etype: str, reason: str,
               ev: dict, linked: list[str], event_key: str) -> ExceptionRecord:
    amount = getattr(rec, "amount",
                     getattr(rec, "settlement_amount",
                             getattr(rec, "expected_amount", None)))
    dt = getattr(rec, "txn_date",
                 getattr(rec, "settlement_date",
                         getattr(rec, "entry_date", None)))
    ident = getattr(rec, "order_id", getattr(rec, "utr", "?"))
    return ExceptionRecord(
        exception_id="",
        type=etype,
        source=u.source.value,
        record_id=ident,
        amount=(str(amount) if amount is not None else None),
        date=(dt.isoformat() if dt is not None else None),
        reason=reason,
        evidence=ev,
        linked_record_ids=linked,
        event_key=event_key,
        method=METHOD,
    )


def build_exceptions_report(
    exceptions: list[ExceptionRecord],
    gateway_total: int, bank_total: int, ledger_total: int,
    source_files: Optional[dict] = None,
) -> dict:
    by_type: dict[str, int] = {t: 0 for t in ExceptionType.ALL}
    by_source: dict[str, int] = {s: 0 for s in ("gateway", "bank", "ledger")}
    for e in exceptions:
        by_type[e.type] += 1
        by_source[e.source] += 1

    events: set = set()
    for e in exceptions:
        events.add((e.type, e.event_key))

    out = []
    for i, e in enumerate(exceptions, start=1):
        d = e.__dict__.copy()
        d["exception_id"] = f"EXC-{i:04d}"
        out.append(d)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pipeline": "deterministic -> fuzzy -> exception_classifier",
        "source_files": source_files or {},
        "summary": {
            "gateway_total": gateway_total,
            "bank_total": bank_total,
            "ledger_total": ledger_total,
            "total_unmatched": len(exceptions),
            "total_exceptions": len(exceptions),
            "by_type": by_type,
            "by_source": by_source,
            "distinct_events": len(events),
        },
        "exceptions": out,
    }


def write_exceptions(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _print_summary(report: dict) -> None:
    s = report["summary"]
    print(f"{'─' * 3} Pass 3: Exception Classifier {'─' * 39}")
    print(f"✗ unmatched records ....... {s['total_unmatched']}")
    print(f"  distinct events ........ {s['distinct_events']}")
    print("  breakdown by type:")
    for t in ExceptionType.ALL:
        if s["by_type"][t]:
            print(f"    {t:<22} {s['by_type'][t]}")
    print(f"  by source .............. gateway {s['by_source']['gateway']}, "
          f"bank {s['by_source']['bank']}, ledger {s['by_source']['ledger']}")


def run_pipeline(data_dir: Path = DATA_DIR) -> dict:
    gateway, bank, ledger = load_sources(data_dir)
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
    report = build_exceptions_report(
        exceptions, len(gateway), len(bank), len(ledger),
        source_files={
            "gateway": GATEWAY_CSV, "bank": BANK_CSV, "ledger": LEDGER_CSV,
        },
    )
    return report


def main() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    report = run_pipeline(DATA_DIR)
    out_path = DATA_DIR.parent / "reports" / "exceptions.json"
    write_exceptions(report, out_path)
    _print_summary(report)
    print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()
