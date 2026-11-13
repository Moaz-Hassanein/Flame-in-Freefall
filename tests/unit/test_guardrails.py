"""Unit tests for the deterministic guardrails module."""

from __future__ import annotations

from flame.rag.guardrails import (
    GuardrailResult,
    _check_cross_family_caveat,
    _check_modeled_disclosure,
    _check_numeric_grounding,
    _remove_invalid_citations,
    run_guardrails,
)
from flame.retrieval.catalog import FieldCatalog, FieldInfo
from flame.retrieval.structured import AggregateResult
from flame.schemas.query_plan import (
    AggregateFunction,
    AggregateSpec,
    FilterCondition,
    FilterOperator,
    PlanIntent,
    QueryPlan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_catalog() -> FieldCatalog:
    """Return a minimal FieldCatalog for testing."""
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
            "burning_rate_mms": FieldInfo(
                name="burning_rate_mms",
                data_type="float",
                is_canonical=True,
                is_enrichment=False,
                is_numeric=True,
                is_categorical=False,
            ),
        }
    )


def _make_plan(
    intent: PlanIntent = PlanIntent.LOOKUP,
    filters: list[FilterCondition] | None = None,
    aggregates: list[AggregateSpec] | None = None,
    include_modeled: bool = False,
) -> QueryPlan:
    return QueryPlan(
        intent=intent,
        filters=filters or [],
        aggregates=aggregates or [],
        include_modeled=include_modeled,
    )


def _make_evidence_rows(n: int = 2, modeled: bool = False) -> list[dict]:
    return [
        {
            "experiment_id": f"EXP-{i:03d}",
            "is_modeled": modeled,
            "oxygen_pct": 21.0 + i,
            "burning_rate_mms": 1.5 + i * 0.1,
            "dataset_family": "FLEX",
        }
        for i in range(1, n + 1)
    ]


def _make_aggregate(
    fn: str = "mean",
    field: str = "burning_rate_mms",
    value: float | None = 1.6,
    n_used: int = 10,
    n_null: int = 0,
    n_quar: int = 0,
    group_key: dict | None = None,
) -> AggregateResult:
    return AggregateResult(
        fn=fn,
        field=field,
        value=value,
        n_used=n_used,
        n_null_excluded=n_null,
        n_quarantined_excluded=n_quar,
        group_key=group_key,
    )


# ---------------------------------------------------------------------------
# 1. Citation validity
# ---------------------------------------------------------------------------

def test_remove_invalid_citations_cleans_text_and_list():
    text = "Experiments [EXP-001] and [FAKE-999] were tested."
    cited = ["EXP-001", "FAKE-999"]
    valid = {"EXP-001"}

    cleaned_text, cleaned_list, warnings = _remove_invalid_citations(text, cited, valid)

    assert "[FAKE-999]" not in cleaned_text
    assert "[EXP-001]" in cleaned_text
    assert "FAKE-999" not in cleaned_list
    assert "EXP-001" in cleaned_list
    assert any("FAKE-999" in w for w in warnings)


def test_remove_invalid_citations_all_valid_no_change():
    text = "Only [EXP-001] was used."
    cited = ["EXP-001"]
    valid = {"EXP-001"}

    cleaned_text, cleaned_list, warnings = _remove_invalid_citations(text, cited, valid)

    assert cleaned_text == text
    assert cleaned_list == cited
    assert warnings == []


# ---------------------------------------------------------------------------
# 2. Numeric grounding
# ---------------------------------------------------------------------------

def test_numeric_grounding_matched_values_no_warnings():
    rows = [{"experiment_id": "EXP-001", "oxygen_pct": 21.0}]
    aggs = [_make_aggregate(value=21.0)]

    warnings = _check_numeric_grounding("Oxygen was 21.0 percent.", rows, aggs)
    assert warnings == []


def test_numeric_grounding_unmatched_value_warns():
    rows = [{"experiment_id": "EXP-001", "oxygen_pct": 21.0}]
    aggs = []

    warnings = _check_numeric_grounding("Oxygen was 99.9 percent.", rows, aggs)
    assert any("99.9" in w for w in warnings)


def test_numeric_grounding_year_integers_excluded():
    rows: list[dict] = []
    aggs: list[AggregateResult] = []

    warnings = _check_numeric_grounding("Test conducted in 2001.", rows, aggs)
    assert warnings == []


def test_numeric_grounding_zero_matched_exactly():
    rows = [{"experiment_id": "EXP-001", "co2_pct": 0.0}]
    aggs: list[AggregateResult] = []

    warnings = _check_numeric_grounding("CO2 was 0.0 percent.", rows, aggs)
    assert warnings == []


# ---------------------------------------------------------------------------
# 3. Modeled row disclosure
# ---------------------------------------------------------------------------

def test_modeled_disclosure_missing_returns_warning():
    rows = [{"experiment_id": "EXP-001", "is_modeled": True}]
    warning = _check_modeled_disclosure("The experiment showed combustion.", rows)
    assert warning is not None
    assert "modeled" in warning.lower()


def test_modeled_disclosure_present_no_warning():
    rows = [{"experiment_id": "EXP-001", "is_modeled": True}]
    warning = _check_modeled_disclosure("This is a modeled result.", rows)
    assert warning is None


def test_modeled_disclosure_no_modeled_rows_no_warning():
    rows = [{"experiment_id": "EXP-001", "is_modeled": False}]
    warning = _check_modeled_disclosure("The result was clear.", rows)
    assert warning is None


# ---------------------------------------------------------------------------
# 4. Exclusion auto-caveats
# ---------------------------------------------------------------------------

def test_exclusion_limitations_null_values():
    from flame.rag.guardrails import _build_exclusion_limitations

    agg = _make_aggregate(n_null=5, n_quar=0)
    lims = _build_exclusion_limitations([agg])

    assert len(lims) == 1
    assert "5 null value(s)" in lims[0]


def test_exclusion_limitations_quarantined_values():
    from flame.rag.guardrails import _build_exclusion_limitations

    agg = _make_aggregate(n_null=0, n_quar=42)
    lims = _build_exclusion_limitations([agg])

    assert any("42 quarantined" in l for l in lims)


def test_exclusion_limitations_no_exclusions_empty():
    from flame.rag.guardrails import _build_exclusion_limitations

    agg = _make_aggregate(n_null=0, n_quar=0)
    lims = _build_exclusion_limitations([agg])
    assert lims == []


# ---------------------------------------------------------------------------
# 5. Cross-family caveat
# ---------------------------------------------------------------------------

def test_cross_family_caveat_no_family_filter_warns():
    plan = _make_plan(
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="burning_rate_mms")],
    )
    agg_flex = _make_aggregate(group_key={"dataset_family": "FLEX"})
    agg_bass = _make_aggregate(group_key={"dataset_family": "BASS-II"})

    result = _check_cross_family_caveat(plan, [agg_flex, agg_bass])
    assert result is not None
    assert "burning_rate_mms" in result


def test_cross_family_caveat_single_family_no_warning():
    plan = _make_plan(
        filters=[FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="FLEX")],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="burning_rate_mms")],
    )
    agg_flex = _make_aggregate(group_key={"dataset_family": "FLEX"})

    result = _check_cross_family_caveat(plan, [agg_flex])
    assert result is None


def test_cross_family_caveat_no_burning_rate_no_warning():
    plan = _make_plan(
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="oxygen_pct")],
    )
    result = _check_cross_family_caveat(plan, [_make_aggregate(field="oxygen_pct")])
    assert result is None


# ---------------------------------------------------------------------------
# 6. run_guardrails integration
# ---------------------------------------------------------------------------

def test_run_guardrails_happy_path_passes():
    rows = _make_evidence_rows(2, modeled=False)
    text = "Experiment [EXP-001] had oxygen 22.0%."
    cited = ["EXP-001"]
    aggs = [_make_aggregate(value=22.0)]
    plan = _make_plan()
    catalog = _make_catalog()

    result = run_guardrails(text, cited, [], rows, aggs, plan, catalog)

    assert result.passed
    assert result.answer_text == text
    assert result.cited_ids == ["EXP-001"]


def test_run_guardrails_invalid_citation_removed():
    rows = _make_evidence_rows(1)
    text = "Experiment [EXP-001] and [GHOST-999] were tested."
    cited = ["EXP-001", "GHOST-999"]
    plan = _make_plan()
    catalog = _make_catalog()

    result = run_guardrails(text, cited, [], rows, [], plan, catalog)

    assert "[GHOST-999]" not in result.answer_text
    assert "GHOST-999" not in result.cited_ids
    assert not result.passed  # citation failure marks as not passed
    assert any("GHOST-999" in f for f in result.failures)


def test_run_guardrails_modeled_disclosure_appended():
    rows = _make_evidence_rows(1, modeled=True)
    text = "Experiment [EXP-001] had oxygen 22.0%."
    cited = ["EXP-001"]
    plan = _make_plan(include_modeled=True)
    catalog = _make_catalog()

    result = run_guardrails(text, cited, [], rows, [], plan, catalog)

    assert "modeled" in result.answer_text.lower()
    assert any("Modeled row" in f for f in result.failures)


def test_run_guardrails_exclusion_limitation_added():
    rows = _make_evidence_rows(1)
    text = "No citations here."
    cited: list[str] = []
    aggs = [_make_aggregate(n_null=3, n_quar=0)]
    plan = _make_plan()
    catalog = _make_catalog()

    result = run_guardrails(text, cited, [], rows, aggs, plan, catalog)

    assert any("3 null" in lim for lim in result.limitations)
