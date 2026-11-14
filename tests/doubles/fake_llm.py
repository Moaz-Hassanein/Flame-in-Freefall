"""Test double LLM client for deterministic unit testing of retry, exceptions, and tools."""

from __future__ import annotations

from typing import Any

from flame.llm.client import (
    LLMClient,
    StructuredCompletionResponse,
    TextCompletionResponse,
    TokenUsage,
)


class FakeLLMClient(LLMClient):
    """Test double LLM client that can enqueue mock responses or exceptions."""

    def __init__(self) -> None:
        self.structured_queue: list[dict[str, Any] | Exception] = []
        self.text_queue: list[str | Exception] = []
        self.calls: list[dict[str, Any]] = []

    def enqueue_structured(self, response_or_err: dict[str, Any] | Exception) -> None:
        """Enqueue structured tool-call response arguments or an exception."""
        self.structured_queue.append(response_or_err)

    def enqueue_text(self, text_or_err: str | Exception) -> None:
        """Enqueue plain text response or an exception."""
        self.text_queue.append(text_or_err)

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
        self.calls.append(
            {
                "type": "structured",
                "system_prompt": system_prompt,
                "user_message": user_message,
                "tool_name": tool_name,
                "tool_description": tool_description,
                "tool_schema": tool_schema,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )

        if not self.structured_queue:
            # Default empty plan if queue is exhausted
            return StructuredCompletionResponse(
                tool_name=tool_name,
                arguments={"intent": "lookup"},
                usage=TokenUsage(input_tokens=10, output_tokens=10),
            )

        item = self.structured_queue.pop(0)
        if isinstance(item, Exception):
            raise item

        return StructuredCompletionResponse(
            tool_name=tool_name,
            arguments=item,
            usage=TokenUsage(input_tokens=15, output_tokens=25),
        )

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> TextCompletionResponse:
        self.calls.append(
            {
                "type": "text",
                "system_prompt": system_prompt,
                "user_message": user_message,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )

        if not self.text_queue:
            return TextCompletionResponse(
                content="Mock default response",
                usage=TokenUsage(input_tokens=10, output_tokens=10),
            )

        item = self.text_queue.pop(0)
        if isinstance(item, Exception):
            raise item

        return TextCompletionResponse(
            content=item,
            usage=TokenUsage(input_tokens=10, output_tokens=20),
        )


__all__ = ["FakeLLMClient"]
