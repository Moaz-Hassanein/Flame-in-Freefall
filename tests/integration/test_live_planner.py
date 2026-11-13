"""Live tests for Anthropic planner execution.

These tests communicate with the real Anthropic API when FLAME_LLM_API_KEY
and FLAME_LLM_MODEL are configured. They are marked with 'live' and are skipped
by default unless run with `pytest -m live` or when keys are present.
"""

from __future__ import annotations

import os

import pytest

from flame.config import get_settings
from flame.llm.anthropic_client import AnthropicClient
from flame.rag.planner import QueryPlanner
from flame.schemas.query_plan import PlanIntent, QueryPlan

live_marker = pytest.mark.skipif(
    not os.getenv("FLAME_LLM_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="Live tests require FLAME_LLM_API_KEY or ANTHROPIC_API_KEY to be set.",
)


@pytest.mark.live
@live_marker
def test_live_anthropic_planner_basic_query() -> None:
    settings = get_settings()
    # Support ANTHROPIC_API_KEY fallback for convenience in live runs
    if not settings.llm_api_key and os.getenv("ANTHROPIC_API_KEY"):
        os.environ["FLAME_LLM_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]
    if not settings.llm_model:
        os.environ["FLAME_LLM_MODEL"] = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    client = AnthropicClient()
    planner = QueryPlanner(llm_client=client)

    result = planner.plan("Which experiments in the FLEX dataset family tested Methanol fuel?")

    assert isinstance(result.plan, QueryPlan)
    assert result.plan.intent == PlanIntent.LOOKUP
    field_names = [f.field for f in result.plan.filters]
    assert "dataset_family" in field_names or "fuel_material" in field_names
