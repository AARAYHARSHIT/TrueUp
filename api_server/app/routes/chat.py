"""Chat endpoint for Q&A agent."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from api_server.app.schemas import ChatRequest, ChatResponse
from api_server.app.services.qa_service import run_chat

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Ask a natural-language question about the reconciliation data.

    The agent uses six tools to retrieve facts and compose grounded answers.
    """
    try:
        from api_server.app.services.llm_provider import get_provider
        from api_server.app.services.groq_provider import GroqProvider
        from api_server.app.services.gemini_provider import GeminiProvider

        provider = None
        if request.provider:
            if request.provider.lower() == "gemini":
                provider = GeminiProvider()
            elif request.provider.lower() == "groq":
                provider = GroqProvider()
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown provider '{request.provider}'. Use 'groq' or 'gemini'.",
                )

        result = run_chat(request.question, provider=provider)
        return ChatResponse(**result)

    except RuntimeError as exc:
        # LLM provider not configured or API error
        raise HTTPException(
            status_code=503,
            detail={
                "error": str(exc),
                "hint": "Configure GROQ_API_KEY and LLM_PROVIDER in your .env file.",
            },
        )
    except Exception as exc:
        logger.exception("Chat error")
        raise HTTPException(status_code=500, detail={"error": str(exc)})
