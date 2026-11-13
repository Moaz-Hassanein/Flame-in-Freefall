"""Unit tests for QueryPlan Pydantic schema and contract validation."""

from __future__ import annotations

import pytest

from flame.retrieval.errors import (
    PlanValidationError,
    UnknownFieldError,
    UnknownOperatorError,
)
from flame.schemas.query_plan import (
    DEFAULT_LIMIT,
    HARD_MAX_LIMIT,
    WHITELIST_FIELDS,
    AggregateFunction,
    AggregateSpec,
    FilterCondition,
    FilterOperator,
    PlanIntent,
    QueryPlan,
    SortDirection,
    SortSpec,
)


def test_whitelist_contains_canonical_and_enrichment_columns() -> None:
    assert "experiment_id" in WHITELIST_FIELDS
    assert "oxygen_pct" in WHITELIST_FIELDS
    assert "burning_rate_mms" in WHITELIST_FIELDS
    assert "is_modeled" in WHITELIST_FIELDS
    assert "data_quality_flags" in WHITELIST_FIELDS
    assert "pi_name" in WHITELIST_FIELDS
    assert len(WHITELIST_FIELDS) == 44


def test_valid_lookup_plan_is_accepted() -> None:
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="FLEX"),
            FilterCondition(field="oxygen_pct", op=FilterOperator.GTE, value=21.0),
        ],
        select_fields=["fuel_material", "oxygen_pct", "burning_rate_mms"],
        sort=[SortSpec(field="oxygen_pct", direction=SortDirection.DESC)],
        limit=50,
    )
    assert plan.intent == PlanIntent.LOOKUP
    assert len(plan.filters) == 2
    assert plan.limit == 50
    assert plan.include_modeled is False


def test_unknown_field_in_filter_raises_typed_error() -> None:
    with pytest.raises(UnknownFieldError, match="Unknown filter field 'malicious_column'"):
        FilterCondition(field="malicious_column", op=FilterOperator.EQ, value=123)


def test_unknown_operator_in_filter_raises_typed_error() -> None:
    with pytest.raises(UnknownOperatorError, match="Unknown filter operator 'like'"):
        FilterCondition.model_validate({"field": "oxygen_pct", "op": "like", "value": "21%"})


def test_unknown_field_in_aggregates_raises_typed_error() -> None:
    with pytest.raises(UnknownFieldError, match="Unknown aggregate field 'not_a_field'"):
        AggregateSpec(fn=AggregateFunction.MEAN, field="not_a_field")


def test_unknown_function_in_aggregates_raises_typed_error() -> None:
    with pytest.raises(UnknownOperatorError, match="Unknown aggregate function 'variance'"):
        AggregateSpec.model_validate({"fn": "variance", "field": "oxygen_pct"})


def test_unknown_field_in_select_fields_raises_typed_error() -> None:
    with pytest.raises(UnknownFieldError, match="Unknown select_fields field 'secret_key'"):
        QueryPlan(
            intent=PlanIntent.LOOKUP,
            select_fields=["secret_key"],
        )


def test_unknown_field_in_group_by_raises_typed_error() -> None:
    with pytest.raises(UnknownFieldError, match="Unknown group_by field 'random_field'"):
        QueryPlan(
            intent=PlanIntent.AGGREGATE,
            group_by=["random_field"],
        )


def test_unknown_field_in_sort_raises_typed_error() -> None:
    with pytest.raises(UnknownFieldError, match="Unknown sort field 'bad_column'"):
        QueryPlan(
            intent=PlanIntent.LOOKUP,
            sort=[SortSpec(field="bad_column")],
        )


def test_sort_spec_accepts_strings_and_tuples() -> None:
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        sort=["oxygen_pct desc", ("burning_rate_mms", "asc")],
    )
    assert len(plan.sort) == 2
    assert plan.sort[0].field == "oxygen_pct"
    assert plan.sort[0].direction == SortDirection.DESC
    assert plan.sort[1].field == "burning_rate_mms"
    assert plan.sort[1].direction == SortDirection.ASC


def test_limit_enforcement_positive_and_hard_maximum() -> None:
    # Default limit
    default_plan = QueryPlan(intent=PlanIntent.LOOKUP)
    assert default_plan.limit == DEFAULT_LIMIT

    # Explicit limit within bounds
    plan = QueryPlan(intent=PlanIntent.LOOKUP, limit=500)
    assert plan.limit == 500

    # Non-positive limit rejected
    with pytest.raises(PlanValidationError, match="Limit must be a positive integer"):
        QueryPlan(intent=PlanIntent.LOOKUP, limit=0)

    with pytest.raises(PlanValidationError, match="Limit must be a positive integer"):
        QueryPlan(intent=PlanIntent.LOOKUP, limit=-5)

    # Exceeding hard maximum rejected
    with pytest.raises(
        PlanValidationError, match=f"exceeds server-side hard maximum of {HARD_MAX_LIMIT}"
    ):
        QueryPlan(intent=PlanIntent.LOOKUP, limit=HARD_MAX_LIMIT + 1)


def test_between_operator_validation() -> None:
    # Valid between
    cond = FilterCondition(field="oxygen_pct", op=FilterOperator.BETWEEN, value=[15.0, 30.0])
    assert cond.value == [15.0, 30.0]

    # Length != 2 rejected
    with pytest.raises(PlanValidationError, match="requires a 2-element sequence"):
        FilterCondition(field="oxygen_pct", op=FilterOperator.BETWEEN, value=[15.0])

    # None bounds rejected
    with pytest.raises(PlanValidationError, match="bounds cannot be None"):
        FilterCondition(field="oxygen_pct", op=FilterOperator.BETWEEN, value=[None, 30.0])


def test_in_operator_validation() -> None:
    # Valid in
    cond = FilterCondition(field="dataset_family", op=FilterOperator.IN, value=["FLEX", "BASS-II"])
    assert cond.value == ["FLEX", "BASS-II"]

    # Non-collection rejected
    with pytest.raises(PlanValidationError, match="requires a collection"):
        FilterCondition(field="dataset_family", op=FilterOperator.IN, value="FLEX")


def test_null_value_rejected_for_equality() -> None:
    with pytest.raises(PlanValidationError, match="requires a non-null value"):
        FilterCondition(field="oxygen_pct", op=FilterOperator.EQ, value=None)


def test_is_null_and_not_null_allow_none_value() -> None:
    cond1 = FilterCondition(field="co_ppm", op=FilterOperator.IS_NULL)
    assert cond1.value is None

    cond2 = FilterCondition(field="burn_time_s", op=FilterOperator.NOT_NULL)
    assert cond2.value is None


def test_explain_experiment_requires_experiment_id() -> None:
    # Valid with experiment_ids
    plan1 = QueryPlan(intent=PlanIntent.EXPLAIN_EXPERIMENT, experiment_ids=["FLEX-001"])
    assert plan1.experiment_ids == ["FLEX-001"]

    # Valid with filter on experiment_id
    plan2 = QueryPlan(
        intent=PlanIntent.EXPLAIN_EXPERIMENT,
        filters=[FilterCondition(field="experiment_id", op=FilterOperator.EQ, value="FLEX-001")],
    )
    assert len(plan2.filters) == 1

    # Missing experiment_id raises PlanValidationError
    with pytest.raises(
        PlanValidationError, match="requires experiment_ids or a filter on experiment_id"
    ):
        QueryPlan(intent=PlanIntent.EXPLAIN_EXPERIMENT)


def test_extra_fields_forbidden() -> None:
    with pytest.raises(PlanValidationError):
        QueryPlan.model_validate({"intent": "lookup", "unsupported_field": True})


def test_non_string_field_name_rejected() -> None:
    from flame.schemas.query_plan import _validate_field_name

    with pytest.raises(UnknownFieldError, match="Expected string for test_context"):
        _validate_field_name(12345, context="test_context")  # type: ignore[arg-type]


def test_invalid_types_for_operators_and_intents() -> None:
    # Invalid filter operator type
    with pytest.raises(UnknownOperatorError, match="Invalid filter operator type: int"):
        FilterCondition.model_validate({"field": "oxygen_pct", "op": 123})

    # Invalid aggregate function type
    with pytest.raises(UnknownOperatorError, match="Invalid aggregate function type: int"):
        AggregateSpec.model_validate({"field": "oxygen_pct", "fn": 123})

    # Invalid sort direction type
    with pytest.raises(PlanValidationError, match="Invalid sort direction type: int"):
        SortSpec.model_validate({"field": "oxygen_pct", "direction": 123})

    # Invalid intent type
    with pytest.raises(PlanValidationError, match="Invalid intent type: int"):
        QueryPlan.model_validate({"intent": 123})


def test_sort_spec_edge_cases() -> None:
    # Sort from dict
    plan1 = QueryPlan(
        intent=PlanIntent.LOOKUP,
        sort=[{"field": "oxygen_pct", "direction": "desc"}],
    )
    assert plan1.sort[0].direction == SortDirection.DESC

    # Non-list sort
    with pytest.raises(PlanValidationError, match="Sort must be a list"):
        QueryPlan.model_validate({"intent": "lookup", "sort": "oxygen_pct desc"})

    # Invalid sort string tokens
    with pytest.raises(PlanValidationError, match="Cannot parse sort specification"):
        QueryPlan(intent=PlanIntent.LOOKUP, sort=["oxygen_pct desc extra_token"])

    # Invalid sort item type
    with pytest.raises(PlanValidationError, match="Invalid sort specification item"):
        QueryPlan(intent=PlanIntent.LOOKUP, sort=[12345])  # type: ignore[list-item]
