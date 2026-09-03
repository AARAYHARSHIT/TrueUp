# TrueUp — Web Dashboard

> Next.js 16 frontend for the TrueUp reconciliation engine.
> Clean Ledger dark finance design. Swiss grid. Semantic colors.

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

**Prerequisites:** The FastAPI backend must be running on port 8000.

```bash
# From project root
pip install -r api_server/requirements.txt
python -m uvicorn api_server.app.main:app --host 127.0.0.1 --port 8000
```

## Features

### Onboarding Experience

- **Welcome Screen** — First-time visitors see a clean landing page with "Start Demo" and "Explore Dashboard" options
- **Guided Demo** — 5-step narrative walkthrough explaining the reconciliation engine
- **Presentation Mode** — Full-screen slideshow with keyboard navigation

### Routes

| Route | Description |
|---|---|
| `/` | Overview dashboard — match rate hero, KPI cards, pipeline waterfall, exceptions |
| `/reconcile` | Pipeline waterfall detail — 5-pass visual flow |
| `/exceptions` | Exception table with type/source filters |
| `/transactions` | Search by order ID — investigation view |
| `/transactions/[txnId]` | Transaction investigation — evidence timeline, source comparison, confidence |
| `/cash` | Cash position + 14-day forecast chart |
| `/reports` | Report viewer with JSON/TXT download and copy to clipboard |

### Investigation Page

The `/transactions/[txnId]` route provides transaction-level investigation:

- **Evidence timeline** — 7-step pipeline visualization
- **Source comparison** — Gateway/Bank/Ledger side-by-side
- **Confidence indicators** — color-coded bar
- **Exception details** — type, reason, evidence, linked records
- **Copy as text** — export full report to clipboard
- **Compare view** — matched vs unmatched comparison

### Demo transactions

- `ORD-10071` — Exception (MISSING_SETTLEMENT)
- `ORD-10001` — Matched (exact_order_id)
- `ORD-99999` — Not Found

## Keyboard Navigation

- **Arrow Left/Right** — Navigate between steps in guided demo/presentation
- **Space** — Next step
- **Escape** — Exit presentation/guided demo
- **F** — Toggle fullscreen in presentation mode

## Report Download

The Reports page supports multiple export formats:

- **Download JSON** — Full structured report
- **Download TXT** — Human-readable text format
- **Copy** — Copy report to clipboard

## Tech Stack

| Layer | Choice |
|---|---|
| Framework | Next.js 16 (App Router) |
| Styling | Tailwind CSS v4 |
| State | TanStack Query v5 |
| Animation | Motion (motion/react) v13 |
| Charts | Recharts v3 |
| Icons | Lucide React |
| Language | TypeScript (strict) |

## Design System

Clean Ledger dark finance UI with semantic colors:
- Green = verified/matched
- Amber = needs review
- Red = unresolved/missing
- Blue = structure/navigation

See `app/globals.css` for the full token set.

## Error Handling

- **Error Boundary** — Catches and displays runtime errors
- **Global Loading** — Consistent loading states across the application
- **Retry Mechanisms** — All data fetching includes retry options

## Responsive Design

- Mobile-friendly navigation
- Collapsible sidebar on smaller screens
- Responsive grid layouts
- Touch-friendly interactions
