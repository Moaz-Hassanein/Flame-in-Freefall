"""Unit tests for the structured query plan execution engine."""

from __future__ import annotations

import duckdb
import pytest

from flame.config import get_settings
from flame.retrieval.structured import execute_plan
from flame.schemas.query_plan import (
    AggregateFunction,
    AggregateSpec,
    FilterCondition,
    FilterOperator,
    PlanIntent,
    QueryPlan,
)


@pytest.fixture
def cursor() -> duckdb.DuckDBPyConnection:
    settings = get_settings()
    conn = duckdb.connect(database=":memory:")
    parquet_posix = settings.dataset_output_path.as_posix()
    conn.execute(f"CREATE VIEW experiments AS SELECT * FROM read_parquet('{parquet_posix}')")
    cur = conn.cursor()
    yield cur
    cur.close()
    conn.close()


def test_modeled_rows_never_appear_in_default_results(cursor: duckdb.DuckDBPyConnection) -> None:
    plan = QueryPlan(intent=PlanIntent.LOOKUP, limit=1000)
    result = execute_plan(cursor, plan)

    assert len(result.rows) == 840  # 892 total - 52 modeled = 840
    assert all(row["is_modeled"] is False for row in result.rows)


def test_modeled_rows_included_when_flag_true(cursor: duckdb.DuckDBPyConnection) -> None:
    plan = QueryPlan(intent=PlanIntent.LOOKUP, include_modeled=True, limit=1000)
    result = execute_plan(cursor, plan)

    assert len(result.rows) == 892
    modeled_rows = [r for r in result.rows if r["is_modeled"] is True]
    assert len(modeled_rows) == 52
    assert all(r["is_modeled"] is True for r in modeled_rows)


def test_airflow_quarantine_and_null_accounting(cursor: duckdb.DuckDBPyConnection) -> None:
    """Verify that airflow aggregates count 42 quarantined and 11 null values."""
    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="airflow_velocity_cms")],
    )
    result = execute_plan(cursor, plan)
    assert len(result.aggregates) == 1
    agg = result.aggregates[0]

    assert agg.field == "airflow_velocity_cms"
    assert agg.n_used == 787
    assert agg.n_quarantined_excluded == 42
    assert agg.n_null_excluded == 11
    assert agg.n_used + agg.n_quarantined_excluded + agg.n_null_excluded == 840


def test_empty_results_return_explicit_empty_result_never_exception(
    cursor: duckdb.DuckDBPyConnection,
) -> None:
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        filters=[
            FilterCondition(
                field="fuel_material", op=FilterOperator.EQ, value="NonExistentFuel_9999"
            )
        ],
    )
    result = execute_plan(cursor, plan)
    assert result.is_empty
    assert len(result.rows) == 0
    assert len(result.aggregates) == 0
    assert result.total_matching_rows == 0


def test_empty_results_with_aggregates_return_empty_aggregates(
    cursor: duckdb.DuckDBPyConnection,
) -> None:
    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(
                field="fuel_material", op=FilterOperator.EQ, value="NonExistentFuel_9999"
            )
        ],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="oxygen_pct")],
    )
    result = execute_plan(cursor, plan)
    assert len(result.rows) == 0
    assert len(result.aggregates) == 0
    assert result.is_empty


def test_mandatory_columns_present_in_every_row(cursor: duckdb.DuckDBPyConnection) -> None:
    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        select_fields=["fuel_material"],
        limit=10,
    )
    result = execute_plan(cursor, plan)
    assert len(result.rows) == 10
    for r in result.rows:
        assert "experiment_id" in r
        assert "source_url" in r
        assert "investigation_id" in r
        assert "data_quality_flags" in r
        assert isinstance(r["data_quality_flags"], list)
        assert "is_modeled" in r
        assert "fuel_material" in r


def test_out_of_scope_intent_returns_empty_with_warning(
    cursor: duckdb.DuckDBPyConnection,
) -> None:
    plan = QueryPlan(intent=PlanIntent.OUT_OF_SCOPE)
    result = execute_plan(cursor, plan)
    assert result.is_empty
    assert any("out_of_scope" in w for w in result.warnings)


def test_limit_enforcement(cursor: duckdb.DuckDBPyConnection) -> None:
    plan = QueryPlan(intent=PlanIntent.LOOKUP, limit=5)
    result = execute_plan(cursor, plan)
    assert len(result.rows) == 5
