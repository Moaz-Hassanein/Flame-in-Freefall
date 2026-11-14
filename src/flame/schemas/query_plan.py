"""Typed query plan schema and validation for deterministic retrieval.

The :class:`QueryPlan` is the only contract between any future planner (LLM or API)
and the structured retrieval engine. It specifies exact deterministic operations
over the validated dataset snapshot without any model execution.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from flame.retrieval.errors import (
    PlanValidationError,
    UnknownFieldError,
    UnknownOperatorError,
)
from flame.schemas.experiment import CANONICAL_COLUMNS, DatasetRecord

# Allowed fields are derived directly from the trusted DatasetRecord schema,
# which includes all 28 canonical columns and all enrichment fields.
WHITELIST_FIELDS: frozenset[str] = frozenset(DatasetRecord.model_fields.keys())
CANONICAL_FIELDS: frozenset[str] = frozenset(CANONICAL_COLUMNS)

DEFAULT_LIMIT: int = 100
HARD_MAX_LIMIT: int = 1000


class BasePlanModel(BaseModel):
    """Base model for query plan entities that unwraps typed validation errors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError as err:
            for error in err.errors():
                ctx = error.get("ctx")
                if ctx and "error" in ctx and isinstance(ctx["error"], PlanValidationError):
                    raise ctx["error"] from err
            raise PlanValidationError(str(err)) from err

    @classmethod
    def model_validate(cls, obj: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return super().model_validate(obj, *args, **kwargs)
        except ValidationError as err:
            for error in err.errors():
                ctx = error.get("ctx")
                if ctx and "error" in ctx and isinstance(ctx["error"], PlanValidationError):
                    raise ctx["error"] from err
            raise PlanValidationError(str(err)) from err


class PlanIntent(StrEnum):
    """Supported deterministic retrieval intents."""

    LOOKUP = "lookup"
    AGGREGATE = "aggregate"
    COMPARE = "compare"
    EXPLAIN_EXPERIMENT = "explain_experiment"
    QUALITATIVE = "qualitative"
    OUT_OF_SCOPE = "out_of_scope"


class FilterOperator(StrEnum):
    """Supported deterministic filter operators."""

    EQ = "eq"
    IN = "in"
    GTE = "gte"
    LTE = "lte"
    BETWEEN = "between"
    CONTAINS = "contains"
    IS_NULL = "is_null"
    NOT_NULL = "not_null"


class AggregateFunction(StrEnum):
    """Supported aggregate functions."""

    COUNT = "count"
    MEAN = "mean"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"


class SortDirection(StrEnum):
    """Sort direction."""

    ASC = "asc"
    DESC = "desc"


def _validate_field_name(field_name: str, context: str = "field") -> str:
    """Validate that a field name exists in the trusted schema whitelist."""
    if not isinstance(field_name, str):
        raise UnknownFieldError(f"Expected string for {context}, got {type(field_name).__name__}.")
    if field_name not in WHITELIST_FIELDS:
        raise UnknownFieldError(
            f"Unknown {context} '{field_name}'. "
            f"Field names must be in the schema whitelist ({len(WHITELIST_FIELDS)} fields)."
        )
    return field_name


class FilterCondition(BasePlanModel):
    """Single deterministic filter condition on a whitelisted field."""

    field: str
    op: FilterOperator
    value: Any = None

    @field_validator("field")
    @classmethod
    def _validate_field(cls, v: str) -> str:
        return _validate_field_name(v, context="filter field")

    @field_validator("op", mode="before")
    @classmethod
    def _validate_op(cls, v: object) -> FilterOperator:
        if isinstance(v, FilterOperator):
            return v
        if isinstance(v, str):
            try:
                return FilterOperator(v.lower())
            except ValueError as err:
                valid_ops = [op.value for op in FilterOperator]
                raise UnknownOperatorError(
                    f"Unknown filter operator '{v}'. Allowed operators: {valid_ops}."
                ) from err
        raise UnknownOperatorError(f"Invalid filter operator type: {type(v).__name__}.")

    @model_validator(mode="after")
    def _validate_value(self) -> FilterCondition:
        if self.op in (FilterOperator.IS_NULL, FilterOperator.NOT_NULL):
            return self
        if self.value is None:
            raise PlanValidationError(
                f"Filter operator '{self.op.value}' requires a non-null value."
            )
        if self.op == FilterOperator.BETWEEN:
            if not isinstance(self.value, (list, tuple)) or len(self.value) != 2:
                raise PlanValidationError(
                    "Filter operator 'between' requires a 2-element sequence [low, high], "
                    f"got {self.value!r}."
                )
            if self.value[0] is None or self.value[1] is None:
                raise PlanValidationError("Filter operator 'between' bounds cannot be None.")
        elif self.op == FilterOperator.IN and not isinstance(self.value, (list, tuple, set)):
            raise PlanValidationError(
                f"Filter operator 'in' requires a collection, got {type(self.value).__name__}."
            )
        return self


class AggregateSpec(BasePlanModel):
    """Specification of an aggregate function to compute on a field."""

    fn: AggregateFunction
    field: str

    @field_validator("field")
    @classmethod
    def _validate_field(cls, v: str) -> str:
        return _validate_field_name(v, context="aggregate field")

    @field_validator("fn", mode="before")
    @classmethod
    def _validate_fn(cls, v: object) -> AggregateFunction:
        if isinstance(v, AggregateFunction):
            return v
        if isinstance(v, str):
            try:
                return AggregateFunction(v.lower())
            except ValueError as err:
                valid_fns = [f.value for f in AggregateFunction]
                raise UnknownOperatorError(
                    f"Unknown aggregate function '{v}'. Allowed functions: {valid_fns}."
                ) from err
        raise UnknownOperatorError(f"Invalid aggregate function type: {type(v).__name__}.")


class SortSpec(BasePlanModel):
    """Specification for sorting query results."""

    field: str
    direction: SortDirection = SortDirection.ASC

    @field_validator("field")
    @classmethod
    def _validate_field(cls, v: str) -> str:
        return _validate_field_name(v, context="sort field")

    @field_validator("direction", mode="before")
    @classmethod
    def _validate_direction(cls, v: object) -> SortDirection:
        if isinstance(v, SortDirection):
            return v
        if isinstance(v, str):
            try:
                return SortDirection(v.lower())
            except ValueError as err:
                raise PlanValidationError(
                    f"Unknown sort direction '{v}'. Allowed: 'asc', 'desc'."
                ) from err
        raise PlanValidationError(f"Invalid sort direction type: {type(v).__name__}.")


class QueryPlan(BasePlanModel):
    """The formal contract between LLM planner and deterministic retrieval.

    Validates all field names, operators, and parameters against the trusted
    schema whitelist before any compilation or database interaction.
    """

    intent: PlanIntent
    filters: list[FilterCondition] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregates: list[AggregateSpec] = Field(default_factory=list)
    select_fields: list[str] = Field(default_factory=list)
    sort: list[SortSpec] = Field(default_factory=list)
    limit: int = Field(default=DEFAULT_LIMIT)
    include_modeled: bool = Field(default=False)
    experiment_ids: list[str] | None = Field(default=None)
    allow_cross_family_aggregate: bool = Field(
        default=False,
        description="When True, allows aggregating across families without grouping by family.",
    )

    @field_validator("intent", mode="before")
    @classmethod
    def _validate_intent(cls, v: object) -> PlanIntent:
        if isinstance(v, PlanIntent):
            return v
        if isinstance(v, str):
            try:
                return PlanIntent(v.lower())
            except ValueError as err:
                valid_intents = [i.value for i in PlanIntent]
                raise PlanValidationError(
                    f"Unknown intent '{v}'. Allowed intents: {valid_intents}."
                ) from err
        raise PlanValidationError(f"Invalid intent type: {type(v).__name__}.")

    @field_validator("group_by")
    @classmethod
    def _validate_group_by(cls, values: list[str]) -> list[str]:
        return [_validate_field_name(f, context="group_by field") for f in values]

    @field_validator("select_fields")
    @classmethod
    def _validate_select_fields(cls, values: list[str]) -> list[str]:
        return [_validate_field_name(f, context="select_fields field") for f in values]

    @field_validator("sort", mode="before")
    @classmethod
    def _validate_sort(cls, values: object) -> list[SortSpec]:
        if not isinstance(values, (list, tuple)):
            raise PlanValidationError("Sort must be a list of SortSpec items or tuples.")
        parsed: list[SortSpec] = []
        for item in values:
            if isinstance(item, SortSpec):
                parsed.append(item)
            elif isinstance(item, dict):
                parsed.append(SortSpec.model_validate(item))
            elif isinstance(item, (tuple, list)) and len(item) == 2:
                field_val, dir_val = item
                parsed.append(
                    SortSpec(
                        field=str(field_val),
                        direction=SortDirection(str(dir_val).lower()),
                    )
                )
            elif isinstance(item, str):
                tokens = item.strip().split()
                if len(tokens) == 1:
                    parsed.append(SortSpec(field=tokens[0]))
                elif len(tokens) == 2:
                    parsed.append(
                        SortSpec(
                            field=tokens[0],
                            direction=SortDirection(tokens[1].lower()),
                        )
                    )
                else:
                    raise PlanValidationError(f"Cannot parse sort specification: {item!r}")
            else:
                raise PlanValidationError(f"Invalid sort specification item: {item!r}")
        return parsed

    @field_validator("limit")
    @classmethod
    def _validate_limit(cls, v: int) -> int:
        if v <= 0:
            raise PlanValidationError("Limit must be a positive integer.")
        if v > HARD_MAX_LIMIT:
            raise PlanValidationError(
                f"Requested limit {v} exceeds server-side hard maximum of {HARD_MAX_LIMIT}."
            )
        return v

    @model_validator(mode="after")
    def _check_intent_constraints(self) -> QueryPlan:
        if (
            self.intent == PlanIntent.EXPLAIN_EXPERIMENT
            and not self.experiment_ids
            and not any(f.field == "experiment_id" for f in self.filters)
        ):
            raise PlanValidationError(
                "explain_experiment intent requires experiment_ids or a filter on experiment_id."
            )
        return self


__all__ = [
    "CANONICAL_FIELDS",
    "DEFAULT_LIMIT",
    "HARD_MAX_LIMIT",
    "WHITELIST_FIELDS",
    "AggregateFunction",
    "AggregateSpec",
    "BasePlanModel",
    "FilterCondition",
    "FilterOperator",
    "PlanIntent",
    "QueryPlan",
    "SortDirection",
    "SortSpec",
]
