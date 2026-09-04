"""Gemini LLM provider for TrueUp.

Implements the LLMProvider interface using Google's Gemini API.
Gemini serves as the fallback provider when Groq is unavailable.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from api_server.app.services.llm_provider import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Gemini LLM provider using Google's Generative AI API."""

    def __init__(self) -> None:
        self._api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self._model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

    @property
    def provider_name(self) -> str:
        return "gemini"

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
        """Send a chat completion request via Gemini's REST API."""
        if not self._api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

        import httpx

        # Build Gemini function declarations
        gemini_tools = []
        for tool in tools:
            gemini_tools.append({
                "function_declarations": [{
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": _convert_schema(tool.get("input_schema", tool.get("parameters", {}))),
                }]
            })

        # Convert messages to Gemini format
        contents = _convert_messages(messages, system)

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.0,
            },
        }
        if gemini_tools:
            payload["tools"] = gemini_tools

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self._model}:generateContent?key={self._api_key}"
        )

        t0 = time.monotonic()
        try:
            resp = httpx.post(url, json=payload, timeout=60.0)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            raise RuntimeError(f"Gemini API call failed: {exc}") from exc

        elapsed_ms = round((time.monotonic() - t0) * 1000)
        data = resp.json()

        candidate = data.get("candidates", [{}])[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        finish_reason = candidate.get("finishReason", "STOP")

        text_parts = []
        tool_calls: list[ToolCall] = []
        call_counter = 0

        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            if "functionCall" in part:
                fc = part["functionCall"]
                call_counter += 1
                tool_calls.append(ToolCall(
                    id=f"call_{call_counter}",
                    name=fc["name"],
                    input=fc.get("args", {}),
                ))

        usage_meta = data.get("usageMetadata", {})

        logger.debug(
            "Gemini response: model=%s elapsed=%dms stop=%s tools=%d",
            self._model, elapsed_ms, finish_reason, len(tool_calls),
        )

        return LLMResponse(
            text="\n".join(text_parts).strip(),
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
            input_tokens=usage_meta.get("promptTokenCount", 0),
            output_tokens=usage_meta.get("candidatesTokenCount", 0),
        )


def _convert_schema(schema: dict) -> dict:
    """Convert OpenAI-style schema to Gemini-compatible format."""
    if not schema:
        return {"type": "OBJECT", "properties": {}}

    result: dict[str, Any] = {}

    type_map = {
        "object": "OBJECT",
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "array": "ARRAY",
    }

    if "type" in schema:
        result["type"] = type_map.get(schema["type"], schema["type"].upper())

    if "properties" in schema:
        result["properties"] = {}
        for key, prop in schema["properties"].items():
            result["properties"][key] = _convert_schema(prop)

    if "description" in schema:
        result["description"] = schema["description"]

    if "required" in schema:
        result["required"] = schema["required"]

    if "items" in schema:
        result["items"] = _convert_schema(schema["items"])

    if "enum" in schema:
        result["enum"] = schema["enum"]

    return result


def _convert_messages(messages: list[dict], system: str) -> list[dict]:
    """Convert OpenAI-style messages to Gemini format."""
    contents = []

    # Add system instruction as a user/model pair if present
    if system:
        contents.append({
            "role": "user",
            "parts": [{"text": f"System: {system}"}],
        })
        contents.append({
            "role": "model",
            "parts": [{"text": "Understood. I will follow these instructions."}],
        })

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        if role == "assistant":
            gemini_role = "model"
        elif role == "tool":
            gemini_role = "user"
        else:
            gemini_role = "user"

        parts = []
        if isinstance(content, str) and content:
            parts.append({"text": content})
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_result":
                        parts.append({
                            "functionResponse": {
                                "name": block.get("tool_use_id", "unknown"),
                                "response": {"result": block.get("content", "")},
                            }
                        })
                    elif block.get("type") == "text":
                        parts.append({"text": block.get("text", "")})
                    elif "text" in block:
                        parts.append({"text": block["text"]})
                    elif "functionCall" in block:
                        parts.append({"functionCall": block["functionCall"]})

        if "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                parts.append({
                    "functionCall": {
                        "name": fn.get("name", ""),
                        "args": args,
                    }
                })

        if role == "tool":
            parts.append({
                "functionResponse": {
                    "name": msg.get("tool_name") or msg.get("tool_call_id", "unknown"),
                    "response": {"result": content if isinstance(content, str) else json.dumps(content)},
                }
            })

        if parts:
            contents.append({"role": gemini_role, "parts": parts})

    return contents
