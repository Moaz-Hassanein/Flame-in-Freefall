"""Unit tests for semantic retrieval, hybrid search, and fusion."""

from __future__ import annotations

import pytest

from flame.retrieval.fusion import fuse_retrieval
from flame.retrieval.semantic import SemanticRetriever, build_document_text
from flame.retrieval.store import ExperimentStore
from flame.schemas.query_plan import FilterCondition, FilterOperator, PlanIntent, QueryPlan


@pytest.fixture
def store():
    with ExperimentStore() as s:
        yield s


def test_build_document_text():
    row = {
        "experiment_id": "EXP-01",
        "dataset_family": "ACME",
        "fuel_material": "Methane",
        "material_category": "gas",
        "extinction_outcome": "Extinction",
        "sample_description": "Porous burner",
        "notes": "Spherical laminar flame",
    }
    doc = build_document_text(row)
    assert "EXP-01" in doc
    assert "Methane" in doc
    assert "Spherical laminar flame" in doc


def test_semantic_retriever_hybrid_search(store: ExperimentStore):
    retriever = SemanticRetriever()
    plan = QueryPlan(intent=PlanIntent.QUALITATIVE)

    # Search for water spray cooling
    results = retriever.search_hybrid(
        query_text="water mist fine spray cooling",
        plan=plan,
        limit=5,
    )
    assert len(results) > 0
    # ACME-CFI-03 was fine water spray
    assert "ACME-CFI-03" in results


def test_semantic_retriever_respects_modeled_exclusion(store: ExperimentStore):
    retriever = SemanticRetriever()
    # Plan excluding modeled rows
    plan = QueryPlan(intent=PlanIntent.QUALITATIVE, include_modeled=False)
    results = retriever.search_hybrid(
        query_text="Partial gravity computational model",
        plan=plan,
        limit=10,
    )

    # Fetch rows to verify is_modeled is False
    cur = store.get_cursor()
    cur.execute(
        "SELECT is_modeled FROM experiments WHERE experiment_id IN (SELECT unnest(?))",
        [results],
    )
    for (is_mod,) in cur.fetchall():
        assert not is_mod


def test_fuse_retrieval_qualitative_intent(store: ExperimentStore):
    plan = QueryPlan(intent=PlanIntent.QUALITATIVE)
    fused = fuse_retrieval(
        question="Which experiments used Halon replacement chemical suppression?",
        plan=plan,
        store=store,
    )
    assert len(fused.rows) > 0
    eids = [r["experiment_id"] for r in fused.rows[:5]]
    assert "ACME-CFI-02" in eids or "SLICE-005" in eids


def test_fuse_retrieval_lookup_bypasses_semantic(store: ExperimentStore):
    # Lookup intent should only run structured query
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        filters=[FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="FLEX")],
        limit=5,
    )
    fused = fuse_retrieval(
        question="FLEX experiments",
        plan=plan,
        store=store,
    )
    assert len(fused.rows) == 5
    assert all(r["dataset_family"] == "FLEX" for r in fused.rows)
