"""Structured deterministic retrieval engine over the validated Parquet snapshot.

Provides:
- :class:`~flame.retrieval.store.ExperimentStore`: DuckDB snapshot store with cursors.
- :class:`~flame.schemas.query_plan.QueryPlan`: Pydantic v2 deterministic retrieval contract.
- :func:`~flame.retrieval.compiler.compile_plan`: SQL compiler producing parameterized queries.
- :class:`~flame.retrieval.structured.RetrievalResult`: Results with null/quarantine accounting.
- :class:`~flame.retrieval.catalog.FieldCatalog`: Catalog of fields, types, units, and values.
"""

from __future__ import annotations

from flame.retrieval.catalog import (
    FieldCatalog,
    FieldInfo,
    build_field_catalog,
)
from flame.retrieval.compiler import (
    CompiledPlan,
    CompiledQuery,
    compile_plan,
)
from flame.retrieval.errors import (
    ExecutionError,
    PlanValidationError,
    QueryCompilationError,
    RetrievalError,
    UnknownFieldError,
    UnknownOperatorError,
)
from flame.retrieval.store import (
    DatasetVersionInfo,
    ExperimentStore,
)
from flame.retrieval.structured import (
    AggregateResult,
    RetrievalResult,
    execute_compiled_plan,
    execute_plan,
)
from flame.schemas.query_plan import (
    CANONICAL_FIELDS,
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

__all__ = [
    "CANONICAL_FIELDS",
    "DEFAULT_LIMIT",
    "HARD_MAX_LIMIT",
    "WHITELIST_FIELDS",
    "AggregateFunction",
    "AggregateResult",
    "AggregateSpec",
    "CompiledPlan",
    "CompiledQuery",
    "DatasetVersionInfo",
    "ExecutionError",
    "ExperimentStore",
    "FieldCatalog",
    "FieldInfo",
    "FilterCondition",
    "FilterOperator",
    "PlanIntent",
    "PlanValidationError",
    "QueryCompilationError",
    "QueryPlan",
    "RetrievalError",
    "RetrievalResult",
    "SortDirection",
    "SortSpec",
    "UnknownFieldError",
    "UnknownOperatorError",
    "build_field_catalog",
    "compile_plan",
    "execute_compiled_plan",
    "execute_plan",
]
