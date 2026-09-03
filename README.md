# TrueUp — AI Finance Controller

> **Razorpay AI Buildathon — Track 04: "Run the books and the cash position"**
>
> Deterministic-first, fuzzy-second, LLM-only-when-genuinely-ambiguous reconciliation of payment data. No hallucinations. Every number proven against ground truth.

---

## What It Does

Businesses see the same money three different ways: the **gateway log** says one thing, the **bank settlement file** says another, and the **merchant ledger** says a third. Reconciling them today means hours of `VLOOKUP` against gateway fees, T+2/T+3 settlement drift, split payouts, garbled UTRs, and paise-level rounding noise.

**TrueUp automates that loop and is honest about what it can't match.**

```
gateway_log.csv ─┐
bank_settlement.csv ─┼─▶ deterministic (exact key) → fuzzy (tolerance) → exception classify → LLM resolve (only ambiguous) → report
merchant_ledger.csv ─┘                                                                              ↓
                                                                                          Q&A Agent (CLI + Web)
```

| Pass | What it proves | Result on synthetic data |
|------|----------------|--------------------------|
| **Deterministic** | Exact `order_id ↔ order_id_ref` after strip/upper normalization | 73.75% (59/80) |
| **Fuzzy** | Amount ≤ ₹5, date ≤ 5 days, rapidfuzz ≥ 80%, split/batch detection | **87.50%** (70/80), +13.75pp |
| **Exception classifier** | Every leftover → one of 9 named types with evidence | 24 exceptions / 9 events |
| **LLM resolver** | Only for `UNRESOLVED_AMBIGUOUS` (0 in current data — correctly idle) | 0 calls, full failure-path coverage |
| **Reporter** | Match rate vs ground truth → `reconciliation_report.json` | Record counts match ✓ |
| **Cash forecaster** | 14-day inflow projection from unsettled exceptions | ₹1.59 Cr projected |
| **Q&A agent** | 6 tools over live pipeline data, zero hallucinated numbers | 11 canonical questions |

**Stance:** match what you can prove, name what you can't, never hide an exception.

---

## Repository Structure

```
TrueUp/
├── trueup/                    # Core reconciliation engine (Python)
│   ├── src/                   # 10 engine modules
│   ├── tests/                 # 196 tests
│   ├── data/                  # Synthetic CSV + ground truth (seed=42)
│   ├── reports/               # Generated reconciliation_report.json
│   ├── requirements.txt
│   ├── run_demo.sh            # Engine-only demo runner
│   └── .env.example
│
├── api_server/                # FastAPI REST layer (Python)
│   ├── app/                   # Routes, services, schemas
│   ├── tests/                 # 30 integration tests
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                  # Next.js 16 dashboard (TypeScript)
│   ├── app/                   # 10 pages (App Router)
│   ├── components/            # 28 React components
│   ├── hooks/                 # 10 TanStack Query hooks
│   ├── lib/                   # API client, types, formatters
│   ├── package.json
│   ├── next.config.ts         # API proxy to port 8000
│   └── .env.example
│
├── run_demo.sh                # Root unified demo runner
└── README.md                  # This file
```

---

## Quick Start (Fresh Clone)

```bash
git clone https://github.com/AARAYHARSHIT/Trueup.git
cd Trueup
```

### Option 1: One-Command Verification (Recommended)

```bash
# Run all validation steps — no persistent servers started
bash run_demo.sh
```

This runs:
1. Environment checks (Python 3.11+, Node 18+)
2. Engine validation (data gen → pipeline → 196 tests)
3. API validation (imports → 30 tests)
4. Frontend validation (typecheck → production build)

**No API keys required** — all LLM paths run in dry-run mode.

### Option 2: Component-Level Runs

```bash
# Engine only (includes data gen, pipeline, all tests)
bash run_demo.sh --engine

# API only (imports + tests)
bash run_demo.sh --api

# Frontend only (typecheck + build)
bash run_demo.sh --frontend

# Full (same as no args)
bash run_demo.sh --full
```

### Option 3: Manual Development Setup

**Engine (Terminal 1):**
```bash
cd trueup
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate
pip install -r requirements.txt
python -m src.data_generator
python -m src.reporter
python -m pytest -q
```

**API Server (Terminal 2):**
```bash
cd api_server
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -r ../trueup/requirements.txt
python -m uvicorn api_server.app.main:app --host 127.0.0.1 --port 8000
# Docs: http://127.0.0.1:8000/api/v1/docs
```

**Frontend (Terminal 3):**
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

## Environment Variables

Each component has its own `.env.example` — copy to `.env` and fill in:

### `trueup/.env.example`
```bash
ANTHROPIC_API_KEY=your_key_here
```
*Only needed for live Q&A agent (`python -m src.qa_agent --test`). Pipeline runs fully without it.*

### `api_server/.env.example`
```bash
LLM_PROVIDER=groq
GROQ_API_KEY=
GEMINI_API_KEY=
```
*Only needed for `/api/v1/chat` endpoint. All other endpoints work without keys.*

### `frontend/.env.example`
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```
*Points to API server. Do not change unless API runs elsewhere.*

---

## Engine CLI Usage

```bash
cd trueup
venv\Scripts\activate

# One-command demo (data + pipeline + tests)
bash run_demo.sh

# Individual steps
python -m src.data_generator        # Generate synthetic data (seed=42)
python -m src.reporter              # Run pipeline + print report
python -m src.cash_forecaster       # 14-day cash forecast
python -m pytest -q                 # All 196 tests

# Q&A Agent
python -m src.qa_agent                          # Interactive
python -m src.qa_agent "What is the match rate?" # Single question
python -m src.qa_agent --test                   # 11 canonical questions (needs ANTHROPIC_API_KEY)
python -m src.qa_agent --verbose "Explain ORD-10044"
```

### Direct Tool Access (No API Key Needed)
```python
from src.qa_agent import get_match_rate, list_exceptions, explain_match, get_cash_position, get_cash_forecast

print(get_match_rate())
print(list_exceptions("MISSING_SETTLEMENT"))
print(explain_match("ORD-10071"))
print(get_cash_position())
print(get_cash_forecast())
```

---

## API Startup

```bash
cd api_server
venv\Scripts\activate
pip install -r requirements.txt
pip install -r ../trueup/requirements.txt
python -m uvicorn api_server.app.main:app --host 127.0.0.1 --port 8000
```

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
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

### Demo Transactions
| ID | Status | Type | Amount |
|---|---|---|---|
| `ORD-10071` | EXCEPTION | MISSING_SETTLEMENT | ₹21,643.55 |
| `ORD-10001` | MATCHED | exact_order_id | ₹15,240.00 |
| `ORD-99999` | NOT_FOUND | — | — |

---

## Frontend Startup

```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000). **Requires API server running on port 8000.**

### Routes
| Route | Description |
|-------|-------------|
| `/` | Overview — match rate hero, KPI cards, pipeline waterfall, exceptions |
| `/reconcile` | Pipeline waterfall detail — 5-pass visual flow |
| `/exceptions` | Exception table with type/source filters |
| `/transactions` | Search by order ID |
| `/transactions/[txnId]` | Investigation — evidence timeline, source comparison, confidence |
| `/cash` | Cash position + 14-day forecast chart |
| `/reports` | Report viewer with JSON/TXT download |
| `/agent` | AI Controller — natural language Q&A |

### Keyboard Navigation
- **Arrow Left/Right** — Navigate guided demo/presentation steps
- **Space** — Next step
- **Escape** — Exit presentation/guided demo
- **F** — Toggle fullscreen

---

## Testing

```bash
# Engine (196 tests)
cd trueup && python -m pytest -q

# API (30 tests)
cd .. && python -m pytest api_server/tests/test_api.py -q

# Frontend
cd frontend
npm run typecheck   # TypeScript strict mode
npm run lint        # ESLint (0 errors, warnings only)
npm run build       # Production build
```

---

## One-Command Verification

```bash
bash run_demo.sh
```

**Expected output (exact numbers — any change is a regression):**
```
Engine: 196 passed
  deterministic: 59/80 = 73.75%
  final: 70/80 = 87.50%
  improvement: +13.75pp
  exceptions: 24 across 9 events

API: 30 passed
  health: ok, match_rate=87.50%

Frontend: typecheck OK, build OK
  10 routes compiled
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: rapidfuzz` | Run `pip install -r trueup/requirements.txt` in API venv |
| API health returns `pipeline_loaded: false` | Ensure engine data exists: run `python -m src.data_generator && python -m src.reporter` in `trueup/` |
| Frontend shows "Failed to fetch" | Verify API runs on port 8000; check `frontend/.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8000` |
| Port 8000/3000 in use | Kill existing processes: `taskkill /F /IM python.exe` / `taskkill /F /IM node.exe` |
| `tsc --noEmit` fails | Run `npm install` in `frontend/` |
| LLM calls fail | Set `ANTHROPIC_API_KEY` (engine) or `GROQ_API_KEY` + `LLM_PROVIDER=groq` (API) in `.env` files |

---

## Technology Stack

| Layer | Choice | Why |
|-------|--------|-----|
| **Engine Language** | Python 3.11+ | Stdlib breadth, evaluator-friendly |
| **Data IO** | pandas | CSV loading only at IO boundary |
| **Money Math** | `Decimal` (stdlib) | Paise-exact; float corrupts rounding-diff cases |
| **Fuzzy Matching** | rapidfuzz | Fast, maintained edit distance |
| **LLM (Engine)** | Anthropic SDK (Claude) | Direct tool-calling, no framework |
| **LLM (API)** | Groq (primary) + Gemini (fallback) | Fast inference, free tier |
| **API Framework** | FastAPI | Modern, async, auto-docs |
| **Frontend** | Next.js 16 (App Router) | React 19, Turbopack, server components |
| **Styling** | Tailwind CSS v4 | Clean Ledger dark finance theme |
| **State** | TanStack Query v5 | Server state, caching, retries |
| **Animation** | Motion (motion/react) v13 | Smooth transitions |
| **Charts** | Recharts v3 | Declarative, composable |
| **Icons** | Lucide React | Consistent, accessible |
| **Testing** | pytest / Vitest (via Next) | Fixtures, parametrize, async support |

---

## Key Design Decisions

1. **Cascade Architecture** — Cheapest, most certain first (deterministic → fuzzy → classify → LLM). LLM is last resort.
2. **Pure-Python Matching Cores** — Testability + Decimal precision; no heavy ML dependencies.
3. **Reports as JSON** — Structured output prevents hallucination; feeds Q&A agent directly.
4. **No LangChain / No Live Gateway APIs** — Per brief: CLI + local CSV suffices.
5. **Deterministic Synthetic Data** — Seed=42 guarantees byte-identical runs for evaluators.

---

## Verified Numbers (Evaluator Checklist)

| Metric | Value | Source |
|--------|-------|--------|
| Gateway transactions | 80 | `data/gateway_log.csv` |
| Bank settlements | 75 | `data/bank_settlement.csv` |
| Merchant ledger entries | 78 | `data/merchant_ledger.csv` |
| Clean 1:1:1 triples | 25 | `data/ground_truth.json` |
| Edge cases | 73 across 10 categories | `data/DATA.md` |
| Deterministic match rate | 73.75% (59/80) | `reports/reconciliation_report.json` |
| Final match rate | 87.50% (70/80) | `reports/reconciliation_report.json` |
| Improvement | +13.75pp | Reporter comparison |
| Split detected | 4/4 | Fuzzy matcher |
| Batch detected | 2/3 | Fuzzy matcher |
| Exceptions | 24 | `reports/exceptions.json` |
| Distinct economic events | 9 | Exception `event_key` grouping |
| By type | BATCH 15, MISSING 6, ORPHAN 3 | Classifier |
| Unreconciled cash | ₹205,409.15 | `get_cash_position()` |
| Cash forecast (14d) | ₹1,591,848.06 | `python -m src.cash_forecaster` |
| Tests | **196 / 196 passing** | `pytest -q` |
| API tests | **30 / 30 passing** | `pytest api_server/tests/test_api.py -q` |

---

## License

MIT — see [LICENSE](LICENSE).

---

## Track & Submission

- **Track 04** — Razorpay AI Buildathon "Run the books and the cash position."
- **Build window:** Aug 22 → Sep 4, 2026
- **Fresh-clone verified:** clone → venv → install → `bash run_demo.sh` in under 5 minutes.