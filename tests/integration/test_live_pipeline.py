"""Live integration test for the ask() pipeline.

Marked with pytest.mark.live and skipped unless FLAME_LLM_API_KEY or
ANTHROPIC_API_KEY is present in the environment.
"""

from __future__ import annotations

import pytest

from flame.config import get_settings
from flame.llm.anthropic_client import AnthropicClient
from flame.rag.pipeline import ask
from flame.retrieval.store import ExperimentStore
from flame.schemas.answer import AnswerStatus


@pytest.fixture
def api_key() -> str:
    cfg = get_settings()
    key = cfg.get_llm_api_key()
    if not key:
        pytest.skip("FLAME_LLM_API_KEY / ANTHROPIC_API_KEY not configured")
    return key


@pytest.mark.live
def test_live_ask_lookup(api_key: str):
    cfg = get_settings()
    llm = AnthropicClient(api_key=api_key, model=cfg.llm_model)

    with ExperimentStore() as store:
        resp = ask(
            question="Find experiments using PMMA in BASS-II with oxygen percentage >= 20",
            llm_client=llm,
            store=store,
            catalog=store.catalog,
        )

    assert resp.status == AnswerStatus.answered
    assert resp.answer_markdown is not None
    assert len(resp.citations) > 0
    # Guardrail check: every cited id must be in evidence
    evidence_ids = {row["experiment_id"] for row in resp.evidence}
    for c in resp.citations:
        assert c.experiment_id in evidence_ids


@pytest.mark.live
def test_live_ask_out_of_scope(api_key: str):
    cfg = get_settings()
    llm = AnthropicClient(api_key=api_key, model=cfg.llm_model)

    with ExperimentStore() as store:
        resp = ask(
            question="What is the boiling point of liquid water on Jupiter?",
            llm_client=llm,
            store=store,
            catalog=store.catalog,
        )

    assert resp.status == AnswerStatus.out_of_scope
    assert resp.citations == []
