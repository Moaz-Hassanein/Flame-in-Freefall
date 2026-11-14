"""Unit tests for QueryPlanner: prompt, retry, and normalization."""

from __future__ import annotations

import pytest

from flame.llm.client import LLMUnavailable
from flame.rag.planner import (
    PlannerResult,
    QueryPlanner,
    format_catalog_summary,
    load_planner_system_prompt,
)
from flame.retrieval.catalog import FieldCatalog, FieldInfo
from flame.schemas.query_plan import (
    FilterOperator,
    PlanIntent,
)
from tests.doubles.fake_llm import FakeLLMClient


@pytest.fixture
def mock_catalog() -> FieldCatalog:
    return FieldCatalog(
        fields={
            "experiment_id": FieldInfo(
                name="experiment_id",
                data_type="string",
                is_canonical=True,
                is_enrichment=False,
                is_numeric=False,
                is_categorical=False,
            ),
            "fuel_material": FieldInfo(
                name="fuel_material",
                data_type="string",
                is_canonical=True,
                is_enrichment=False,
                is_numeric=False,
                is_categorical=True,
                allowed_values=["Methanol", "Heptane", "PMMA (Acrylic)", "Ethanol Droplet"],
            ),
            "dataset_family": FieldInfo(
                name="dataset_family",
                data_type="string",
                is_canonical=True,
                is_enrichment=False,
                is_numeric=False,
                is_categorical=True,
                allowed_values=["FLEX", "BASS-II", "GRC Drop Tower", "SOFIE"],
            ),
            "burning_rate_mms": FieldInfo(
                name="burning_rate_mms",
                data_type="float",
                unit="mm/s",
                is_canonical=True,
                is_enrichment=False,
                is_numeric=True,
                is_categorical=False,
                min_value=0.05,
                max_value=2.45,
            ),
            "is_modeled": FieldInfo(
                name="is_modeled",
                data_type="boolean",
                is_canonical=False,
                is_enrichment=True,
                is_numeric=False,
                is_categorical=False,
            ),
        }
    )


def test_load_planner_system_prompt() -> None:
    prompt = load_planner_system_prompt()
    assert "{{catalog_summary}}" in prompt
    assert "MODELED ROW POLICY" in prompt


def test_format_catalog_summary(mock_catalog: FieldCatalog) -> None:
    summary = format_catalog_summary(mock_catalog)
    assert "- `fuel_material` (string)" in summary
    assert "- `burning_rate_mms` (float) [mm/s]" in summary
    assert "Methanol" in summary


def test_planner_successful_plan(mock_catalog: FieldCatalog) -> None:
    fake_llm = FakeLLMClient()
    fake_llm.enqueue_structured(
        {
            "intent": "lookup",
            "filters": [
                {"field": "fuel_material", "op": "eq", "value": "Methanol"},
            ],
            "select_fields": ["experiment_id"],
            "limit": 100,
        }
    )

    planner = QueryPlanner(llm_client=fake_llm, catalog=mock_catalog)
    res = planner.plan("Which experiments used Methanol?")

    assert isinstance(res, PlannerResult)
    assert res.plan.intent == PlanIntent.LOOKUP
    assert len(res.plan.filters) == 1
    assert res.plan.filters[0].field == "fuel_material"
    assert res.plan.filters[0].value == "Methanol"
    assert not res.clarification_needed


def test_planner_validation_retry_and_recovery(mock_catalog: FieldCatalog) -> None:
    fake_llm = FakeLLMClient()
    # 1st attempt: invalid operator 'equals'
    fake_llm.enqueue_structured(
        {
            "intent": "lookup",
            "filters": [
                {"field": "fuel_material", "op": "equals", "value": "Methanol"},
            ],
        }
    )
    # 2nd attempt (retry with error feedback): valid operator 'eq'
    fake_llm.enqueue_structured(
        {
            "intent": "lookup",
            "filters": [
                {"field": "fuel_material", "op": "eq", "value": "Methanol"},
            ],
        }
    )

    planner = QueryPlanner(llm_client=fake_llm, catalog=mock_catalog)
    res = planner.plan("Find methanol")

    assert res.plan.intent == PlanIntent.LOOKUP
    assert res.plan.filters[0].op == FilterOperator.EQ
    assert len(fake_llm.calls) == 2
    # Verify the second call received the validation error message
    assert "Your previous QueryPlan was invalid" in fake_llm.calls[1]["user_message"]


def test_planner_exhausted_retry_emits_out_of_scope(mock_catalog: FieldCatalog) -> None:
    fake_llm = FakeLLMClient()
    # Both attempts invalid
    fake_llm.enqueue_structured({"intent": "invalid_intent"})
    fake_llm.enqueue_structured({"intent": "invalid_again"})

    planner = QueryPlanner(llm_client=fake_llm, catalog=mock_catalog)
    res = planner.plan("Do something invalid")

    assert res.plan.intent == PlanIntent.OUT_OF_SCOPE
    assert res.clarification_needed
    assert "Validation error on retry" in str(res.clarification_message)


def test_planner_llm_exception_emits_out_of_scope(mock_catalog: FieldCatalog) -> None:
    fake_llm = FakeLLMClient()
    fake_llm.enqueue_structured(LLMUnavailable("Network down"))

    planner = QueryPlanner(llm_client=fake_llm, catalog=mock_catalog)
    res = planner.plan("Find tests")

    assert res.plan.intent == PlanIntent.OUT_OF_SCOPE
    assert res.clarification_needed
    assert "LLM interaction failed" in str(res.clarification_message)


def test_planner_fuzzy_normalization_and_ambiguity(mock_catalog: FieldCatalog) -> None:
    fake_llm = FakeLLMClient()
    # User's plan contains 'pmma' (case match to PMMA (Acrylic))
    fake_llm.enqueue_structured(
        {
            "intent": "lookup",
            "filters": [
                {"field": "fuel_material", "op": "eq", "value": "pmma"},
            ],
        }
    )

    planner = QueryPlanner(llm_client=fake_llm, catalog=mock_catalog)
    res = planner.plan("Which tests used pmma?")

    assert res.plan.filters[0].value == "PMMA (Acrylic)"
    assert any("PMMA (Acrylic)" in note for note in res.normalization_notes)
