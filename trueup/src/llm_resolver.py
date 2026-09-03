"""Pass 4 LLM-Assisted Resolver for TrueUp.

Consumes UNRESOLVED_AMBIGUOUS exceptions from the exception classifier and
calls Claude to attempt a final resolution.  Every other exception type is
already named deterministically and does NOT need LLM help.

Decision logic (suggestions.txt #17):
  confidence >= 0.80  -> auto-accept (method = "llm_resolver:auto")
  0.50 <= conf < 0.80 -> flag for human review (method = "llm_resolver:review")
  confidence < 0.50   -> keep unresolved (method = "llm_resolver:low_conf")

Every Claude call - hit or miss - is appended to reports/llm_calls.jsonl so
the build journal can trace what the model decided and why.

API failures (network error, rate-limit, missing key) are caught and logged;
the exception is kept as UNRESOLVED_AMBIGUOUS so the pipeline never crashes.

Run:
    python -m src.llm_resolver           # full pipeline + LLM pass
    python -m src.llm_resolver --dry-run # skip actual API calls (smoke test)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from src.exception_classifier import (
    ExceptionRecord,
    ExceptionType,
    build_exceptions_report,
    run_pipeline,
    write_exceptions,
)
from src.deterministic_matcher import DATA_DIR

# -- environment ---------------------------------------------------------------
load_dotenv()

logger = logging.getLogger(__name__)

REPORTS_DIR = DATA_DIR.parent / "reports"
LLM_LOG_PATH = REPORTS_DIR / "llm_calls.jsonl"
RESOLVED_REPORT_PATH = REPORTS_DIR / "exceptions_resolved.json"

# -- thresholds ----------------------------------------------------------------
THRESHOLD_AUTO_ACCEPT = 0.80
THRESHOLD_REVIEW = 0.50

# -- Claude model --------------------------------------------------------------
MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 512
TEMPERATURE = 0.0

# -- prompt template -----------------------------------------------------------
SYSTEM_PROMPT = """You are a financial reconciliation assistant for TrueUp, an
Indian payment-reconciliation engine.  Three data sources are reconciled:
  - gateway_log.csv  - Razorpay gateway transactions (ORD-xxxxx)
  - bank_settlement.csv - bank payouts (UTR-xxxxx)
  - merchant_ledger.csv - merchant accounting entries

Your job: given one UNRESOLVED_AMBIGUOUS exception and a list of candidate
records that might be its match, decide whether any candidate is a credible
match and return a structured JSON response.

Rules:
  1. Respond ONLY with valid JSON - no markdown fences, no prose.
  2. The JSON must contain exactly these keys:
       proposed_match  - candidate record_id string, or null
       confidence      - float 0.0-1.0
       rationale       - one-sentence explanation (max 120 chars)
  3. confidence >= 0.80  means you are highly confident
     confidence 0.50-0.79 means plausible but uncertain (human should verify)
     confidence < 0.50  means you cannot confidently match
  4. If no candidate is a good match, set proposed_match to null and
     confidence to 0.0."""


def _build_user_prompt(exc: ExceptionRecord, candidates: list[dict]) -> str:
    lines = [
        "EXCEPTION TO RESOLVE",
        f"  exception_id : {exc.exception_id}",
        f"  type         : {exc.type}",
        f"  source       : {exc.source}",
        f"  record_id    : {exc.record_id}",
        f"  amount       : {exc.amount}",
        f"  date         : {exc.date}",
        f"  reason       : {exc.reason}",
        f"  evidence     : {json.dumps(exc.evidence)}",
        "",
        "CANDIDATE RECORDS (from other sources)",
    ]
    if candidates:
        for i, c in enumerate(candidates, 1):
            lines.append(f"  [{i}] {json.dumps(c)}")
    else:
        lines.append("  (none provided)")
    lines += [
        "",
        "Return ONLY a JSON object with keys: proposed_match, confidence, rationale.",
    ]
    return "\n".join(lines)


# -- LLM call logging ----------------------------------------------------------

def _log_call(entry: dict) -> None:
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        with LLM_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception as log_err:
        logger.warning("failed to write LLM call log: %s", log_err)


# -- Claude API call -----------------------------------------------------------

def _call_claude(
    exc: ExceptionRecord,
    candidates: list[dict],
    dry_run: bool = False,
) -> dict:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    user_msg = _build_user_prompt(exc, candidates)

    base = {
        "exception_id": exc.exception_id,
        "record_id": exc.record_id,
        "timestamp": ts,
        "model": MODEL,
        "dry_run": dry_run,
    }

    if dry_run:
        stub = {
            **base,
            "proposed_match": None,
            "confidence": 0.0,
            "rationale": "[DRY-RUN] skipped real API call",
            "outcome": "low_conf",
        }
        logger.info("[DRY-RUN] skipped Claude call for %s", exc.exception_id)
        _log_call(stub)
        return stub

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        err = "ANTHROPIC_API_KEY not set; cannot call Claude"
        logger.error(err)
        entry = {**base, "proposed_match": None, "confidence": 0.0,
                 "rationale": "", "outcome": "error", "error": err}
        _log_call(entry)
        return entry

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        t0 = time.monotonic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        elapsed_ms = round((time.monotonic() - t0) * 1000)

        raw_text = response.content[0].text.strip()
        logger.debug("Claude raw response for %s: %s", exc.exception_id, raw_text)

        parsed = json.loads(raw_text)
        proposed_match: Optional[str] = parsed.get("proposed_match")
        confidence: float = float(parsed.get("confidence", 0.0))
        rationale: str = str(parsed.get("rationale", ""))[:200]

        if confidence >= THRESHOLD_AUTO_ACCEPT:
            outcome = "auto_accept"
        elif confidence >= THRESHOLD_REVIEW:
            outcome = "flag_review"
        else:
            outcome = "low_conf"

        entry = {
            **base,
            "elapsed_ms": elapsed_ms,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "proposed_match": proposed_match,
            "confidence": confidence,
            "rationale": rationale,
            "outcome": outcome,
        }
        logger.info(
            "LLM resolved %s -> proposed=%s conf=%.2f outcome=%s",
            exc.exception_id, proposed_match, confidence, outcome,
        )

    except json.JSONDecodeError as je:
        err = f"Claude returned non-JSON: {je}"
        logger.warning("JSON parse error for %s: %s | raw=%s",
                       exc.exception_id, je, raw_text[:200])
        entry = {**base, "proposed_match": None, "confidence": 0.0,
                 "rationale": "", "outcome": "error", "error": err,
                 "raw_response": raw_text[:500]}

    except Exception as api_err:
        err = f"{type(api_err).__name__}: {api_err}"
        logger.warning("Claude API error for %s: %s", exc.exception_id, api_err)
        entry = {**base, "proposed_match": None, "confidence": 0.0,
                 "rationale": "", "outcome": "error", "error": err}

    _log_call(entry)
    return entry


# -- candidate extraction ------------------------------------------------------

def _extract_candidates(exc: ExceptionRecord) -> list[dict]:
    candidates: list[dict] = []
    for rid in exc.linked_record_ids:
        candidates.append({"record_id": rid, "source": "linked"})
    if exc.evidence:
        candidates.append({"type": "evidence", **exc.evidence})
    return candidates[:10]


# -- resolver logic ------------------------------------------------------------

def resolve_exceptions(
    exceptions: list[ExceptionRecord],
    dry_run: bool = False,
) -> tuple[list[ExceptionRecord], list[dict]]:
    """Apply LLM resolution to UNRESOLVED_AMBIGUOUS exceptions only."""
    ambiguous = [e for e in exceptions if e.type == ExceptionType.UNRESOLVED_AMBIGUOUS]
    non_ambiguous = [e for e in exceptions if e.type != ExceptionType.UNRESOLVED_AMBIGUOUS]

    logger.info(
        "LLM resolver: %d total exceptions, %d UNRESOLVED_AMBIGUOUS to process",
        len(exceptions), len(ambiguous),
    )

    llm_logs: list[dict] = []
    resolved: list[ExceptionRecord] = []

    for exc in ambiguous:
        candidates = _extract_candidates(exc)
        result = _call_claude(exc, candidates, dry_run=dry_run)
        llm_logs.append(result)

        outcome = result.get("outcome", "error")

        if outcome == "auto_accept" and result.get("proposed_match"):
            exc.method = "llm_resolver:auto"
            exc.reason = (
                f"[LLM auto-accepted] proposed_match={result['proposed_match']} "
                f"conf={result['confidence']:.2f} | {result['rationale']}"
            )
            exc.evidence = {
                **exc.evidence,
                "llm_proposed_match": result["proposed_match"],
                "llm_confidence": result["confidence"],
                "llm_rationale": result["rationale"],
                "llm_outcome": outcome,
            }
            logger.info("AUTO-ACCEPTED %s -> %s", exc.exception_id, result["proposed_match"])

        elif outcome == "flag_review":
            exc.method = "llm_resolver:review"
            exc.reason = (
                f"[LLM flagged for review] proposed_match={result.get('proposed_match')} "
                f"conf={result['confidence']:.2f} | {result['rationale']}"
            )
            exc.evidence = {
                **exc.evidence,
                "llm_proposed_match": result.get("proposed_match"),
                "llm_confidence": result["confidence"],
                "llm_rationale": result["rationale"],
                "llm_outcome": outcome,
            }
            logger.info("FLAGGED FOR REVIEW %s", exc.exception_id)

        else:
            exc.method = "llm_resolver:low_conf" if outcome != "error" else "llm_resolver:error"
            exc.evidence = {
                **exc.evidence,
                "llm_outcome": outcome,
                "llm_confidence": result.get("confidence", 0.0),
                "llm_error": result.get("error"),
            }
            logger.info("KEPT UNRESOLVED %s (outcome=%s)", exc.exception_id, outcome)

        resolved.append(exc)

    return non_ambiguous + resolved, llm_logs


# -- report helpers ------------------------------------------------------------

def _llm_summary(llm_logs: list[dict]) -> dict:
    total = len(llm_logs)
    by_outcome: dict[str, int] = {}
    errors = 0
    total_input_tokens = 0
    total_output_tokens = 0

    for log in llm_logs:
        outcome = log.get("outcome", "unknown")
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        if outcome == "error":
            errors += 1
        total_input_tokens += log.get("input_tokens", 0)
        total_output_tokens += log.get("output_tokens", 0)

    return {
        "total_llm_calls": total,
        "by_outcome": by_outcome,
        "api_errors": errors,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
    }


def _print_llm_summary(llm_logs: list[dict]) -> None:
    print(f"{'---'} Pass 4: LLM Resolver {'---' * 7}")
    if not llm_logs:
        print("  no UNRESOLVED_AMBIGUOUS exceptions -- LLM pass skipped")
        return
    s = _llm_summary(llm_logs)
    print(f"  LLM calls .............. {s['total_llm_calls']}")
    for outcome, count in sorted(s["by_outcome"].items()):
        print(f"    {outcome:<18} {count}")
    if s["api_errors"]:
        print(f"  WARNING: API errors .... {s['api_errors']}")
    if s["total_input_tokens"]:
        print(f"  tokens in/out .......... {s['total_input_tokens']} / {s['total_output_tokens']}")
    print(f"  LLM call log ........... {LLM_LOG_PATH}")


# -- main ----------------------------------------------------------------------

def main(dry_run: bool = False) -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    report = run_pipeline(DATA_DIR)
    raw_exceptions: list[ExceptionRecord] = []

    from src.exception_classifier import ExceptionRecord as ER
    for exc_dict in report["exceptions"]:
        er = ER(
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

    updated_exceptions, llm_logs = resolve_exceptions(raw_exceptions, dry_run=dry_run)

    s = report["summary"]
    final_report = build_exceptions_report(
        updated_exceptions,
        gateway_total=s["gateway_total"],
        bank_total=s["bank_total"],
        ledger_total=s["ledger_total"],
        source_files=report.get("source_files"),
    )
    final_report["pipeline"] = "deterministic -> fuzzy -> exception_classifier -> llm_resolver"
    final_report["llm_summary"] = _llm_summary(llm_logs)

    write_exceptions(final_report, RESOLVED_REPORT_PATH)

    from src.exception_classifier import _print_summary
    _print_summary(report)
    _print_llm_summary(llm_logs)
    print(f"  wrote {RESOLVED_REPORT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TrueUp LLM Resolver (Pass 4)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip real Claude API calls (for CI / smoke tests)",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
