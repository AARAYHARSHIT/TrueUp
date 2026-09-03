#!/usr/bin/env bash
# TrueUp — one-command demo for evaluators
# Usage:  bash run_demo.sh   (from trueup/)
# Windows: bash run_demo.sh  (Git Bash)  OR  python -m src.data_generator && python -m src.reporter && python -m pytest -q
set -e

# ── helpers ──────────────────────────────────────────────────────────
info()  { echo -e "\n\033[1;36m▶ $*\033[0m"; }
ok()    { echo -e "\033[0;32m  ✓ $*\033[0m"; }
warn()  { echo -e "\033[0;33m  ! $*\033[0m"; }
die()   { echo -e "\033[0;31m  ✘ $*\033[0m" >&2; exit 1; }

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "════════════════════════════════════════════════════════════════"
echo "  TrueUp — AI Finance Controller  •  Track 04 Demo"
echo "  Deterministic → Fuzzy → Classify → LLM → Report → Forecast"
echo "════════════════════════════════════════════════════════════════"

# ── 1. Python check ────────────────────────────────────────────────
info "Checking Python..."
if ! command -v python &>/dev/null && ! command -v python3 &>/dev/null; then
  die "Python not found. Install Python 3.11+ and retry."
fi
PY="python"
command -v python &>/dev/null || PY="python3"
ok "$($PY --version) found"

# ── 2. Virtual environment (create if missing) ─────────────────────
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
  info "Creating virtual environment (venv)..."
  $PY -m venv venv
  ok "venv created"
else
  ok "venv already exists"
fi

# ── 3. Dependencies ────────────────────────────────────────────────
info "Installing dependencies..."
if [ -f "venv/Scripts/activate" ]; then
  # Windows Git Bash
  # shellcheck disable=SC1091
  source venv/Scripts/activate 2>/dev/null || true
elif [ -f "venv/bin/activate" ]; then
  # macOS / Linux
  # shellcheck disable=SC1091
  source venv/bin/activate 2>/dev/null || true
fi
# Use the venv pip if available, otherwise system pip
PIP="pip"
[ -f "venv/Scripts/pip" ] && PIP="venv/Scripts/pip"
[ -f "venv/bin/pip" ] && PIP="venv/bin/pip"
$PIP install -q -r requirements.txt
ok "dependencies installed (pandas, pytest, rapidfuzz, anthropic, python-dotenv)"

# ── 4. Environment note ────────────────────────────────────────────
if [ ! -f ".env" ]; then
  warn ".env not found — copying .env.example (set ANTHROPIC_API_KEY for live Q&A agent)"
  cp .env.example .env 2>/dev/null || true
fi
if grep -q "your_key_here" .env 2>/dev/null; then
  warn "ANTHROPIC_API_KEY is still placeholder — pipeline runs in dry-run mode; live Q&A needs a real key"
fi
# Pick python that respects venv
RUN_PY="python"
[ -f "venv/Scripts/python" ] && RUN_PY="venv/Scripts/python"
[ -f "venv/bin/python" ] && RUN_PY="venv/bin/python"
command -v python &>/dev/null || RUN_PY="python3"

# ── 5. Generate synthetic dataset ──────────────────────────────────
info "Generating synthetic dataset (seed=42)..."
$RUN_PY -m src.data_generator
ok "data ready: gateway 80 / bank 75 / ledger 78  (see data/DATA.md)"

# ── 6. Run full reconciliation pipeline ────────────────────────────
info "Running reconciliation pipeline (reporter)..."
$RUN_PY -m src.reporter
ok "report written to reports/reconciliation_report.json"

# ── 7. Cash forecast (stretch) ─────────────────────────────────────
info "Generating cash flow forecast (14-day)..."
$RUN_PY -m src.cash_forecaster
ok "forecast complete"

# ── 8. Tests ───────────────────────────────────────────────────────
info "Running test suite (196 tests)..."
$RUN_PY -m pytest -q
ok "196/196 tests passing"

# ── 9. Q&A agent smoke test (no API key needed) ───────────────────
info "Q&A agent — direct tool smoke test (no API key needed)..."
$RUN_PY -c "
from src.qa_agent import get_match_rate, list_exceptions, explain_match, get_cash_position, get_cash_forecast
print('  get_match_rate:', get_match_rate()['final'])
print('  list_exceptions MISSING_SETTLEMENT:', list_exceptions('MISSING_SETTLEMENT')['total'], 'found')
print('  explain_match ORD-10071:', explain_match('ORD-10071')['exception_type'])
print('  get_cash_position total:', get_cash_position()['total_unreconciled_inr'])
print('  get_cash_forecast total:', get_cash_forecast()['total_forecast_inr'])
"
ok "tool smoke test passed"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Demo complete.  Next steps:"
echo "    • Interactive Q&A:   python -m src.qa_agent"
echo "    • Single question:   python -m src.qa_agent \"What is the match rate?\""
echo "    • With LLM:          set ANTHROPIC_API_KEY in .env, then python -m src.qa_agent --test"
echo "    • Report:            cat reports/reconciliation_report.json"
echo "════════════════════════════════════════════════════════════════"
