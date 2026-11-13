"""Anthropic LLM client implementation using the official Anthropic SDK."""

from __future__ import annotations

import logging
import time
from typing import Any

import anthropic

from flame.config import Settings, get_settings
from flame.llm.client import (
    LLMClient,
    LLMInvalidOutput,
    LLMRateLimit,
    LLMTimeout,
    LLMUnavailable,
    StructuredCompletionResponse,
    TextCompletionResponse,
    TokenUsage,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 30.0
DEFAULT_MAX_RETRIES = 3
INITIAL_BACKOFF_S = 1.0
BACKOFF_FACTOR = 2.0


class AnthropicClient(LLMClient):
    """Anthropic API client implementing the LLMClient protocol."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.settings = settings or get_settings()
        api_key_secret = self.settings.llm_api_key
        if not api_key_secret:
            raise ValueError(
                "FLAME_LLM_API_KEY is required to initialize AnthropicClient. "
                "Provide it via environment variable or .env."
            )
        self.api_key = api_key_secret.get_secret_value()

        # Model name comes ONLY from config or explicit argument, never hardcoded default
        configured_model = model or self.settings.llm_model
        if not configured_model:
            raise ValueError(
                "FLAME_LLM_MODEL is required to initialize AnthropicClient. "
                "Provide it via environment variable or .env."
            )
        self.model = configured_model
        self.timeout = timeout
        self.max_retries = max_retries

        # Initialize official Anthropic SDK client
        self._client = anthropic.Anthropic(
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=0,  # We manage bounded retries with custom backoff and typed mapping
        )

    def _execute_with_retry(self, fn: Any) -> Any:
        """Execute callable with bounded exponential backoff for transient errors."""
        backoff = INITIAL_BACKOFF_S
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                return fn()
            except anthropic.APITimeoutError as err:
                last_error = err
                logger.warning(
                    "Anthropic API timeout on attempt %d/%d: %s",
                    attempt,
                    self.max_retries,
                    err,
                )
                if attempt == self.max_retries:
                    raise LLMTimeout(
                        f"Anthropic request timed out after {self.max_retries} attempts: {err}"
                    ) from err
            except anthropic.RateLimitError as err:
                last_error = err
                logger.warning(
                    "Anthropic rate limit encountered on attempt %d/%d: %s",
                    attempt,
                    self.max_retries,
                    err,
                )
                if attempt == self.max_retries:
                    raise LLMRateLimit(f"Anthropic rate limit exceeded: {err}") from err
            except (
                anthropic.APIConnectionError,
                anthropic.InternalServerError,
                anthropic.OverloadedError,
                anthropic.ServiceUnavailableError,
            ) as err:
                last_error = err
                logger.warning(
                    "Transient Anthropic error on attempt %d/%d: %s",
                    attempt,
                    self.max_retries,
                    err,
                )
                if attempt == self.max_retries:
                    raise LLMUnavailable(
                        f"Anthropic service unavailable after {self.max_retries} attempts: {err}"
                    ) from err
            except anthropic.APIStatusError as err:
                # Non-transient HTTP errors (e.g. 400 Bad Request, 401 Unauthorized, 403 Forbidden)
                raise LLMUnavailable(
                    f"Anthropic API status error ({err.status_code}): {err.message}"
                ) from err
            except Exception as err:
                raise LLMUnavailable(
                    f"Unexpected error communicating with Anthropic: {err}"
                ) from err

            time.sleep(backoff)
            backoff *= BACKOFF_FACTOR

        if last_error:
            raise LLMUnavailable(
                f"Anthropic call failed after {self.max_retries} attempts: {last_error}"
            ) from last_error
        raise LLMUnavailable("Anthropic call failed with unknown error.")

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
        """Call Anthropic Messages API with forced tool choice."""
        tool_definition: anthropic.types.ToolParam = {
            "name": tool_name,
            "description": tool_description,
            "input_schema": tool_schema,
        }
        tool_choice: anthropic.types.ToolChoiceToolParam = {
            "type": "tool",
            "name": tool_name,
        }
        messages: list[anthropic.types.MessageParam] = [{"role": "user", "content": user_message}]

        def _call() -> Any:
            return self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
                tools=[tool_definition],
                tool_choice=tool_choice,
            )

        response = self._execute_with_retry(_call)

        # Parse token usage
        usage = TokenUsage(
            input_tokens=getattr(response.usage, "input_tokens", 0),
            output_tokens=getattr(response.usage, "output_tokens", 0),
        )

        # Locate tool use content block
        raw_text_parts: list[str] = []
        tool_arguments: dict[str, Any] | None = None

        for block in response.content:
            if getattr(block, "type", None) == "text":
                raw_text_parts.append(block.text)
            elif getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                input_data = block.input
                if isinstance(input_data, dict):
                    tool_arguments = input_data
                else:
                    raise LLMInvalidOutput(
                        f"Anthropic returned non-dictionary tool arguments for "
                        f"'{tool_name}': {input_data!r}"
                    )

        if tool_arguments is None:
            raise LLMInvalidOutput(
                f"Anthropic response did not contain required tool_use block "
                f"for tool '{tool_name}'."
            )

        raw_text = "\n".join(raw_text_parts) if raw_text_parts else None

        return StructuredCompletionResponse(
            tool_name=tool_name,
            arguments=tool_arguments,
            usage=usage,
            raw_content=raw_text,
        )

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> TextCompletionResponse:
        """Call Anthropic Messages API for plain text completion."""
        messages: list[anthropic.types.MessageParam] = [{"role": "user", "content": user_message}]

        def _call() -> Any:
            return self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )

        response = self._execute_with_retry(_call)

        usage = TokenUsage(
            input_tokens=getattr(response.usage, "input_tokens", 0),
            output_tokens=getattr(response.usage, "output_tokens", 0),
        )

        text_content = ""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_content += block.text

        return TextCompletionResponse(
            content=text_content,
            usage=usage,
        )


__all__ = ["AnthropicClient"]
