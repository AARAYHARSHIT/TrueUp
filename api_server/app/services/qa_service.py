"""Q&A service for TrueUp API.

Runs the existing tool-calling loop through the provider abstraction,
preserving the six TrueUp tools and the custom agent architecture.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from api_server.app.services.llm_provider import LLMProvider, get_provider
from api_server.app.services.pipeline_service import (
    SYSTEM_PROMPT,
    TOOLS,
    dispatch_tool,
)

logger = logging.getLogger(__name__)


def run_chat(question: str, provider: LLMProvider | None = None) -> dict:
    """Run a question through the tool-calling loop and return the answer.

    Args:
        question: Natural-language question about the reconciliation data.
        provider: Optional pre-configured provider. If None, uses get_provider().

    Returns:
        Dict with 'answer', 'tools_used', and 'provider' fields.
    """
    if provider is None:
        provider = get_provider()

    messages: list[dict] = [{"role": "user", "content": question}]
    tools_used: list[dict] = []
    max_iterations = 10  # safety limit

    for _ in range(max_iterations):
        response = provider.chat(
            messages=messages,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            max_tokens=1024,
        )

        if response.stop_reason == "end_turn" or not response.tool_calls:
            return {
                "answer": response.text,
                "tools_used": tools_used,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
            }

        # Process tool calls
        tool_calls_payload = []
        for tc in response.tool_calls:
            tool_calls_payload.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.input),
                },
            })

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": response.text or None,
            "tool_calls": tool_calls_payload,
        }
        messages.append(assistant_msg)

        # Execute tools and build results
        for tc in response.tool_calls:
            result_json = dispatch_tool(tc.name, tc.input)
            tools_used.append({
                "name": tc.name,
                "input": tc.input,
                "result_summary": result_json[:200],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_json,
            })

    # Safety fallback
    return {
        "answer": "I was unable to fully answer this question within the allowed iterations. Please try a simpler question.",
        "tools_used": tools_used,
        "provider": provider.provider_name,
        "model": provider.model_name,
    }
