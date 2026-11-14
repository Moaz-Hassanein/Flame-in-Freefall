"""Execution engine for structured deterministic retrieval plans.

Executes compiled plans against a DuckDB connection cursor, strictly enforcing:
- Modeled rows exclusion by default; explicit is_modeled labeling when included.
- Explicit accounting of n_used, n_null_excluded, and n_quarantined_excluded.
- Default dataset_family grouping and warnings for semantically sensitive fields.
- Returning an explicit empty RetrievalResult (never an exception) on empty results.
"""

from __future__ import annotations

from typing import Any

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from flame.retrieval.compiler import CompiledPlan, compile_plan
from flame.schemas.query_plan import AggregateFunction, PlanIntent, QueryPlan


class AggregateResult(BaseModel):
    """Computed aggregate with exact null and quarantine accounting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fn: str = Field(description="Aggregate function name (count, mean, median, min, max).")
    field: str = Field(description="Column name aggregated.")
    value: float | int | None = Field(
        default=None,
        description="Computed aggregate value, or None if all values were null/quarantined.",
    )
    n_used: int = Field(description="Number of non-null, non-quarantined values included.")
    n_null_excluded: int = Field(description="Number of unquarantined null values excluded.")
    n_quarantined_excluded: int = Field(
        description="Number of quarantined values excluded (e.g. corrupted airflow readings)."
    )
    group_key: dict[str, Any] | None = Field(
        default=None, description="Grouping field values if the aggregate was grouped."
    )
    warning: str | None = Field(
        default=None, description="Optional specific warning about this aggregate."
    )


class RetrievalResult(BaseModel):
    """Deterministic retrieval response containing rows, aggregates, and warnings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rows: list[dict[str, Any]] = Field(default_factory=list)
    aggregates: list[AggregateResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    total_matching_rows: int = Field(default=0)

    @property
    def is_empty(self) -> bool:
        """True if no rows and no aggregates were produced."""
        return len(self.rows) == 0 and len(self.aggregates) == 0


def execute_compiled_plan(
    cur: duckdb.DuckDBPyConnection,
    compiled: CompiledPlan,
    plan: QueryPlan,
) -> RetrievalResult:
    """Execute a compiled query plan using a DuckDB cursor."""
    warnings = list(compiled.warnings)
    rows: list[dict[str, Any]] = []
    aggregates: list[AggregateResult] = []

    if plan.intent == PlanIntent.OUT_OF_SCOPE:
        return RetrievalResult(
            rows=[],
            aggregates=[],
            warnings=warnings,
            total_matching_rows=0,
        )

    # 1. Execute rows query if compiled
    if compiled.rows_query is not None:
        cur.execute(compiled.rows_query.sql, compiled.rows_query.params)
        raw_rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]

        for raw in raw_rows:
            row_dict: dict[str, Any] = dict(zip(col_names, raw, strict=True))

            # Normalize data_quality_flags to a clean list of strings
            flags = row_dict.get("data_quality_flags")
            if flags is None:
                row_dict["data_quality_flags"] = []
            elif isinstance(flags, (list, tuple)):
                row_dict["data_quality_flags"] = list(flags)

            # Ensure is_modeled is an explicit boolean
            row_dict["is_modeled"] = bool(row_dict.get("is_modeled", False))

            rows.append(row_dict)

    # 2. Execute aggregates query if compiled
    if compiled.aggregates_query is not None:
        cur.execute(compiled.aggregates_query.sql, compiled.aggregates_query.params)
        agg_rows = cur.fetchall()

        n_group_cols = len(compiled.effective_group_by)

        for row in agg_rows:
            group_key: dict[str, Any] | None = None
            if n_group_cols > 0:
                group_key = {col: row[idx] for idx, col in enumerate(compiled.effective_group_by)}

            # Check if this group matched any rows at all
            if len(compiled.aggregate_specs) > 0:
                first_used = int(row[n_group_cols + 1])
                first_null = int(row[n_group_cols + 2])
                first_quar = int(row[n_group_cols + 3])
                if first_used == 0 and first_null == 0 and first_quar == 0:
                    # 0 rows matched in the entire dataset for this query
                    continue

            for i, spec in enumerate(compiled.aggregate_specs):
                offset = n_group_cols + i * 4
                raw_val = row[offset]
                n_used = int(row[offset + 1])
                n_null = int(row[offset + 2])
                n_quar = int(row[offset + 3])

                val: float | int | None = None
                if raw_val is not None:
                    val = int(raw_val) if spec.fn == AggregateFunction.COUNT else float(raw_val)

                aggregates.append(
                    AggregateResult(
                        fn=spec.fn.value,
                        field=spec.field,
                        value=val,
                        n_used=n_used,
                        n_null_excluded=n_null,
                        n_quarantined_excluded=n_quar,
                        group_key=group_key,
                    )
                )

    # Determine total matching rows
    total_matching = len(rows)
    if aggregates and len(compiled.aggregate_specs) > 0:
        first_spec = compiled.aggregate_specs[0]
        matching_for_spec = sum(
            agg.n_used + agg.n_null_excluded + agg.n_quarantined_excluded
            for agg in aggregates
            if agg.field == first_spec.field and agg.fn == first_spec.fn.value
        )
        if matching_for_spec > 0 or len(rows) == 0:
            total_matching = matching_for_spec

    return RetrievalResult(
        rows=rows,
        aggregates=aggregates,
        warnings=warnings,
        total_matching_rows=total_matching,
    )


def execute_plan(
    cur: duckdb.DuckDBPyConnection,
    plan: QueryPlan,
    *,
    table_name: str = "experiments",
) -> RetrievalResult:
    """Compile and execute a QueryPlan using a DuckDB cursor."""
    compiled = compile_plan(plan, table_name=table_name)
    return execute_compiled_plan(cur, compiled, plan)


__all__ = [
    "AggregateResult",
    "RetrievalResult",
    "execute_compiled_plan",
    "execute_plan",
]
