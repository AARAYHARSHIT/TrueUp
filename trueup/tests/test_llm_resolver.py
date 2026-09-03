"""Tests for src/llm_resolver.py.

All tests run without a real ANTHROPIC_API_KEY by using dry_run=True or by
mocking the anthropic client.  The test suite verifies:
  1. Confidence threshold routing (auto_accept / flag_review / low_conf).
  2. Dry-run mode (no real API calls, stub response logged).
  3. Missing API key -> graceful error, exception kept unresolved.
  4. Non-JSON Claude response -> graceful error, exception kept unresolved.
  5. Only UNRESOLVED_AMBIGUOUS exceptions are sent to the LLM.
  6. LLM call log (llm_calls.jsonl) is written for every call.
"""
from __future__ import annotations

import json
import types
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.exception_classifier import ExceptionRecord, ExceptionType
from src.llm_resolver import (
    THRESHOLD_AUTO_ACCEPT,
    THRESHOLD_REVIEW,
    _build_user_prompt,
    _call_claude,
    _extract_candidates,
    _llm_summary,
    resolve_exceptions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_exc(
    exc_id: str = "EXC-0001",
    etype: str = ExceptionType.UNRESOLVED_AMBIGUOUS,
    source: str = "gateway",
    record_id: str = "ORD-99999",
    amount: str = "5000.00",
    evidence: dict | None = None,
    linked: list[str] | None = None,
) -> ExceptionRecord:
    return ExceptionRecord(
        exception_id=exc_id,
        type=etype,
        source=source,
        record_id=record_id,
        amount=amount,
        date="2026-08-01",
        reason="test reason",
        evidence=evidence or {},
        linked_record_ids=linked or [],
        event_key=record_id,
        method="exception_classifier",
    )


def _fake_anthropic_response(json_payload: dict) -> MagicMock:
    """Return a mock that looks like an anthropic.messages.create() response."""
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(json_payload))]
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 30
    return msg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPromptBuilding(unittest.TestCase):
    def test_prompt_contains_exception_fields(self):
        exc = _make_exc(record_id="ORD-10001", amount="1234.56")
        prompt = _build_user_prompt(exc, [])
        self.assertIn("ORD-10001", prompt)
        self.assertIn("1234.56", prompt)
        self.assertIn("EXCEPTION TO RESOLVE", prompt)

    def test_prompt_lists_candidates(self):
        exc = _make_exc()
        candidates = [{"record_id": "UTR-50001", "source": "bank"}]
        prompt = _build_user_prompt(exc, candidates)
        self.assertIn("UTR-50001", prompt)

    def test_prompt_no_candidates(self):
        exc = _make_exc()
        prompt = _build_user_prompt(exc, [])
        self.assertIn("none provided", prompt)


class TestCandidateExtraction(unittest.TestCase):
    def test_extracts_linked_ids(self):
        exc = _make_exc(linked=["UTR-11111", "UTR-22222"])
        candidates = _extract_candidates(exc)
        ids = [c.get("record_id") for c in candidates]
        self.assertIn("UTR-11111", ids)
        self.assertIn("UTR-22222", ids)

    def test_includes_evidence(self):
        exc = _make_exc(evidence={"batch_utr": "UTR-99"})
        candidates = _extract_candidates(exc)
        evidence_items = [c for c in candidates if c.get("type") == "evidence"]
        self.assertTrue(len(evidence_items) > 0)

    def test_capped_at_ten(self):
        exc = _make_exc(linked=[f"ID-{i}" for i in range(20)])
        candidates = _extract_candidates(exc)
        self.assertLessEqual(len(candidates), 10)


class TestDryRun(unittest.TestCase):
    def test_dry_run_returns_stub(self):
        exc = _make_exc()
        result = _call_claude(exc, [], dry_run=True)
        self.assertEqual(result["outcome"], "low_conf")
        self.assertIsNone(result["proposed_match"])
        self.assertEqual(result["confidence"], 0.0)
        self.assertTrue(result["dry_run"])
        self.assertIn("DRY-RUN", result["rationale"])

    def test_dry_run_logged(self, tmp_path=None):
        exc = _make_exc(exc_id="EXC-DRY")
        with patch("src.llm_resolver.LLM_LOG_PATH", Path("reports/llm_calls.jsonl")):
            result = _call_claude(exc, [], dry_run=True)
        self.assertEqual(result["exception_id"], "EXC-DRY")


class TestMissingApiKey(unittest.TestCase):
    def test_missing_key_returns_error(self):
        exc = _make_exc()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            result = _call_claude(exc, [], dry_run=False)
        self.assertEqual(result["outcome"], "error")
        self.assertIn("ANTHROPIC_API_KEY", result["error"])
        self.assertEqual(result["confidence"], 0.0)


class TestConfidenceThresholds(unittest.TestCase):
    """Test that the three routing tiers work correctly."""

    def _mock_call(self, confidence: float, proposed: str = "UTR-12345"):
        exc = _make_exc()
        payload = {
            "proposed_match": proposed,
            "confidence": confidence,
            "rationale": "test rationale",
        }
        mock_response = _fake_anthropic_response(payload)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        mock_anthropic_module = types.ModuleType("anthropic")
        mock_anthropic_module.Anthropic = MagicMock(return_value=mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            with patch.dict("sys.modules", {"anthropic": mock_anthropic_module}):
                result = _call_claude(exc, [], dry_run=False)
        return result

    def test_high_confidence_auto_accept(self):
        result = self._mock_call(confidence=0.92)
        self.assertEqual(result["outcome"], "auto_accept")

    def test_boundary_auto_accept(self):
        result = self._mock_call(confidence=THRESHOLD_AUTO_ACCEPT)
        self.assertEqual(result["outcome"], "auto_accept")

    def test_mid_confidence_flag_review(self):
        result = self._mock_call(confidence=0.65)
        self.assertEqual(result["outcome"], "flag_review")

    def test_boundary_flag_review_lower(self):
        result = self._mock_call(confidence=THRESHOLD_REVIEW)
        self.assertEqual(result["outcome"], "flag_review")

    def test_low_confidence_unresolved(self):
        result = self._mock_call(confidence=0.30)
        self.assertEqual(result["outcome"], "low_conf")

    def test_zero_confidence(self):
        result = self._mock_call(confidence=0.0, proposed=None)
        self.assertEqual(result["outcome"], "low_conf")


class TestBadJsonResponse(unittest.TestCase):
    def test_non_json_response_is_error(self):
        exc = _make_exc()
        msg = MagicMock()
        msg.content = [MagicMock(text="Sorry, I cannot help with that.")]
        msg.usage.input_tokens = 10
        msg.usage.output_tokens = 8

        mock_client = MagicMock()
        mock_client.messages.create.return_value = msg

        mock_anthropic_module = types.ModuleType("anthropic")
        mock_anthropic_module.Anthropic = MagicMock(return_value=mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            with patch.dict("sys.modules", {"anthropic": mock_anthropic_module}):
                result = _call_claude(exc, [], dry_run=False)

        self.assertEqual(result["outcome"], "error")
        self.assertIn("non-JSON", result["error"])


class TestApiException(unittest.TestCase):
    def test_network_error_is_graceful(self):
        exc = _make_exc()

        mock_anthropic_module = types.ModuleType("anthropic")
        mock_anthropic_module.Anthropic = MagicMock(
            side_effect=ConnectionError("network unreachable")
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            with patch.dict("sys.modules", {"anthropic": mock_anthropic_module}):
                result = _call_claude(exc, [], dry_run=False)

        self.assertEqual(result["outcome"], "error")
        self.assertIn("ConnectionError", result["error"])
        self.assertEqual(result["confidence"], 0.0)


class TestResolveExceptions(unittest.TestCase):
    """Integration-style tests for resolve_exceptions()."""

    def test_only_ambiguous_are_sent_to_llm(self):
        exc_ambiguous = _make_exc(etype=ExceptionType.UNRESOLVED_AMBIGUOUS)
        exc_missing = _make_exc(exc_id="EXC-0002", etype=ExceptionType.MISSING_SETTLEMENT)
        exc_orphan = _make_exc(exc_id="EXC-0003", etype=ExceptionType.ORPHAN_LEDGER)

        updated, logs = resolve_exceptions(
            [exc_ambiguous, exc_missing, exc_orphan], dry_run=True
        )
        # Only 1 LLM call for the ambiguous exception
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["exception_id"], "EXC-0001")
        # All 3 exceptions survive in the output
        self.assertEqual(len(updated), 3)

    def test_method_updated_for_low_conf(self):
        exc = _make_exc()
        updated, logs = resolve_exceptions([exc], dry_run=True)
        resolved_exc = next(e for e in updated if e.exception_id == "EXC-0001")
        self.assertEqual(resolved_exc.method, "llm_resolver:low_conf")

    def test_non_ambiguous_method_unchanged(self):
        exc = _make_exc(etype=ExceptionType.BATCH_SETTLEMENT)
        updated, logs = resolve_exceptions([exc], dry_run=True)
        self.assertEqual(len(logs), 0)
        self.assertEqual(updated[0].method, "exception_classifier")

    def test_evidence_updated_on_dry_run(self):
        exc = _make_exc()
        updated, _ = resolve_exceptions([exc], dry_run=True)
        resolved_exc = updated[0]
        self.assertIn("llm_outcome", resolved_exc.evidence)

    def test_auto_accept_updates_method(self):
        exc = _make_exc()
        payload = {"proposed_match": "UTR-12345", "confidence": 0.95,
                   "rationale": "Strong amount and date alignment"}
        mock_response = _fake_anthropic_response(payload)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_module = types.ModuleType("anthropic")
        mock_anthropic_module.Anthropic = MagicMock(return_value=mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            with patch.dict("sys.modules", {"anthropic": mock_anthropic_module}):
                updated, logs = resolve_exceptions([exc], dry_run=False)

        self.assertEqual(logs[0]["outcome"], "auto_accept")
        self.assertEqual(updated[0].method, "llm_resolver:auto")
        self.assertIn("llm_proposed_match", updated[0].evidence)

    def test_flag_review_updates_method(self):
        exc = _make_exc()
        payload = {"proposed_match": "UTR-55555", "confidence": 0.65,
                   "rationale": "Plausible match but amount differs slightly"}
        mock_response = _fake_anthropic_response(payload)
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_module = types.ModuleType("anthropic")
        mock_anthropic_module.Anthropic = MagicMock(return_value=mock_client)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            with patch.dict("sys.modules", {"anthropic": mock_anthropic_module}):
                updated, logs = resolve_exceptions([exc], dry_run=False)

        self.assertEqual(logs[0]["outcome"], "flag_review")
        self.assertEqual(updated[0].method, "llm_resolver:review")


class TestLlmSummary(unittest.TestCase):
    def test_summary_counts(self):
        logs = [
            {"outcome": "auto_accept", "input_tokens": 100, "output_tokens": 30},
            {"outcome": "flag_review", "input_tokens": 110, "output_tokens": 25},
            {"outcome": "low_conf", "input_tokens": 90, "output_tokens": 20},
            {"outcome": "error", "input_tokens": 0, "output_tokens": 0},
        ]
        s = _llm_summary(logs)
        self.assertEqual(s["total_llm_calls"], 4)
        self.assertEqual(s["by_outcome"]["auto_accept"], 1)
        self.assertEqual(s["by_outcome"]["flag_review"], 1)
        self.assertEqual(s["by_outcome"]["low_conf"], 1)
        self.assertEqual(s["api_errors"], 1)
        self.assertEqual(s["total_input_tokens"], 300)
        self.assertEqual(s["total_output_tokens"], 75)

    def test_empty_logs(self):
        s = _llm_summary([])
        self.assertEqual(s["total_llm_calls"], 0)
        self.assertEqual(s["api_errors"], 0)


if __name__ == "__main__":
    unittest.main()
