"""Unit tests for LLMClient protocol, exceptions, and Anthropic implementation retry logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from flame.config import Settings
from flame.llm.anthropic_client import AnthropicClient
from flame.llm.client import (
    LLMInvalidOutput,
    LLMRateLimit,
    LLMTimeout,
    LLMUnavailable,
    TokenUsage,
)
from tests.doubles.fake_llm import FakeLLMClient


def test_token_usage_total() -> None:
    usage = TokenUsage(input_tokens=150, output_tokens=75)
    assert usage.input_tokens == 150
    assert usage.output_tokens == 75
    assert usage.total_tokens == 225


def test_fake_llm_client_structured_and_text() -> None:
    client = FakeLLMClient()
    client.enqueue_structured({"intent": "lookup", "filters": []})
    client.enqueue_text("Hello combustion!")

    res = client.complete_structured(
        system_prompt="sys",
        user_message="Find methanol tests",
        tool_name="QueryPlan",
        tool_description="plan",
        tool_schema={},
    )
    assert res.tool_name == "QueryPlan"
    assert res.arguments == {"intent": "lookup", "filters": []}
    assert res.usage.total_tokens == 40

    txt = client.complete_text(system_prompt="sys", user_message="ping")
    assert txt.content == "Hello combustion!"
    assert txt.usage.total_tokens == 30
    assert len(client.calls) == 2


def test_fake_llm_client_raises_enqueued_exception() -> None:
    client = FakeLLMClient()
    client.enqueue_structured(LLMRateLimit("Quota exceeded"))

    with pytest.raises(LLMRateLimit, match="Quota exceeded"):
        client.complete_structured(
            system_prompt="sys",
            user_message="msg",
            tool_name="tool",
            tool_description="desc",
            tool_schema={},
        )


def test_anthropic_client_requires_api_key_and_model() -> None:
    empty_settings = Settings()
    with pytest.raises(ValueError, match="FLAME_LLM_API_KEY is required"):
        AnthropicClient(empty_settings)

    settings_with_key = Settings(llm_api_key="test-key", llm_model=None)
    with pytest.raises(ValueError, match="FLAME_LLM_MODEL is required"):
        AnthropicClient(settings_with_key)


@patch("anthropic.Anthropic")
def test_anthropic_client_timeout_retry_and_mapping(mock_sdk_cls: MagicMock) -> None:
    settings = Settings(llm_api_key="test-key", llm_model="test-model")
    client = AnthropicClient(settings=settings, max_retries=2)

    # Configure mock to raise APITimeoutError
    mock_messages = MagicMock()
    mock_messages.create.side_effect = anthropic.APITimeoutError(request=MagicMock())
    client._client.messages = mock_messages

    with patch("time.sleep") as mock_sleep:
        with pytest.raises(LLMTimeout, match="timed out after 2 attempts"):
            client.complete_text(system_prompt="sys", user_message="ping")
        assert mock_sleep.call_count == 1
        assert mock_messages.create.call_count == 2


@patch("anthropic.Anthropic")
def test_anthropic_client_rate_limit_mapping(mock_sdk_cls: MagicMock) -> None:
    settings = Settings(llm_api_key="test-key", llm_model="test-model")
    client = AnthropicClient(settings=settings, max_retries=1)

    mock_response = MagicMock(status_code=429, headers={})
    mock_messages = MagicMock()
    mock_messages.create.side_effect = anthropic.RateLimitError(
        message="rate limit", response=mock_response, body={}
    )
    client._client.messages = mock_messages

    with pytest.raises(LLMRateLimit, match="rate limit exceeded"):
        client.complete_text(system_prompt="sys", user_message="ping")


@patch("anthropic.Anthropic")
def test_anthropic_client_unavailable_mapping(mock_sdk_cls: MagicMock) -> None:
    settings = Settings(llm_api_key="test-key", llm_model="test-model")
    client = AnthropicClient(settings=settings, max_retries=1)

    mock_messages = MagicMock()
    mock_messages.create.side_effect = anthropic.APIConnectionError(request=MagicMock())
    client._client.messages = mock_messages

    with pytest.raises(LLMUnavailable, match="unavailable"):
        client.complete_text(system_prompt="sys", user_message="ping")


@patch("anthropic.Anthropic")
def test_anthropic_client_invalid_output_handling(mock_sdk_cls: MagicMock) -> None:
    settings = Settings(llm_api_key="test-key", llm_model="test-model")
    client = AnthropicClient(settings=settings, max_retries=1)

    # Return text block instead of tool_use block
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "I cannot call tools."

    mock_res = MagicMock()
    mock_res.content = [text_block]
    mock_res.usage.input_tokens = 5
    mock_res.usage.output_tokens = 5

    mock_messages = MagicMock()
    mock_messages.create.return_value = mock_res
    client._client.messages = mock_messages

    with pytest.raises(LLMInvalidOutput, match="did not contain required tool_use block"):
        client.complete_structured(
            system_prompt="sys",
            user_message="query",
            tool_name="QueryPlan",
            tool_description="desc",
            tool_schema={},
        )
