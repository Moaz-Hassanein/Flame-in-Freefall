"""Unit tests for the parameterized SQL compiler and SQL injection prevention."""

from __future__ import annotations

import duckdb
import pytest

from flame.retrieval.compiler import (
    MANDATORY_ROW_COLUMNS,
    compile_plan,
    compile_where_clause,
)
from flame.schemas.query_plan import (
    AggregateFunction,
    AggregateSpec,
    FilterCondition,
    FilterOperator,
    PlanIntent,
    QueryPlan,
    SortDirection,
    SortSpec,
)


def test_sql_injection_in_filter_value_remains_parameterized() -> None:
    """Verify that SQL injection strings in filter values cannot alter SQL structure."""
    injection_payload = "'; DROP TABLE experiments; --"
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        filters=[
            FilterCondition(field="fuel_material", op=FilterOperator.EQ, value=injection_payload)
        ],
        select_fields=["fuel_material"],
    )

    compiled = compile_plan(plan)
    assert compiled.rows_query is not None

    # The SQL text must contain only the placeholder ?, never the raw injection string
    assert injection_payload not in compiled.rows_query.sql
    assert "DROP TABLE" not in compiled.rows_query.sql
    assert "fuel_material = ?" in compiled.rows_query.sql
    assert injection_payload in compiled.rows_query.params

    # Execute safely in DuckDB without error and without executing DROP TABLE
    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE experiments ("
        "experiment_id VARCHAR, "
        "source_url VARCHAR, "
        "investigation_id VARCHAR, "
        "data_quality_flags VARCHAR[], "
        "is_modeled BOOLEAN, "
        "fuel_material VARCHAR"
        ")"
    )
    conn.execute("INSERT INTO experiments VALUES ('E1', 'http://a', 'INV1', [], FALSE, 'Methanol')")

    cur = conn.cursor()
    cur.execute(compiled.rows_query.sql, compiled.rows_query.params)
    results = cur.fetchall()
    assert len(results) == 0  # No row matches the injection string

    # Table still exists intact
    count = cur.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    assert count == 1
    cur.close()
    conn.close()


def test_sql_injection_in_contains_remains_parameterized() -> None:
    """Verify contains operator with quotes and wildcards stays parameterized."""
    injection_payload = "%' OR '1'='1"
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        filters=[
            FilterCondition(
                field="fuel_material", op=FilterOperator.CONTAINS, value=injection_payload
            )
        ],
    )

    compiled = compile_plan(plan)
    assert compiled.rows_query is not None
    assert "ILIKE '%' || ? || '%'" in compiled.rows_query.sql
    assert injection_payload not in compiled.rows_query.sql
    assert injection_payload in compiled.rows_query.params


@pytest.mark.parametrize(
    "payload",
    [
        "1 OR 1=1",
        "admin' --",
        "' UNION SELECT 1, 2, 3 --",
        "'; EXEC xp_cmdshell('dir'); --",
        '" or ""="',
    ],
)
def test_various_injection_payloads_stay_in_params(payload: str) -> None:
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        filters=[FilterCondition(field="sample_description", op=FilterOperator.EQ, value=payload)],
    )
    compiled = compile_plan(plan)
    assert compiled.rows_query is not None
    assert payload not in compiled.rows_query.sql
    assert payload in compiled.rows_query.params


def test_modeled_rows_excluded_by_default() -> None:
    plan = QueryPlan(intent=PlanIntent.LOOKUP)
    where_sql, params = compile_where_clause(plan)
    assert "is_modeled = FALSE" in where_sql
    assert len(params) == 0


def test_modeled_rows_included_when_flag_true() -> None:
    plan = QueryPlan(intent=PlanIntent.LOOKUP, include_modeled=True)
    where_sql, _ = compile_where_clause(plan)
    assert "is_modeled = FALSE" not in where_sql


def test_compile_all_filter_operators() -> None:
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        filters=[
            FilterCondition(field="oxygen_pct", op=FilterOperator.EQ, value=21.0),
            FilterCondition(field="pressure_kpa", op=FilterOperator.GTE, value=100.0),
            FilterCondition(field="pressure_mmhg", op=FilterOperator.LTE, value=800.0),
            FilterCondition(field="burn_time_s", op=FilterOperator.BETWEEN, value=[2.0, 10.0]),
            FilterCondition(
                field="dataset_family", op=FilterOperator.IN, value=["FLEX", "BASS-II"]
            ),
            FilterCondition(field="extinction_outcome", op=FilterOperator.IS_NULL),
            FilterCondition(field="flame_temp_k", op=FilterOperator.NOT_NULL),
            FilterCondition(field="fuel_material", op=FilterOperator.CONTAINS, value="droplet"),
        ],
    )
    where_sql, params = compile_where_clause(plan)
    assert "oxygen_pct = ?" in where_sql
    assert "pressure_kpa >= ?" in where_sql
    assert "pressure_mmhg <= ?" in where_sql
    assert "burn_time_s BETWEEN ? AND ?" in where_sql
    assert "dataset_family IN (?, ?)" in where_sql
    assert "extinction_outcome IS NULL" in where_sql
    assert "flame_temp_k IS NOT NULL" in where_sql
    assert "fuel_material ILIKE '%' || ? || '%'" in where_sql
    assert params == [21.0, 100.0, 800.0, 2.0, 10.0, "FLEX", "BASS-II", "droplet"]


def test_empty_in_filter_compiles_to_false() -> None:
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        filters=[FilterCondition(field="dataset_family", op=FilterOperator.IN, value=[])],
    )
    where_sql, params = compile_where_clause(plan)
    assert "1 = 0" in where_sql
    assert len(params) == 0


def test_semantically_different_column_groups_by_family_by_default() -> None:
    """Aggregating burning_rate_mms across families triggers dataset_family grouping & warning."""
    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="burning_rate_mms")],
    )
    compiled = compile_plan(plan)
    assert "dataset_family" in compiled.effective_group_by
    assert any("semantically different" in w for w in compiled.warnings)
    assert compiled.aggregates_query is not None
    assert "GROUP BY dataset_family" in compiled.aggregates_query.sql


def test_semantically_different_column_single_family_filter_needs_no_forced_grouping() -> None:
    """When filter constrains to a single family, dataset_family is not forced into group_by."""
    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="FLEX")],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="burning_rate_mms")],
    )
    compiled = compile_plan(plan)
    assert "dataset_family" not in compiled.effective_group_by
    assert len(compiled.warnings) == 0


def test_cross_family_aggregate_override_flag() -> None:
    """When allow_cross_family_aggregate is True, grouping is not forced but warning is emitted."""
    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="burning_rate_mms")],
        allow_cross_family_aggregate=True,
    )
    compiled = compile_plan(plan)
    assert "dataset_family" not in compiled.effective_group_by
    assert any("semantically different" in w for w in compiled.warnings)


def test_mandatory_columns_always_present_in_rows_query() -> None:
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        select_fields=["fuel_material", "oxygen_pct"],
    )
    compiled = compile_plan(plan)
    assert compiled.rows_query is not None
    for mandatory in MANDATORY_ROW_COLUMNS:
        assert mandatory in compiled.rows_query.selected_columns
    assert "fuel_material" in compiled.rows_query.selected_columns
    assert "oxygen_pct" in compiled.rows_query.selected_columns


def test_sorting_order_and_limit() -> None:
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        sort=[SortSpec(field="oxygen_pct", direction=SortDirection.DESC)],
        limit=25,
    )
    compiled = compile_plan(plan)
    assert compiled.rows_query is not None
    assert "ORDER BY oxygen_pct DESC NULLS LAST" in compiled.rows_query.sql
    assert "LIMIT ?" in compiled.rows_query.sql
    assert compiled.rows_query.params[-1] == 25


def test_out_of_scope_intent_compiles_no_queries() -> None:
    plan = QueryPlan(intent=PlanIntent.OUT_OF_SCOPE)
    compiled = compile_plan(plan)
    assert compiled.rows_query is None
    assert compiled.aggregates_query is None
    assert any("out_of_scope" in w for w in compiled.warnings)


def test_assert_whitelisted_raises_unknown_field_error() -> None:
    from flame.retrieval.compiler import _assert_whitelisted
    from flame.retrieval.errors import UnknownFieldError

    with pytest.raises(UnknownFieldError, match="unwhitelisted test_context 'hack_field' rejected"):
        _assert_whitelisted("hack_field", context="test_context")


def test_compile_experiment_ids_non_empty_and_empty() -> None:
    # Non-empty experiment_ids
    plan = QueryPlan(
        intent=PlanIntent.EXPLAIN_EXPERIMENT,
        experiment_ids=["EXP-1", "EXP-2"],
    )
    where_sql, params = compile_where_clause(plan)
    assert "experiment_id IN (?, ?)" in where_sql
    assert "EXP-1" in params
    assert "EXP-2" in params

    # Empty experiment_ids
    plan_empty = QueryPlan(
        intent=PlanIntent.EXPLAIN_EXPERIMENT,
        filters=[FilterCondition(field="experiment_id", op=FilterOperator.EQ, value="EXP-1")],
        experiment_ids=[],
    )
    where_sql_empty, _ = compile_where_clause(plan_empty)
    assert "1 = 0" in where_sql_empty


def test_single_family_in_filter_recognition() -> None:
    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[FilterCondition(field="dataset_family", op=FilterOperator.IN, value=["FLEX"])],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="burning_rate_mms")],
    )
    compiled = compile_plan(plan)
    # Since only 1 family in the IN filter, dataset_family is not forcibly added
    assert "dataset_family" not in compiled.effective_group_by


def test_semantically_different_column_when_family_already_in_group_by() -> None:
    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        group_by=["dataset_family"],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="burning_rate_mms")],
    )
    compiled = compile_plan(plan)
    assert compiled.effective_group_by == ["dataset_family"]
    assert any(
        "due to documented cross-family semantic differences" in w for w in compiled.warnings
    )


def test_all_aggregate_functions_compile() -> None:
    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        aggregates=[
            AggregateSpec(fn=AggregateFunction.COUNT, field="oxygen_pct"),
            AggregateSpec(fn=AggregateFunction.MEAN, field="oxygen_pct"),
            AggregateSpec(fn=AggregateFunction.MEDIAN, field="oxygen_pct"),
            AggregateSpec(fn=AggregateFunction.MIN, field="oxygen_pct"),
            AggregateSpec(fn=AggregateFunction.MAX, field="oxygen_pct"),
        ],
    )
    compiled = compile_plan(plan)
    assert compiled.aggregates_query is not None
    assert "COUNT(oxygen_pct)" in compiled.aggregates_query.sql
    assert "AVG(oxygen_pct)" in compiled.aggregates_query.sql
    assert "MEDIAN(oxygen_pct)" in compiled.aggregates_query.sql
    assert "MIN(oxygen_pct)" in compiled.aggregates_query.sql
    assert "MAX(oxygen_pct)" in compiled.aggregates_query.sql
