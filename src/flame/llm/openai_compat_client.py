"""OpenAI-compatible LLM client (Ollama, LM Studio, llama.cpp, vLLM)."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

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

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_TIMEOUT_S = 180.0  # local models can be slow on CPU
DEFAULT_MAX_RETRIES = 4
INITIAL_BACKOFF_S = 1.0
BACKOFF_FACTOR = 2.0


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort: parse a JSON object from model text (handles ``` fences)."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    for candidate in (cleaned, cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]):
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, dict):
            return value
    return None


def _fix_null_lists(args: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Turn null into [] for properties the schema declares as arrays."""
    props = schema.get("properties") or {}
    for key, spec in props.items():
        if key in args and args[key] is None and isinstance(spec, dict):
            kind = spec.get("type")
            if kind == "array" or (isinstance(kind, list) and "array" in kind):
                args[key] = []
    return args


def _normalize_arguments(
    args: dict[str, Any] | None, tool_name: str, schema: dict[str, Any]
) -> dict[str, Any] | None:
    """Unwrap {"name": tool, "arguments": {...}} and repair null list fields."""
    if not isinstance(args, dict):
        return args
    inner = args.get("arguments")
    if args.get("name") == tool_name and inner is not None:
        if isinstance(inner, str):
            inner = _extract_json_object(inner)
        if isinstance(inner, dict):
            args = inner
    return _fix_null_lists(args, schema)


class OpenAICompatClient(LLMClient):
    """Client for any server exposing POST {base_url}/chat/completions."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.settings = settings or get_settings()
        configured_model = model or self.settings.llm_model
        if not configured_model:
            raise ValueError("FLAME_LLM_MODEL is required to initialize OpenAICompatClient.")
        self.model = configured_model
        self.base_url = (
            base_url or getattr(self.settings, "llm_base_url", None) or DEFAULT_BASE_URL
        ).rstrip("/")
        secret = self.settings.llm_api_key
        api_key = secret.get_secret_value() if secret else "local"
        self.timeout = (
            timeout
            if timeout is not None
            else (getattr(self.settings, "llm_timeout_s", None) or DEFAULT_TIMEOUT_S)
        )
        self.max_retries = max_retries
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        backoff = INITIAL_BACKOFF_S
        for attempt in range(1, self.max_retries + 1):
            last = attempt == self.max_retries
            try:
                resp = self._http.post("/chat/completions", json=payload)
            except httpx.TimeoutException as err:
                logger.warning("LLM timeout %d/%d: %s", attempt, self.max_retries, err)
                if last:
                    raise LLMTimeout(
                        f"Local LLM timed out after {self.max_retries} attempts."
                    ) from err
            except httpx.TransportError as err:
                logger.warning("LLM connection error %d/%d: %s", attempt, self.max_retries, err)
                if last:
                    raise LLMUnavailable(
                        f"Cannot reach LLM server at {self.base_url} (is Ollama running?): {err}"
                    ) from err
            else:
                if resp.status_code == 429:
                    if last:
                        raise LLMRateLimit("LLM server rate limit exceeded.")
                    try:
                        retry_after = float(resp.headers.get("retry-after", 0) or 0)
                    except ValueError:
                        retry_after = 0.0
                    backoff = max(backoff, min(retry_after, 20.0))
                elif resp.status_code >= 500:
                    if last:
                        raise LLMUnavailable(
                            f"LLM server error {resp.status_code}: {resp.text[:300]}"
                        )
                elif resp.status_code >= 400:
                    salvaged = self._salvage_failed_generation(resp)
                    if salvaged is not None:
                        return salvaged
                    raise LLMUnavailable(
                        f"LLM API status error ({resp.status_code}): {resp.text[:300]}"
                    )
                else:
                    try:
                        body = resp.json()
                    except ValueError as err:
                        raise LLMInvalidOutput("LLM server returned non-JSON response.") from err
                    if not isinstance(body, dict):
                        raise LLMInvalidOutput("LLM server returned an unexpected response shape.")
                    return body
            time.sleep(backoff)
            backoff *= BACKOFF_FACTOR
        raise LLMUnavailable("LLM call failed with unknown error.")

    @staticmethod
    def _salvage_failed_generation(resp: httpx.Response) -> dict[str, Any] | None:
        """Recover the model output from a tool_use_failed 400 error, if present."""
        if resp.status_code != 400:
            return None
        try:
            err = resp.json().get("error") or {}
        except (ValueError, AttributeError):
            return None
        fg = err.get("failed_generation")
        if err.get("code") != "tool_use_failed" or not isinstance(fg, str) or not fg.strip():
            return None
        logger.info("Salvaging output from a failed tool-call generation.")
        return {"choices": [{"message": {"content": fg}}], "usage": {}}

    @staticmethod
    def _usage(body: dict[str, Any]) -> TokenUsage:
        u = body.get("usage") or {}
        return TokenUsage(
            input_tokens=int(u.get("prompt_tokens", 0) or 0),
            output_tokens=int(u.get("completion_tokens", 0) or 0),
        )

    @staticmethod
    def _message(body: dict[str, Any]) -> dict[str, Any]:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise LLMInvalidOutput("LLM response contained no choices.")
        msg = choices[0].get("message")
        if not isinstance(msg, dict):
            raise LLMInvalidOutput("LLM response contained no message.")
        return msg

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
        required = [k for k in (tool_schema.get("required") or []) if isinstance(k, str)]

        def _ok(args: dict[str, Any] | None) -> bool:
            return args is not None and all(k in args for k in required)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": tool_description,
                        "parameters": tool_schema,
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": tool_name}},
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        body = self._post(payload)
        usage = self._usage(body)
        msg = self._message(body)
        content = msg.get("content") if isinstance(msg.get("content"), str) else None

        arguments: dict[str, Any] | None = None
        for call in msg.get("tool_calls") or []:
            fn = call.get("function") if isinstance(call, dict) else None
            if not isinstance(fn, dict) or fn.get("name") != tool_name:
                continue
            raw_args = fn.get("arguments")
            if isinstance(raw_args, dict):
                arguments = raw_args
            elif isinstance(raw_args, str):
                arguments = _extract_json_object(raw_args)
            break

        if arguments is None and content:
            # Small models often answer with JSON in plain text instead of a tool call.
            arguments = _extract_json_object(content)

        arguments = _normalize_arguments(arguments, tool_name, tool_schema)
        if not _ok(arguments):
            # Small models often ignore the tool schema. Retry once with schema-constrained
            # JSON output (response_format), which the server enforces during decoding.
            logger.info("Tool-call output missing required fields; retrying with JSON schema.")
            retry_body = self._post(
                {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt
                            + "\n\nRespond with a single JSON object that matches the required "
                            "schema exactly. No prose.",
                        },
                        {"role": "user", "content": user_message},
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {"name": tool_name, "schema": tool_schema, "strict": True},
                    },
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": False,
                }
            )
            extra = self._usage(retry_body)
            usage = TokenUsage(
                input_tokens=usage.input_tokens + extra.input_tokens,
                output_tokens=usage.output_tokens + extra.output_tokens,
            )
            retry_content = self._message(retry_body).get("content")
            if isinstance(retry_content, str):
                candidate = _extract_json_object(retry_content)
                if _ok(candidate) or arguments is None:
                    arguments = candidate
                    content = retry_content

        if arguments is None:
            raise LLMInvalidOutput(
                f"LLM did not return arguments for tool '{tool_name}' "
                f"(model={self.model}). Try a larger or tool-capable model."
            )
        return StructuredCompletionResponse(
            tool_name=tool_name, arguments=arguments, usage=usage, raw_content=content
        )

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> TextCompletionResponse:
        body = self._post(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            }
        )
        msg = self._message(body)
        text = msg.get("content")
        return TextCompletionResponse(
            content=text if isinstance(text, str) else "", usage=self._usage(body)
        )


__all__ = ["OpenAICompatClient"]
