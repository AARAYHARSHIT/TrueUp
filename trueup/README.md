# TrueUp — AI Finance Controller

> **Razorpay AI Buildathon — Track 04: “Run the books and the cash position”**
> Deterministic-first, fuzzy-second, LLM-only-when-genuinely-ambiguous reconciliation of payment data. No hallucinations. Every number proven against ground truth.

One command: `bash run_demo.sh` — generates data, runs the 4-pass pipeline, prints the report, and runs 196 tests.

---

## What It Does — in 30 Seconds

Businesses see the same money three different ways: the **gateway log** says one thing, the **bank settlement file** says another, and the **merchant ledger** says a third. Reconciling them today means hours of `VLOOKUP` against gateway fees, T+2/T+3 settlement drift, split payouts, garbled UTRs, and paise-level rounding noise.

**TrueUp automates that loop and is honest about what it can't match.**

```
gateway_log.csv ─┐
bank_settlement.csv ─┼─▶ deterministic (exact key) → fuzzy (tolerance) → exception classify → LLM resolve (Claude, only ambiguous) → report
merchant_ledger.csv ─┘                                                                              ↓
                                                                                         Q&A Agent (CLI, 6 tools)
```

| Pass | What it proves | Result on synthetic data |
|------|----------------|--------------------------|
| **Deterministic** | Exact `order_id ↔ order_id_ref` after strip/upper normalization | 73.75% (59/80) |
| **Fuzzy** | Amount ≤ Rs 5, date ≤ 5 days, rapidfuzz ≥ 80%, split/batch detection | **87.50%** (70/80), +13.75pp |
| **Exception classifier** | Every leftover → one of 9 named types with evidence | 24 exceptions / 9 events |
| **LLM resolver** | Claude only for `UNRESOLVED_AMBIGUOUS` (0 in current data — correctly idle) | 0 calls, full failure-path coverage |
| **Reporter** | Match rate vs `DATA.md` ground truth → `reconciliation_report.json` | Record counts match ✓ |
| **Cash forecaster** *(stretch)* | 14-day inflow projection from unsettled exceptions | INR 1.59 Cr projected |
| **Q&A agent** | 6 tools over live pipeline data, zero hallucinated numbers | 11 test questions |

Stance: **match what you can prove, name what you can't, never hide an exception.**

---

## Quick Start (Fresh Clone)

```bash
git clone https://github.com/AARAYHARSHIT/Trueup.git
cd Trueup/trueup

# 1. Virtual environment (first time only)
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

# 2. Install dependencies (first time only)
pip install -r requirements.txt

# 3. Configure LLM key (only needed for live Q&A agent calls)
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
# then edit .env and set ANTHROPIC_API_KEY=sk-ant-...

# 4. One-command demo (generates data, runs pipeline, prints reports)
bash run_demo.sh
# Windows without bash:  python -m src.data_generator && python -m src.reporter && python -m pytest -q
```

The pipeline runs with **zero manual steps**. Reports land in `reports/reconciliation_report.json`. Tests run without an API key (LLM paths are dry-run mocked).

---

## Demo Script — What Evaluators See

```bash
bash run_demo.sh
```

What it does, in order:

1. **Install check** — verifies `venv` + `requirements.txt`
2. **Generate data** — `python -m src.data_generator` (seed=42, deterministic — byte-identical every run: 80 gateway / 75 bank / 78 ledger, 73 edge cases across 10 categories + 25 clean triples)
3. **Run pipeline** — `python -m src.reporter` prints the reconciliation report (deterministic vs final vs improvement, split/batch counts, exception breakdown, ground truth comparison)
4. **Cash forecast** — `python -m src.cash_forecaster` prints 14-day projected inflows
5. **Run tests** — `python -m pytest -q` (196 tests, ~35s) — proves every claim above
6. **Q&A smoke test** — direct tool calls: `get_match_rate`, `list_exceptions`, `explain_match ORD-10071`, `get_cash_position`, `get_cash_forecast` (no API key needed for tool smoke test; full agent needs `ANTHROPIC_API_KEY`)

Expected output (numbers are fixed — any change is a regression):

```
deterministic (Pass 1): 59/80 = 73.75%
final (after fuzzy):    70/80 = 87.50%
improvement:            +13.75pp
exceptions: 24 across 9 events (BATCH_SETTLEMENT 15, MISSING_SETTLEMENT 6, ORPHAN_LEDGER 3)
196 passed
```

---

## Q&A Agent

The agent answers natural-language questions about the *live* pipeline data. The system prompt forbids inventing numbers — every figure comes from a tool result.

**Six tools:**

| Tool | Returns | Example question |
|------|---------|------------------|
| `get_match_rate()` | Deterministic vs final, per-pass details | “What is the current match rate?” |
| `list_exceptions(filter)` | Exceptions filtered by type or source | “List all MISSING_SETTLEMENT exceptions” |
| `explain_match(txn_id)` | Matched path or exception for one order | “What happened to ORD-10071?” |
| `summarize(period)` | Summary for a date range | “Give me a summary of August 2026” |
| `get_cash_position()` | Unreconciled cash exposure | “What is the total unreconciled position?” |
| `get_cash_forecast(horizon_days)` | Projected inflows, learned settlement lags | “What is the cash flow forecast for the next two weeks?” |

```bash
# Interactive (ask questions one at a time)
python -m src.qa_agent

# Single question (non-interactive)
python -m src.qa_agent "What is the current match rate?"

# 11 canonical test questions (requires ANTHROPIC_API_KEY for LLM loop)
python -m src.qa_agent --test

# Verbose (shows tool calls)
python -m src.qa_agent --verbose "Explain transaction ORD-10044"

# Direct tool smoke test (no API key needed)
python -c "from src.qa_agent import get_match_rate, get_cash_position; print(get_match_rate()); print(get_cash_position())"
```

---

## Verified Numbers (Evaluator Checklist)

| Metric | Value | Source |
|--------|-------|--------|
| Gateway transactions | 80 | `data/gateway_log.csv` |
| Bank settlements | 75 | `data/bank_settlement.csv` |
| Merchant ledger entries | 78 | `data/merchant_ledger.csv` |
| Clean 1:1:1 triples | 25 | `data/ground_truth.json` / `DATA.md` |
| Edge cases | 73 across 10 categories | `data/DATA.md` |
| Deterministic match rate | 73.75% (59/80) | `reports/reconciliation_report.json` |
| Final match rate | 87.50% (70/80) | `reports/reconciliation_report.json` |
| Improvement | +13.75pp | reporter comparison |
| Split detected | 4/4 | fuzzy matcher |
| Batch detected | 2/3 (3rd has `N/A-BATCH` low edit distance) | fuzzy matcher |
| Exceptions | 24 | `reports/exceptions.json`* |
| Distinct economic events | 9 | exception `event_key` grouping |
| By type | BATCH 15, MISSING 6, ORPHAN 3 (6 types = 0 — correctly resolved by matcher) | classifier |
| Unreconciled cash | Tool-computable via `get_cash_position()` | Q&A agent |
| Cash forecast (14d) | INR 1,591,848.06 | `python -m src.cash_forecaster` |
| Tests | **196 / 196 passing** | `pytest -q` |

\* `reports/exceptions.json` is generated on each run (git-ignored). `reports/reconciliation_report.json` is committed as a reference snapshot.

---

## Project Structure

```
trueup/
├── data/
│   ├── gateway_log.csv        # generated (seed=42) — 80 rows
│   ├── bank_settlement.csv    # generated — 75 rows
│   ├── merchant_ledger.csv    # generated — 78 rows
│   ├── DATA.md                # human-readable ground truth (every injected case by ID)
│   └── ground_truth.json      # machine-readable twin (reporter compares against this)
├── src/
│   ├── schemas.py             # GatewayTransaction, BankSettlement, MerchantLedger + MatchResult, UnmatchedRecord
│   ├── data_generator.py      # seeded synthetic CSVs + 10 edge categories (seed=42)
│   ├── deterministic_matcher.py # Pass 1 — exact key, fail-fast loaders
│   ├── fuzzy_matcher.py       # Pass 2 — amount/date/edit + split/batch detection
│   ├── exception_classifier.py# Pass 3 — 9 named types, precedence-ordered engine
│   ├── llm_resolver.py        # Pass 4 — Claude for UNRESOLVED_AMBIGUOUS only, dry-run, call log
│   ├── reporter.py            # Pass 5 — pipeline runner + ground truth comparison → reconciliation_report.json
│   ├── cash_forecaster.py     # Stretch — 14-day inflow forecast from settlement lag distribution
│   └── qa_agent.py            # 6-tool Q&A agent (custom Anthropic tool loop, no framework)
├── tests/
│   ├── conftest.py
│   ├── test_data_generator.py      # 13 tests
│   ├── test_deterministic.py       # 15 tests
│   ├── test_fuzzy.py               # 14 tests
│   ├── test_exceptions.py          # 13 tests
│   ├── test_llm_resolver.py        # 25 tests
│   ├── test_reporter.py            # 18 tests
│   ├── test_pipeline.py            # 17 tests
│   ├── test_qa_agent.py            # 70 tests
│   └── test_cash_forecaster.py     # 9 tests  (total 196)
├── reports/
│   └── reconciliation_report.json  # committed reference snapshot (regenerated by reporter)
├── requirements.txt
├── .env.example               # ANTHROPIC_API_KEY=your_key_here (never commit .env)
├── .gitignore
├── run_demo.sh                # one-command demo for evaluators
└── README.md                  # this file
```

---

## Data & Ground Truth

The dataset is **synthetic and seeded** (`seed=42`). Every run is byte-identical.

- Dates: Aug 1–21, 2026. Amounts: Rs 50–25,000 (Decimal, paise-exact). Refs: `ORD-XXXXX` / `UTR-XXXXX`.
- 10 injected categories (73 cases): Gateway fee (8), Date drift (10), Split (4), Batch (3×3), Garbled ref (5), Duplicate near-match (4 pairs), Missing settlement (3), Orphan ledger (3), Rounding (5), Partial refund (3) + 25 clean 1:1:1 triples.
- `data/DATA.md` documents every case by ID — the evaluator cross-check. `data/ground_truth.json` is its machine twin that the reporter compares against.

### Why Row Counts Are 80/75/78 (Not Exactly 70 Each)

The 10 mandated edge categories have fixed minimums that change per-source math: splits add extra bank rows (+4), garbled refs carry no ledger row (−5), missing settlements have no bank row (−3), orphans exist only in the ledger (+3). With those locked, exactly-70-per-source and “25–30 clean triples” can only co-exist at 25 clean — landing the three files nearest ~70.

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Language | Python 3.11+ | stdlib breadth, evaluator-friendly |
| Data IO | pandas | CSV loading/grouping only at the IO boundary |
| Money | `Decimal` (stdlib) | Paise-exact; float would corrupt rounding-diff cases |
| Fuzzy text | rapidfuzz | Fast, maintained edit distance — only external matching lib |
| LLM | Anthropic SDK (Claude Sonnet 4.5) | Direct tool-calling; no framework |
| Agent | Custom tool loop | 6 tools don't justify LangChain — full logging control |
| Config | python-dotenv | `.env` for API key, `.env.example` committed |
| Testing | pytest | Fixtures make edge-case tests trivial |

**Key decisions:** cascade (cheapest, most certain first; LLM is last resort) · pure-Python matching cores (testability + Decimal precision) · reports as JSON = the agent interface (structurally prevents hallucination) · no LangChain, no web UI, no live API integrations (per brief: CLI suffices).

---

## Testing

```bash
python -m pytest -v        # verbose, per-test
python -m pytest -q        # summary (196 passed)
python -m pytest tests/test_qa_agent.py -v
python -m pytest tests/test_data_generator.py -v
```

No API key needed for tests — LLM paths run in `dry_run=True` or are mocked. Coverage: every exception type has a micro-fixture, every pipeline handoff is tested, no double-consumption of records, every report field is asserted, and every Q&A tool is dispatched + error-handled.

---

## Environment

- Copy `.env.example` → `.env` and set `ANTHROPIC_API_KEY`. Without it the pipeline still runs end-to-end (reporter dry-runs the LLM resolver); only live `qa_agent --test` / interactive LLM calls need the key.
- Never commit `.env` — it is git-ignored and absent from history (verified).

---

## Track & Submission

- Track 04 — Razorpay AI Buildathon “Run the books and the cash position.”
- Build window Aug 22 → Sep 4, 2026. Repo is `trueup/` inside `https://github.com/AARAYHARSHIT/Trueup`.
- Fresh-clone verified: clone → venv → pip install → `bash run_demo.sh` in under 5 minutes.

---

## REST API (Phase 1)

A versioned FastAPI layer wraps the engine without modifying it.

```bash
# From project root
pip install -r api_server/requirements.txt
python -m uvicorn api_server.app.main:app --host 127.0.0.1 --port 8000
# Docs: http://127.0.0.1:8000/api/v1/docs
```

**Endpoints:**

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/health` | GET | Pipeline status + match rate |
| `/api/v1/summary` | GET | Deterministic vs final stats |
| `/api/v1/pipeline` | GET | Pass-by-pass details |
| `/api/v1/exceptions` | GET | 24 exceptions, filterable |
| `/api/v1/transactions/{txn_id}` | GET | Transaction investigation |
| `/api/v1/cash-position` | GET | Unreconciled exposure |
| `/api/v1/forecast` | GET | 14-day inflow projection |
| `/api/v1/chat` | POST | Q&A via Groq/Gemini |
| `/api/v1/runs/demo` | POST | Re-run pipeline |
| `/api/v1/reports/reconciliation` | GET | Full report JSON |

**LLM Provider:** Groq (primary) + Gemini (fallback). Set `LLM_PROVIDER=groq` and `GROQ_API_KEY` in `.env`.

---

## Web UI — Investigation (Phase 3)

The Next.js frontend includes a transaction investigation page at `/transactions/[txnId]` that makes the core product claim visible: **TrueUp doesn't just say "failed"; it tells you why.**

### Features

- **Evidence timeline** — 7-step pipeline visualization (Gateway → Bank → Ledger → Pass 1–4)
- **Source comparison** — Gateway/Bank/Ledger side-by-side with amounts, dates, UTR
- **Pass-by-pass explanation** — which pass resolved it + method name
- **Confidence indicators** — color-coded bar (green ≥80%, amber 50–80%, red <50%)
- **Named exception display** — exception type with human-readable description
- **Linked IDs** — cross-references shown as clickable badges
- **Copy as text** — full investigation report exportable to clipboard
- **Compare view** — matched vs unmatched comparison for demo pair

### Demo transactions

| ID | Status | Type | Amount |
|---|---|---|---|
| `ORD-10071` | EXCEPTION | MISSING_SETTLEMENT | ₹21,643.55 |
| `ORD-10001` | MATCHED | exact_order_id | ₹15,240.00 |
| `ORD-99999` | NOT_FOUND | — | — |

```bash
# Start the web UI
cd frontend && npm install && npm run dev
# Navigate to http://localhost:3000/transactions/ORD-10071
```

---

## Web Dashboard (Phase 5)

The Next.js frontend provides a complete visual interface for the reconciliation engine.

### Features

- **Onboarding Experience** — Welcome screen with guided demo
- **Guided Demo** — 5-step narrative walkthrough (Problem → Pipeline → Results → Investigation → AI Controller)
- **Presentation Mode** — Full-screen slideshow with keyboard navigation
- **Transaction Investigation** — Evidence timeline, source comparison, confidence indicators
- **AI Controller** — Natural language Q&A with 6 tools
- **Report Download** — JSON, TXT, and clipboard export
- **Responsive Design** — Works on desktop and mobile

### Running the Web Dashboard

```bash
# Start backend API
cd api_server
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Start frontend (in separate terminal)
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### Keyboard Navigation

- **Arrow Left/Right** — Navigate between steps
- **Space** — Next step
- **Escape** — Exit presentation/guided demo
- **F** — Toggle fullscreen

### Quality Gates

```bash
# Backend tests
cd trueup && python -m pytest -q

# Frontend typecheck
cd frontend && npm run typecheck

# Frontend lint
cd frontend && npm run lint

# Frontend production build
cd frontend && npm run build
```
