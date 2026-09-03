"""Synthetic dataset generator for TrueUp.

Fixed seed -> byte-reproducible CSVs, DATA.md and ground_truth.json.
Run: python -m src.data_generator
"""
from __future__ import annotations

import csv
import json
import logging
import random
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

logger = logging.getLogger(__name__)

SEED = 42
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CLEAN_COUNT = 25
FEE_COUNT = 8
DRIFT_COUNT = 10
SPLIT_COUNT = 4
BATCH_CASES = 3
BATCH_SIZE = 3
GARBLED_COUNT = 5
DUP_PAIRS = 4
MISSING_COUNT = 3
ORPHAN_COUNT = 3
ROUNDING_COUNT = 5
REFUND_COUNT = 3

EXPECTED_TOTALS = {
    "gateway": CLEAN_COUNT + FEE_COUNT + DRIFT_COUNT + SPLIT_COUNT
    + BATCH_CASES * BATCH_SIZE + GARBLED_COUNT + DUP_PAIRS * 2
    + MISSING_COUNT + ROUNDING_COUNT + REFUND_COUNT,
    "bank": CLEAN_COUNT + FEE_COUNT + DRIFT_COUNT + SPLIT_COUNT * 2
    + BATCH_CASES + GARBLED_COUNT + DUP_PAIRS * 2 + ROUNDING_COUNT + REFUND_COUNT,
    "ledger": CLEAN_COUNT + FEE_COUNT + DRIFT_COUNT + SPLIT_COUNT
    + BATCH_CASES * BATCH_SIZE + DUP_PAIRS * 2 + MISSING_COUNT
    + ORPHAN_COUNT + ROUNDING_COUNT + REFUND_COUNT,
}

EXPECTED_CATEGORY_COUNTS = {
    "CLEAN_MATCH": CLEAN_COUNT,
    "GATEWAY_FEE": FEE_COUNT,
    "DATE_DRIFT": DRIFT_COUNT,
    "SPLIT_SETTLEMENT": SPLIT_COUNT,
    "BATCH_SETTLEMENT": BATCH_CASES,
    "GARBLED_REFERENCE": GARBLED_COUNT,
    "DUPLICATE_NEAR_MATCH": DUP_PAIRS,
    "MISSING_SETTLEMENT": MISSING_COUNT,
    "ORPHAN_LEDGER": ORPHAN_COUNT,
    "ROUNDING_DIFF": ROUNDING_COUNT,
    "PARTIAL_REFUND": REFUND_COUNT,
}

GATEWAY_HEADERS = ["order_id", "amount", "txn_date", "status", "gateway_fee"]
BANK_HEADERS = ["utr", "settlement_amount", "settlement_date", "order_id_ref"]
LEDGER_HEADERS = ["order_id", "expected_amount", "entry_date", "notes"]

GATEWAY_CSV = "gateway_log.csv"
BANK_CSV = "bank_settlement.csv"
LEDGER_CSV = "merchant_ledger.csv"
GROUND_TRUTH_JSON = "ground_truth.json"
DATA_MD = "DATA.md"

OUTPUT_FILES = (GATEWAY_CSV, BANK_CSV, LEDGER_CSV, GROUND_TRUTH_JSON, DATA_MD)

DATE_MIN = date(2026, 8, 1)
DATE_MAX_TXN = date(2026, 8, 20)
DATE_MAX_ALL = date(2026, 8, 21)
AMOUNT_MIN = 50
AMOUNT_MAX = 25000
FEE_AMOUNT_MIN = 2000

PAISE = Decimal("0.01")
ZERO = Decimal("0.00")

FEE_RATES = (Decimal("0.02"), Decimal("0.025"), Decimal("0.03"))
SPLIT_RATIOS = (Decimal("0.60"), Decimal("0.65"), Decimal("0.70"))
REFUND_FRACS = (Decimal("0.05"), Decimal("0.08"), Decimal("0.10"), Decimal("0.12"))
ROUNDING_DELTAS = (
    Decimal("0.01"), Decimal("-0.01"), Decimal("0.02"),
    Decimal("-0.02"), Decimal("0.01"),
)


def money(value: Decimal) -> Decimal:
    return value.quantize(PAISE, rounding=ROUND_HALF_UP)


def rand_amount(rng: random.Random, lo: int = AMOUNT_MIN, hi: int = AMOUNT_MAX) -> Decimal:
    return Decimal(f"{rng.randint(lo, hi)}.{rng.randrange(100):02d}")


def txn_date(rng: random.Random, max_offset: int = 19) -> date:
    return DATE_MIN + timedelta(days=rng.randint(0, max_offset))


def garble(order_id: str, style: int) -> str:
    digits = order_id[4:]
    if style == 0:
        return order_id[:-3]
    if style == 1:
        return order_id[:4] + digits[1] + digits[0] + digits[2:]
    if style == 2:
        return order_id[:5] + digits[2:]
    if style == 3:
        return order_id.lower()
    return order_id[:-1] + str((int(digits[-1]) + 1) % 10)


@dataclass
class Case:
    case_id: str
    category: str
    order_ids: list[str]
    utrs: list[str]
    expected_outcome: str
    detail: str


class IdAllocator:
    def __init__(self, prefix: str, start: int) -> None:
        self._prefix = prefix
        self._next = start

    def take(self) -> str:
        value = f"{self._prefix}-{self._next}"
        self._next += 1
        return value


def _gw_row(order_id: str, amount: Decimal, day: date, fee: Decimal) -> dict:
    return {
        "order_id": order_id,
        "amount": f"{money(amount):.2f}",
        "txn_date": day.isoformat(),
        "status": "success",
        "gateway_fee": f"{money(fee):.2f}",
    }


def _bank_row(utr: str, amount: Decimal, day: date, ref: str) -> dict:
    return {
        "utr": utr,
        "settlement_amount": f"{money(amount):.2f}",
        "settlement_date": day.isoformat(),
        "order_id_ref": ref,
    }


def _led_row(order_id: str, amount: Decimal, day: date, notes: str) -> dict:
    return {
        "order_id": order_id,
        "expected_amount": f"{money(amount):.2f}",
        "entry_date": day.isoformat(),
        "notes": notes,
    }


def build_dataset(seed: int = SEED) -> dict:
    rng = random.Random(seed)
    orders = IdAllocator("ORD", 10001)
    utr_pool = IdAllocator("UTR", 50001)
    gateway: list[dict] = []
    bank: list[dict] = []
    ledger: list[dict] = []
    cases: list[Case] = []

    def new_case(case_id: str, category: str, oids: list[str], utrs: list[str],
                 outcome: str, detail: str) -> None:
        cases.append(Case(case_id, category, oids, utrs, outcome, detail))

    for i in range(1, CLEAN_COUNT + 1):
        oid = orders.take()
        utr = utr_pool.take()
        day = txn_date(rng)
        lag = rng.choice((0, 1))
        amt = rand_amount(rng)
        gateway.append(_gw_row(oid, amt, day, ZERO))
        bank.append(_bank_row(utr, amt, day + timedelta(days=lag), oid))
        ledger.append(_led_row(oid, amt, day, "sale"))
        new_case(f"CLEAN-{i:02d}", "CLEAN_MATCH", [oid], [utr],
                 "exact 1:1:1 match",
                 f"Rs {amt} txn {day}, settles T+{lag}")

    for i in range(1, FEE_COUNT + 1):
        oid = orders.take()
        utr = utr_pool.take()
        rate = FEE_RATES[(i - 1) % len(FEE_RATES)]
        amt = rand_amount(rng, FEE_AMOUNT_MIN)
        fee = money(amt * rate)
        day = txn_date(rng)
        lag = rng.choice((0, 1))
        gateway.append(_gw_row(oid, amt, day, fee))
        bank.append(_bank_row(utr, amt - fee, day + timedelta(days=lag), oid))
        ledger.append(_led_row(oid, amt, day, f"gateway fee {rate} of txn expected"))
        new_case(f"FEE-{i:02d}", "GATEWAY_FEE", [oid], [utr],
                 "match_with_adjustment: settlement = amount - gateway_fee",
                 f"Rs {amt}, fee Rs {fee} ({rate}), settles T+{lag}")

    for i in range(1, DRIFT_COUNT + 1):
        oid = orders.take()
        utr = utr_pool.take()
        lag = 2 if i <= DRIFT_COUNT // 2 else 3
        day = txn_date(rng, max_offset=17)
        amt = rand_amount(rng)
        gateway.append(_gw_row(oid, amt, day, ZERO))
        bank.append(_bank_row(utr, amt, day + timedelta(days=lag), oid))
        ledger.append(_led_row(oid, amt, day, f"settlement expected T+{lag}"))
        new_case(f"DRIFT-{i:02d}", "DATE_DRIFT", [oid], [utr],
                 "match_with_date_drift (T+2 or T+3)",
                 f"Rs {amt} txn {day}, banks {day + timedelta(days=lag)}")

    for i in range(1, SPLIT_COUNT + 1):
        oid = orders.take()
        utr_a = utr_pool.take()
        utr_b = utr_pool.take()
        ratio = SPLIT_RATIOS[(i - 1) % len(SPLIT_RATIOS)]
        day = txn_date(rng)
        amt = rand_amount(rng)
        part_a = money(amt * ratio)
        part_b = money(amt - part_a)
        gateway.append(_gw_row(oid, amt, day, ZERO))
        bank.append(_bank_row(utr_a, part_a, day, oid))
        bank.append(_bank_row(utr_b, part_b, day + timedelta(days=1), oid))
        ledger.append(_led_row(oid, amt, day, "split settlement expected (2 credits)"))
        new_case(f"SPLIT-{i:02d}", "SPLIT_SETTLEMENT", [oid], [utr_a, utr_b],
                 "one gateway txn -> two bank credits summing to gateway amount",
                 f"Rs {amt} splits into Rs {part_a} + Rs {part_b}")

    for b in range(1, BATCH_CASES + 1):
        members: list[tuple[str, Decimal, date]] = []
        for _ in range(BATCH_SIZE):
            members.append((orders.take(), rand_amount(rng), txn_date(rng, max_offset=16)))
        utr = utr_pool.take()
        total = money(sum((m[1] for m in members), ZERO))
        payout_day = max(m[2] for m in members) + timedelta(days=1)
        for oid, amt, day in members:
            gateway.append(_gw_row(oid, amt, day, ZERO))
            ledger.append(_led_row(oid, amt, day, f"payout batch BATCH-{b:02d} member"))
        bank.append(_bank_row(utr, total, payout_day, f"N/A-BATCH-{b:02d}"))
        new_case(f"BATCH-{b:02d}", "BATCH_SETTLEMENT", [m[0] for m in members], [utr],
                 f"{BATCH_SIZE} gateway txns -> one bank credit of their sum",
                 f"payout Rs {total} on {payout_day}; members "
                 + ", ".join(f"{oid}:Rs {amt}" for oid, amt, _ in members))

    for i in range(1, GARBLED_COUNT + 1):
        oid = orders.take()
        utr = utr_pool.take()
        corrupted = garble(oid, (i - 1) % 5)
        day = txn_date(rng)
        lag = rng.choice((0, 1))
        amt = rand_amount(rng)
        gateway.append(_gw_row(oid, amt, day, ZERO))
        bank.append(_bank_row(utr, amt, day + timedelta(days=lag), corrupted))
        new_case(f"GARBLED-{i:02d}", "GARBLED_REFERENCE", [oid], [utr],
                 "fuzzy reference match required",
                 f"bank shows '{corrupted}' instead of '{oid}', Rs {amt}; "
                 f"gateway and ledger carry the true id")

    for p in range(1, DUP_PAIRS + 1):
        shared_amt = rand_amount(rng)
        day = txn_date(rng, max_offset=18)
        oid_a = orders.take()
        oid_b = orders.take()
        utr_a = utr_pool.take()
        utr_b = utr_pool.take()
        gateway.append(_gw_row(oid_a, shared_amt, day, ZERO))
        gateway.append(_gw_row(oid_b, shared_amt, day + timedelta(days=1), ZERO))
        bank.append(_bank_row(utr_a, shared_amt, day, oid_a))
        bank.append(_bank_row(utr_b, shared_amt, day + timedelta(days=1), oid_b))
        ledger.append(_led_row(oid_a, shared_amt, day, f"duplicate-risk cluster DUP-{p:02d}"))
        ledger.append(_led_row(oid_b, shared_amt, day + timedelta(days=1),
                               f"duplicate-risk cluster DUP-{p:02d}"))
        new_case(f"DUP-{p:02d}", "DUPLICATE_NEAR_MATCH", [oid_a, oid_b], [utr_a, utr_b],
                 "two valid candidates; correct refs disambiguate; ambiguity trap for scoring",
                 f"both Rs {shared_amt}; {oid_a} on {day}, {oid_b} on {day + timedelta(days=1)}")

    for i in range(1, MISSING_COUNT + 1):
        oid = orders.take()
        day = txn_date(rng)
        amt = rand_amount(rng)
        gateway.append(_gw_row(oid, amt, day, ZERO))
        ledger.append(_led_row(oid, amt, day, "awaiting settlement"))
        new_case(f"MISS-{i:02d}", "MISSING_SETTLEMENT", [oid], [],
                 "MISSING_SETTLEMENT exception (still pending, not a bug)",
                 f"Rs {amt} captured {day}, never settled")

    for i in range(1, ORPHAN_COUNT + 1):
        oid = orders.take()
        day = txn_date(rng)
        amt = rand_amount(rng)
        ledger.append(_led_row(oid, amt, day, "manual entry - verify source"))
        new_case(f"ORPHAN-{i:02d}", "ORPHAN_LEDGER", [oid], [],
                 "ORPHAN_LEDGER exception",
                 f"ledger expects Rs {amt} on {day}, no payment anywhere")

    for i in range(1, ROUNDING_COUNT + 1):
        oid = orders.take()
        utr = utr_pool.take()
        delta = ROUNDING_DELTAS[(i - 1) % len(ROUNDING_DELTAS)]
        day = txn_date(rng)
        lag = rng.choice((0, 1))
        amt = rand_amount(rng)
        gateway.append(_gw_row(oid, amt, day, ZERO))
        bank.append(_bank_row(utr, amt + delta, day + timedelta(days=lag), oid))
        ledger.append(_led_row(oid, amt, day, "paise-level variance allowed"))
        new_case(f"ROUND-{i:02d}", "ROUNDING_DIFF", [oid], [utr],
                 "match_with_rounding_diff (1-2 paise)",
                 f"Rs {amt} everywhere except bank Rs {money(amt + delta)} ({delta:+})")

    for i in range(1, REFUND_COUNT + 1):
        oid = orders.take()
        utr = utr_pool.take()
        frac = REFUND_FRACS[(i - 1) % len(REFUND_FRACS)]
        day = txn_date(rng)
        lag = rng.choice((0, 1))
        amt = rand_amount(rng)
        refund = money(amt * frac)
        gateway.append(_gw_row(oid, amt, day, ZERO))
        bank.append(_bank_row(utr, amt - refund, day + timedelta(days=lag), oid))
        ledger.append(_led_row(oid, amt, day, f"refund Rs {refund} issued"))
        new_case(f"REFUND-{i:02d}", "PARTIAL_REFUND", [oid], [utr],
                 "settlement = gateway amount - refund",
                 f"Rs {amt} minus refund Rs {refund} ({frac}) -> banks Rs {money(amt - refund)}")

    gateway.sort(key=lambda r: (r["txn_date"], r["order_id"]))
    bank.sort(key=lambda r: (r["settlement_date"], r["utr"]))
    ledger.sort(key=lambda r: (r["entry_date"], r["order_id"]))
    cases.sort(key=lambda c: c.case_id)

    _validate(gateway, bank, ledger, cases, seed)
    return {"gateway": gateway, "bank": bank, "ledger": ledger,
            "cases": cases, "seed": seed}


def _validate(gateway: list[dict], bank: list[dict], ledger: list[dict],
              cases: list[Case], seed: int) -> None:
    assert seed == SEED, "generator must run with the fixed committed seed"
    assert len(gateway) == EXPECTED_TOTALS["gateway"], (
        f"gateway rows {len(gateway)} != {EXPECTED_TOTALS['gateway']}")
    assert len(bank) == EXPECTED_TOTALS["bank"], (
        f"bank rows {len(bank)} != {EXPECTED_TOTALS['bank']}")
    assert len(ledger) == EXPECTED_TOTALS["ledger"], (
        f"ledger rows {len(ledger)} != {EXPECTED_TOTALS['ledger']}")

    category_counts = Counter(c.category for c in cases)
    assert dict(category_counts) == EXPECTED_CATEGORY_COUNTS, (
        f"category counts drifted: {dict(category_counts)}")

    gw_ids = [r["order_id"] for r in gateway]
    led_ids = [r["order_id"] for r in ledger]
    utrs = [r["utr"] for r in bank]
    assert len(set(gw_ids)) == len(gw_ids), "duplicate order_id inside gateway"
    assert len(set(led_ids)) == len(led_ids), "duplicate order_id inside ledger"
    assert len(set(utrs)) == len(utrs), "duplicate utr inside bank"
    orphan_ids = {c.order_ids[0] for c in cases if c.category == "ORPHAN_LEDGER"}
    assert not (orphan_ids & set(gw_ids) | orphan_ids & set(utrs)), (
        "orphan ledger ids must not exist in gateway or bank")

    for rows, fields in ((gateway, ("amount", "gateway_fee")),
                         (bank, ("settlement_amount",)),
                         (ledger, ("expected_amount",))):
        for row in rows:
            for fld in fields:
                value = Decimal(row[fld])
                assert value == value.quantize(PAISE), f"non-paise value {row[fld]}"

    for rows, date_flds in ((gateway, ("txn_date",)), (bank, ("settlement_date",)),
                            (ledger, ("entry_date",))):
        for row in rows:
            for fld in date_flds:
                day = date.fromisoformat(row[fld])
                assert DATE_MIN <= day <= DATE_MAX_ALL, f"{fld} out of window: {day}"


def _case_to_dict(case: Case) -> dict:
    return asdict(case)


def render_data_md(dataset: dict) -> str:
    lines: list[str] = [
        "# TrueUp - Synthetic Dataset Ground Truth (DATA.md)",
        "",
        "> AUTO-GENERATED by src/data_generator.py. DO NOT EDIT BY HAND.",
        "> If ground truth must change, change the generator and regenerate both",
        "> this file and ground_truth.json together (see rules.md section 2).",
        "",
        f"- RNG seed: {dataset['seed']}",
        "- Date window: 2026-08-01 .. 2026-08-21",
        f"- Amount range: Rs {AMOUNT_MIN} .. Rs {AMOUNT_MAX:,}",
        "",
        "## Record counts",
        "",
        "| Source file | Rows |",
        "|---|---|",
        f"| {GATEWAY_CSV} | {len(dataset['gateway'])} |",
        f"| {BANK_CSV} | {len(dataset['bank'])} |",
        f"| {LEDGER_CSV} | {len(dataset['ledger'])} |",
        "",
        f"Strictly clean 1:1:1 triples: **{CLEAN_COUNT}** "
        "(target ~25-30 per daily_planner.txt)",
        "",
        "## Edge-case inventory (exact counts)",
        "",
        "| Category | Cases | Expected reconciliation outcome |",
        "|---|---|---|",
    ]
    outcomes: dict[str, str] = {}
    for case in dataset["cases"]:
        outcomes.setdefault(case.category, case.expected_outcome)
    for category, count in EXPECTED_CATEGORY_COUNTS.items():
        lines.append(f"| {category} | {count} | {outcomes.get(category, '')} |")

    lines += ["", "## Case catalog", ""]
    current_category = None
    for case in dataset["cases"]:
        if case.category != current_category:
            current_category = case.category
            lines += [f"### {current_category}", "",
                      "| case_id | order_ids | utrs | expected_outcome | detail |",
                      "|---|---|---|---|---|"]
        oids = ", ".join(case.order_ids) or "-"
        utrs = ", ".join(case.utrs) or "-"
        lines.append(f"| {case.case_id} | {oids} | {utrs} | {case.expected_outcome} "
                     f"| {case.detail} |")
    lines.append("")
    return "\n".join(lines)


def write_dataset(dataset: dict, out_dir: Path = DATA_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    def write_csv(name: str, headers: list[str], rows: list[dict]) -> None:
        with (out_dir / name).open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    write_csv(GATEWAY_CSV, GATEWAY_HEADERS, dataset["gateway"])
    write_csv(BANK_CSV, BANK_HEADERS, dataset["bank"])
    write_csv(LEDGER_CSV, LEDGER_HEADERS, dataset["ledger"])

    payload = {
        "seed": dataset["seed"],
        "totals": {source: len(dataset[source]) for source in ("gateway", "bank", "ledger")},
        "clean_triples": CLEAN_COUNT,
        "category_counts": dict(EXPECTED_CATEGORY_COUNTS),
        "cases": [_case_to_dict(c) for c in dataset["cases"]],
    }
    (out_dir / GROUND_TRUTH_JSON).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (out_dir / DATA_MD).write_text(render_data_md(dataset), encoding="utf-8")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    dataset = build_dataset()
    write_dataset(dataset)
    logger.info("wrote %s", sorted(str(DATA_DIR / name) for name in OUTPUT_FILES))
    print("=" * 64)
    print("TrueUp synthetic data generated (seed={})".format(dataset["seed"]))
    print("  gateway_log.csv     {} rows".format(len(dataset["gateway"])))
    print("  bank_settlement.csv {} rows".format(len(dataset["bank"])))
    print("  merchant_ledger.csv {} rows".format(len(dataset["ledger"])))
    print("  clean 1:1:1 triples {}".format(CLEAN_COUNT))
    print("  edge cases          {} across {} categories".format(
        len(dataset["cases"]), len(EXPECTED_CATEGORY_COUNTS) - 1))
    print("  ground truth        {}, {}".format(GROUND_TRUTH_JSON, DATA_MD))
    print("=" * 64)


if __name__ == "__main__":
    main()
