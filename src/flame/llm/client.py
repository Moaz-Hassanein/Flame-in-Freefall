"""Provider-agnostic LLM client protocol, response models, and typed exceptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class LLMError(Exception):
    """Base exception for all LLM client failures."""


class LLMTimeout(LLMError):
    """Raised when an LLM request exceeds configured timeout limits."""


class LLMRateLimit(LLMError):
    """Raised when an LLM provider rejects requests due to rate limits or quotas."""


class LLMInvalidOutput(LLMError):
    """Raised when an LLM returns unparseable, malformed, or schema-violating output."""


class LLMUnavailable(LLMError):
    """Raised when the LLM service or network connection is unavailable."""


@dataclass(frozen=True)
class TokenUsage:
    """Token consumption accounting for an LLM interaction."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens processed."""
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class StructuredCompletionResponse:
    """Result of a structured tool-call completion."""

    tool_name: str
    arguments: dict[str, Any]
    usage: TokenUsage
    raw_content: str | None = None


@dataclass(frozen=True)
class TextCompletionResponse:
    """Result of a plain text completion."""

    content: str
    usage: TokenUsage


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for provider-agnostic LLM interactions."""

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tool_name: str,
        tool_description: str,
        tool_schema: dict[str, Any],
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> StructuredCompletionResponse:
        """Complete structured tool call returning parsed arguments and token usage.

        Args:
            system_prompt: Guiding context and rules for the LLM.
            user_message: User request or query.
            tool_name: Name of the structured tool to invoke.
            tool_description: Explanation of the tool's purpose and usage.
            tool_schema: JSON Schema of expected tool arguments.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            StructuredCompletionResponse with parsed tool arguments and token metrics.

        Raises:
            LLMTimeout: If request times out across retries.
            LLMRateLimit: If provider rate limits persist.
            LLMInvalidOutput: If LLM fails to call tool or returns invalid JSON.
            LLMUnavailable: If network or provider is unreachable.
        """
        ...

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> TextCompletionResponse:
        """Complete plain text response.

        Args:
            system_prompt: Guiding context and rules for the LLM.
            user_message: User request or message.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            TextCompletionResponse with generated text and token metrics.

        Raises:
            LLMTimeout: If request times out across retries.
            LLMRateLimit: If provider rate limits persist.
            LLMUnavailable: If network or provider is unreachable.
        """
        ...


__all__ = [
    "LLMClient",
    "LLMError",
    "LLMInvalidOutput",
    "LLMRateLimit",
    "LLMTimeout",
    "LLMUnavailable",
    "StructuredCompletionResponse",
    "TextCompletionResponse",
    "TokenUsage",
]
