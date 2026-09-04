"""Groq LLM provider for TrueUp.

Implements the LLMProvider interface using Groq's OpenAI-compatible API.
Groq provides fast inference with function/tool calling support.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from api_server.app.services.llm_provider import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    """Groq LLM provider using the OpenAI-compatible API."""

    def __init__(self) -> None:
        self._api_key = os.getenv("GROQ_API_KEY", "").strip()
        self._model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    def chat(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send a chat completion request via Groq's OpenAI-compatible API."""
        if not self._api_key:
            raise RuntimeError("GROQ_API_KEY environment variable is not set.")

        import httpx

        # Build OpenAI-compatible tool definitions
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", tool.get("parameters", {})),
                },
            })

        # Prepend system message
        full_messages = [{"role": "system", "content": system}] + messages

        payload = {
            "model": self._model,
            "messages": full_messages,
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }
        if openai_tools:
            payload["tools"] = openai_tools

        t0 = time.monotonic()
        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_msg = err_json.get("error", {}).get("message", resp.text)
                except Exception:
                    err_msg = resp.text
                raise RuntimeError(f"Groq API error ({resp.status_code}): {err_msg}")
        except Exception as exc:
            logger.error("Groq API error: %s", exc)
            raise RuntimeError(f"Groq API call failed: {exc}") from exc

        elapsed_ms = round((time.monotonic() - t0) * 1000)
        data = resp.json()

        choice = data["choices"][0]
        message = choice["message"]
        finish_reason = choice.get("finish_reason", "stop")

        text = message.get("content") or ""
        tool_calls: list[ToolCall] = []

        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                fn = tc["function"]
                args = fn.get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                tool_calls.append(ToolCall(
                    id=tc.get("id", f"call_{int(time.time()*1000)}"),
                    name=fn["name"],
                    input=args,
                ))

        usage = data.get("usage", {})

        logger.debug(
            "Groq response: model=%s elapsed=%dms stop=%s tools=%d",
            self._model, elapsed_ms, finish_reason, len(tool_calls),
        )

        return LLMResponse(
            text=text.strip(),
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )
