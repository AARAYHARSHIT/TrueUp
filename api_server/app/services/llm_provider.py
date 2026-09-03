"""LLM provider abstraction for TrueUp.

Provides a unified interface for different LLM backends (Groq, Gemini)
while preserving the existing tool-calling loop and six TrueUp tools.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    """Represents a tool call returned by the LLM."""
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send a chat completion request with tool support.

        Args:
            messages: Conversation history in OpenAI-compatible format.
            system: System prompt.
            tools: Tool definitions in OpenAI function-calling format.
            max_tokens: Maximum tokens for the response.

        Returns:
            LLMResponse with text and/or tool_calls.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'groq', 'gemini')."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name being used."""
        ...


def get_provider() -> LLMProvider:
    """Factory function to get the configured LLM provider.

    Reads LLM_PROVIDER env var to select the provider.
    Falls back to Groq if not set, then to Gemini if Groq fails.

    Returns:
        Configured LLMProvider instance.
    """
    provider_name = os.getenv("LLM_PROVIDER", "groq").lower().strip()

    if provider_name == "gemini":
        from api_server.app.services.gemini_provider import GeminiProvider
        return GeminiProvider()

    # Default to Groq
    from api_server.app.services.groq_provider import GroqProvider
    return GroqProvider()
