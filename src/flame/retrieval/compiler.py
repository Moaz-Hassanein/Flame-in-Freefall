"""Parameterized SQL compiler for deterministic retrieval plans.

Translates a :class:`QueryPlan` into parameterized DuckDB SQL using only
whitelisted column identifiers and DB-API parameter placeholders. User or LLM
strings are NEVER formatted or interpolated into SQL text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flame.retrieval.errors import QueryCompilationError, UnknownFieldError
from flame.schemas.experiment import CANONICAL_COLUMNS, ENRICHMENT_COLUMNS
from flame.schemas.query_plan import (
    HARD_MAX_LIMIT,
    WHITELIST_FIELDS,
    AggregateFunction,
    AggregateSpec,
    FilterOperator,
    PlanIntent,
    QueryPlan,
)

# Fields that have documented cross-family semantic differences in docs/data_dictionary.md.
# Aggregations across families on these columns trigger a warning and group by dataset_family
# by default.
SEMANTICALLY_DIFFERENT_COLUMNS: frozenset[str] = frozenset(
    {
        "burning_rate_mms",
        "co2_pct",
        "burn_time_s",
        "initial_diameter_mm",
        "extinction_diameter_mm",
        "flame_temp_k",
        "he_pct",
    }
)

# Columns that must always be available in retrieved rows for citations and traceability.
MANDATORY_ROW_COLUMNS: tuple[str, ...] = (
    "experiment_id",
    "source_url",
    "investigation_id",
    "data_quality_flags",
    "is_modeled",
)

ALL_KNOWN_COLUMNS: tuple[str, ...] = CANONICAL_COLUMNS + ENRICHMENT_COLUMNS


@dataclass(frozen=True)
class CompiledQuery:
    """A single parameterized SQL statement and its bound parameter values."""

    sql: str
    params: list[Any]
    selected_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompiledPlan:
    """The complete compiled execution plan for a QueryPlan."""

    rows_query: CompiledQuery | None
    aggregates_query: CompiledQuery | None
    aggregate_specs: list[AggregateSpec]
    effective_group_by: list[str]
    warnings: list[str]


def _assert_whitelisted(identifier: str, context: str = "identifier") -> str:
    """Ensure identifier belongs to the trusted schema whitelist."""
    if identifier not in WHITELIST_FIELDS:
        raise UnknownFieldError(f"Security error: unwhitelisted {context} '{identifier}' rejected.")
    return identifier


def compile_where_clause(
    plan: QueryPlan,
) -> tuple[str, list[Any]]:
    """Compile filters, experiment IDs, and modeled-row constraints into WHERE SQL.

    Returns:
        (where_sql, params) where where_sql starts with 'WHERE ...' or is empty.
    """
    conditions: list[str] = []
    params: list[Any] = []

    # 1. Modeled rows constraint (default: excluded)
    if not plan.include_modeled:
        conditions.append("is_modeled = FALSE")

    # 2. Plan filters
    for cond in plan.filters:
        field_id = _assert_whitelisted(cond.field, context="filter column")
        op = cond.op

        if op == FilterOperator.EQ:
            conditions.append(f"{field_id} = ?")
            params.append(cond.value)
        elif op == FilterOperator.GTE:
            conditions.append(f"{field_id} >= ?")
            params.append(cond.value)
        elif op == FilterOperator.LTE:
            conditions.append(f"{field_id} <= ?")
            params.append(cond.value)
        elif op == FilterOperator.BETWEEN:
            conditions.append(f"{field_id} BETWEEN ? AND ?")
            params.append(cond.value[0])
            params.append(cond.value[1])
        elif op == FilterOperator.IN:
            items = list(cond.value)
            if not items:
                conditions.append("1 = 0")
            else:
                placeholders = ", ".join("?" for _ in items)
                conditions.append(f"{field_id} IN ({placeholders})")
                params.extend(items)
        elif op == FilterOperator.CONTAINS:
            # Case-insensitive parameterized substring match
            conditions.append(f"{field_id} ILIKE '%' || ? || '%'")
            params.append(str(cond.value))
        elif op == FilterOperator.IS_NULL:
            conditions.append(f"{field_id} IS NULL")
        elif op == FilterOperator.NOT_NULL:
            conditions.append(f"{field_id} IS NOT NULL")
        else:
            raise QueryCompilationError(f"Unsupported filter operator: {op}")

    # 3. Explicit experiment_ids if provided
    if plan.experiment_ids is not None:
        if not plan.experiment_ids:
            conditions.append("1 = 0")
        else:
            placeholders = ", ".join("?" for _ in plan.experiment_ids)
            conditions.append(f"experiment_id IN ({placeholders})")
            params.extend(plan.experiment_ids)

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where_sql, params


def _is_single_family_filter(plan: QueryPlan) -> bool:
    """Check if the plan filters strictly constrain results to a single dataset_family."""
    for cond in plan.filters:
        if cond.field == "dataset_family":
            if cond.op == FilterOperator.EQ and cond.value:
                return True
            if (
                cond.op == FilterOperator.IN
                and isinstance(cond.value, (list, tuple, set))
                and len(cond.value) == 1
            ):
                return True
    return False


def compile_plan(
    plan: QueryPlan,
    *,
    table_name: str = "experiments",
) -> CompiledPlan:
    """Compile a QueryPlan into parameterized DuckDB SQL.

    Handles modeled row filtering, injection prevention, semantically different
    columns grouping, and parameterized SQL generation.
    """
    warnings: list[str] = []
    where_sql, base_params = compile_where_clause(plan)

    # 1. Determine effective grouping for aggregates
    effective_group_by = list(plan.group_by)
    if plan.aggregates:
        # Check for semantically different columns across families
        for agg in plan.aggregates:
            if agg.field in SEMANTICALLY_DIFFERENT_COLUMNS:
                single_family = _is_single_family_filter(plan)
                if not single_family:
                    if "dataset_family" not in effective_group_by:
                        if not plan.allow_cross_family_aggregate:
                            effective_group_by.append("dataset_family")
                            warnings.append(
                                f"Column '{agg.field}' has semantically different definitions "
                                "across dataset families (see data dictionary). "
                                "Computed aggregates are grouped by dataset_family by default."
                            )
                        else:
                            warnings.append(
                                f"Warning: Column '{agg.field}' is aggregated across dataset "
                                "families, but its meaning is documented as semantically different."
                            )
                    else:
                        warnings.append(
                            f"Column '{agg.field}' is aggregated with dataset_family grouping "
                            "due to documented cross-family semantic differences."
                        )

    # Validate all effective group_by fields
    for g_field in effective_group_by:
        _assert_whitelisted(g_field, context="group_by field")

    # 2. Compile Aggregates Query (if aggregates requested)
    aggregates_query: CompiledQuery | None = None
    if plan.aggregates:
        agg_select_parts: list[str] = []
        for g in effective_group_by:
            agg_select_parts.append(g)

        for i, agg in enumerate(plan.aggregates):
            f = _assert_whitelisted(agg.field, context="aggregate field")
            fn = agg.fn

            # Value expression
            if fn == AggregateFunction.COUNT:
                val_expr = f"COUNT({f})"
            elif fn == AggregateFunction.MEAN:
                val_expr = f"AVG({f})"
            elif fn == AggregateFunction.MEDIAN:
                val_expr = f"MEDIAN({f})"
            elif fn == AggregateFunction.MIN:
                val_expr = f"MIN({f})"
            elif fn == AggregateFunction.MAX:
                val_expr = f"MAX({f})"
            else:
                raise QueryCompilationError(f"Unsupported aggregate function: {fn}")

            # Counts for n_used, n_null_excluded, n_quarantined_excluded
            if f == "airflow_velocity_cms":
                n_used_expr = "COUNT(airflow_velocity_cms)"
                n_quar_expr = (
                    "COUNT(*) FILTER (WHERE list_contains(data_quality_flags, "
                    "'AIRFLOW_QUARANTINED'))"
                )
                n_null_expr = (
                    "COUNT(*) FILTER (WHERE airflow_velocity_cms IS NULL "
                    "AND NOT list_contains(data_quality_flags, 'AIRFLOW_QUARANTINED'))"
                )
            else:
                n_used_expr = f"COUNT({f})"
                n_quar_expr = "0"
                n_null_expr = f"COUNT(*) FILTER (WHERE {f} IS NULL)"

            agg_select_parts.append(f"{val_expr} AS val_{i}")
            agg_select_parts.append(f"{n_used_expr} AS n_used_{i}")
            agg_select_parts.append(f"{n_null_expr} AS n_null_{i}")
            agg_select_parts.append(f"{n_quar_expr} AS n_quar_{i}")

        group_by_clause = f"GROUP BY {', '.join(effective_group_by)}" if effective_group_by else ""
        order_by_clause = f"ORDER BY {', '.join(effective_group_by)}" if effective_group_by else ""

        agg_sql_tokens = [
            f"SELECT {', '.join(agg_select_parts)}",
            f"FROM {table_name}",
        ]
        if where_sql:
            agg_sql_tokens.append(where_sql)
        if group_by_clause:
            agg_sql_tokens.append(group_by_clause)
        if order_by_clause:
            agg_sql_tokens.append(order_by_clause)

        agg_sql = "\n".join(agg_sql_tokens)
        aggregates_query = CompiledQuery(
            sql=agg_sql,
            params=list(base_params),
            selected_columns=tuple(effective_group_by),
        )

    # 3. Compile Rows Query (always available unless out_of_scope)
    rows_query: CompiledQuery | None = None
    if plan.intent != PlanIntent.OUT_OF_SCOPE:
        if plan.select_fields:
            # Preserve requested fields while guaranteeing mandatory columns
            cols_to_select: list[str] = []
            seen: set[str] = set()
            for col in plan.select_fields:
                _assert_whitelisted(col, context="select column")
                if col not in seen:
                    cols_to_select.append(col)
                    seen.add(col)
            for m in MANDATORY_ROW_COLUMNS:
                if m not in seen:
                    cols_to_select.append(m)
                    seen.add(m)
        else:
            cols_to_select = list(ALL_KNOWN_COLUMNS)

        row_params = list(base_params)

        # Ordering
        order_parts: list[str] = []
        if plan.sort:
            for s in plan.sort:
                s_field = _assert_whitelisted(s.field, context="sort column")
                dir_str = "ASC" if s.direction.value == "asc" else "DESC"
                order_parts.append(f"{s_field} {dir_str} NULLS LAST")
        else:
            # Deterministic default ordering
            order_parts.append("experiment_id ASC")

        order_clause = f"ORDER BY {', '.join(order_parts)}"

        # Limit enforcement
        limit_val = min(max(1, plan.limit), HARD_MAX_LIMIT)
        limit_clause = "LIMIT ?"
        row_params.append(limit_val)

        row_sql_tokens = [
            f"SELECT {', '.join(cols_to_select)}",
            f"FROM {table_name}",
        ]
        if where_sql:
            row_sql_tokens.append(where_sql)
        row_sql_tokens.append(order_clause)
        row_sql_tokens.append(limit_clause)

        rows_sql = "\n".join(row_sql_tokens)
        rows_query = CompiledQuery(
            sql=rows_sql,
            params=row_params,
            selected_columns=tuple(cols_to_select),
        )
    else:
        warnings.append("Plan intent is out_of_scope; no rows or aggregates compiled.")

    return CompiledPlan(
        rows_query=rows_query,
        aggregates_query=aggregates_query,
        aggregate_specs=plan.aggregates,
        effective_group_by=effective_group_by,
        warnings=warnings,
    )


__all__ = [
    "ALL_KNOWN_COLUMNS",
    "MANDATORY_ROW_COLUMNS",
    "SEMANTICALLY_DIFFERENT_COLUMNS",
    "CompiledPlan",
    "CompiledQuery",
    "compile_plan",
    "compile_where_clause",
]
