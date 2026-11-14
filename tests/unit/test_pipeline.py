"""Unit tests for the end-to-end RAG pipeline orchestration."""

from __future__ import annotations

import pytest

from flame.rag.pipeline import ask
from flame.retrieval.catalog import build_field_catalog
from flame.retrieval.store import ExperimentStore
from flame.schemas.answer import AnswerStatus
from tests.doubles.fake_llm import FakeLLMClient


@pytest.fixture
def store():
    with ExperimentStore() as s:
        yield s


@pytest.fixture
def catalog(store: ExperimentStore):
    cur = store.get_cursor()
    try:
        return build_field_catalog(cur)
    finally:
        cur.close()


def test_ask_out_of_scope_intent(store: ExperimentStore, catalog):
    fake_llm = FakeLLMClient()
    fake_llm.enqueue_structured({"intent": "out_of_scope"})

    response = ask(
        question="What is the speed of sound on Mars?",
        llm_client=fake_llm,
        store=store,
        catalog=catalog,
    )

    assert response.status == AnswerStatus.out_of_scope
    assert response.answer_markdown is not None
    assert "outside the scope" in response.answer_markdown
    assert response.citations == []
    # Generation LLM call was not triggered
    assert len(fake_llm.calls) == 1


def test_ask_insufficient_evidence(store: ExperimentStore, catalog):
    fake_llm = FakeLLMClient()
    # Query looking for a non-existent fuel
    fake_llm.enqueue_structured(
        {
            "intent": "lookup",
            "filters": [{"field": "fuel_material", "op": "eq", "value": "NON_EXISTENT_FUEL_XYZ"}],
            "limit": 10,
        }
    )

    response = ask(
        question="What experiments used NON_EXISTENT_FUEL_XYZ?",
        llm_client=fake_llm,
        store=store,
        catalog=catalog,
    )

    assert response.status == AnswerStatus.insufficient_evidence
    assert response.citations == []
    assert any("No matching" in lim for lim in response.limitations)
    # Generation LLM call was bypassed because results were empty
    assert len(fake_llm.calls) == 1


def test_ask_happy_path_lookup(store: ExperimentStore, catalog):
    fake_llm = FakeLLMClient()
    # Plan: lookup PMMA experiments in BASS-II
    fake_llm.enqueue_structured(
        {
            "intent": "lookup",
            "filters": [
                {"field": "dataset_family", "op": "eq", "value": "BASS-II"},
                {"field": "fuel_material", "op": "eq", "value": "PMMA (Acrylic)"},
            ],
            "limit": 5,
        }
    )
    # Generator response
    fake_llm.enqueue_structured(
        {
            "answer_text": "BASS-II evaluated PMMA in microgravity across multiple runs.",
            "cited_ids": [],
            "limitations": [],
        }
    )

    response = ask(
        question="Show PMMA runs in BASS-II",
        llm_client=fake_llm,
        store=store,
        catalog=catalog,
    )

    assert response.status == AnswerStatus.answered
    assert response.answer_markdown is not None
    assert len(response.evidence) > 0
    assert "plan_s" in response.timings
    assert "retrieval_s" in response.timings
    assert "generate_s" in response.timings


def test_ask_with_citations_and_guardrail_verification(store: ExperimentStore, catalog):
    fake_llm = FakeLLMClient()
    fake_llm.enqueue_structured(
        {
            "intent": "lookup",
            "filters": [
                {"field": "dataset_family", "op": "eq", "value": "FLEX"},
            ],
            "limit": 2,
        }
    )

    # Let's peek at actual IDs
    cur = store.get_cursor()
    cur.execute("SELECT experiment_id FROM experiments WHERE dataset_family = 'FLEX' LIMIT 2")
    real_ids = [r[0] for r in cur.fetchall()]
    cur.close()

    real_id = real_ids[0]
    fake_id = "FAKE_EXP_999"

    # Generator attempts to cite real_id AND fake_id
    fake_llm.enqueue_structured(
        {
            "answer_text": f"Found experiments [{real_id}] and [{fake_id}].",
            "cited_ids": [real_id, fake_id],
            "limitations": [],
        }
    )
    # On guardrail failure, it will retry once
    fake_llm.enqueue_structured(
        {
            "answer_text": f"Corrected: found experiment [{real_id}].",
            "cited_ids": [real_id],
            "limitations": [],
        }
    )

    response = ask(
        question="Tell me about FLEX tests",
        llm_client=fake_llm,
        store=store,
        catalog=catalog,
    )

    assert response.status == AnswerStatus.answered
    cited_ids = [c.experiment_id for c in response.citations]
    assert real_id in cited_ids
    assert fake_id not in cited_ids
    assert f"[{fake_id}]" not in (response.answer_markdown or "")


def test_ask_generation_failure_returns_error_status(store: ExperimentStore, catalog):
    from flame.llm.client import LLMTimeout

    fake_llm = FakeLLMClient()
    fake_llm.enqueue_structured(
        {
            "intent": "lookup",
            "filters": [
                {"field": "dataset_family", "op": "eq", "value": "FLEX"},
            ],
            "limit": 2,
        }
    )
    # Generator times out
    fake_llm.enqueue_structured(LLMTimeout("Provider timed out"))

    response = ask(
        question="Tell me about FLEX tests",
        llm_client=fake_llm,
        store=store,
        catalog=catalog,
    )

    assert response.status == AnswerStatus.error
    assert any("timed out" in lim for lim in response.limitations)
