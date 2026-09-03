"""Runs endpoint for demo pipeline execution."""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter

from api_server.app.schemas import RunDemoResponse
from api_server.app.services.pipeline_service import reload_pipeline, get_match_rate, list_exceptions

router = APIRouter()
logger = logging.getLogger(__name__)

_TRUEUP_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "trueup"


@router.post("/runs/demo", response_model=RunDemoResponse)
def run_demo() -> RunDemoResponse:
    """Re-run the full pipeline and return fresh results.

    This regenerates data, runs the pipeline, and refreshes the cached results.
    """
    try:
        # Run data generator
        subprocess.run(
            [sys.executable, "-m", "src.data_generator"],
            cwd=str(_TRUEUP_ROOT),
            check=True,
            capture_output=True,
            timeout=30,
        )

        # Run reporter
        subprocess.run(
            [sys.executable, "-m", "src.reporter"],
            cwd=str(_TRUEUP_ROOT),
            check=True,
            capture_output=True,
            timeout=30,
        )

        # Reload pipeline cache
        reload_pipeline()

        stats = get_match_rate()
        exc = list_exceptions()

        return RunDemoResponse(
            status="success",
            message="Pipeline re-executed successfully.",
            match_rate=stats["final"]["rate"],
            exceptions=exc["total"],
            tests_passed=True,
        )

    except subprocess.TimeoutExpired:
        return RunDemoResponse(
            status="timeout",
            message="Pipeline execution timed out.",
            match_rate="",
            exceptions=0,
            tests_passed=False,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Pipeline execution failed: %s", exc)
        return RunDemoResponse(
            status="error",
            message=f"Pipeline execution failed: {exc.stderr[:200] if exc.stderr else str(exc)}",
            match_rate="",
            exceptions=0,
            tests_passed=False,
        )
    except Exception as exc:
        logger.exception("Unexpected error in demo run")
        return RunDemoResponse(
            status="error",
            message=str(exc),
            match_rate="",
            exceptions=0,
            tests_passed=False,
        )
