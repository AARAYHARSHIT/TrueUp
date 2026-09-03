"""TrueUp FastAPI Application.

Versioned REST API layer around the existing TrueUp reconciliation engine.
All business logic comes from trueup/src/ -- this is a thin presentation layer.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TrueUp API",
    description=(
        "AI Finance Controller — reconciliation engine REST API. "
        "Exposes the existing TrueUp pipeline (deterministic → fuzzy → "
        "exception classify → LLM resolve) through versioned HTTP endpoints."
    ),
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS (allow frontend dev server)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

from api_server.app.routes.health import router as health_router
from api_server.app.routes.summary import router as summary_router
from api_server.app.routes.pipeline import router as pipeline_router
from api_server.app.routes.exceptions import router as exceptions_router
from api_server.app.routes.transactions import router as transactions_router
from api_server.app.routes.cash import router as cash_router
from api_server.app.routes.forecast import router as forecast_router
from api_server.app.routes.chat import router as chat_router
from api_server.app.routes.runs import router as runs_router
from api_server.app.routes.reports import router as reports_router

app.include_router(health_router, prefix="/api/v1", tags=["Health"])
app.include_router(summary_router, prefix="/api/v1", tags=["Summary"])
app.include_router(pipeline_router, prefix="/api/v1", tags=["Pipeline"])
app.include_router(exceptions_router, prefix="/api/v1", tags=["Exceptions"])
app.include_router(transactions_router, prefix="/api/v1", tags=["Transactions"])
app.include_router(cash_router, prefix="/api/v1", tags=["Cash Position"])
app.include_router(forecast_router, prefix="/api/v1", tags=["Forecast"])
app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
app.include_router(runs_router, prefix="/api/v1", tags=["Runs"])
app.include_router(reports_router, prefix="/api/v1", tags=["Reports"])


@app.get("/", tags=["Root"])
def root() -> dict:
    """API root — returns basic info."""
    return {
        "name": "TrueUp API",
        "version": "1.0.0",
        "docs": "/api/v1/docs",
        "health": "/api/v1/health",
    }
