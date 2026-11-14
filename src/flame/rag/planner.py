"""Structured Query Planner translating natural language questions into validated QueryPlans."""

from __future__ import annotations

import difflib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flame.llm.client import LLMClient
from flame.retrieval.catalog import FieldCatalog, build_field_catalog
from flame.retrieval.errors import PlanValidationError
from flame.retrieval.store import ExperimentStore
from flame.schemas.query_plan import (
    FilterCondition,
    FilterOperator,
    PlanIntent,
    QueryPlan,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
PLANNER_PROMPT_PATH = PROMPTS_DIR / "planner_system.txt"


@dataclass(frozen=True)
class PlannerResult:
    """Outcome of planner execution."""

    plan: QueryPlan
    clarification_needed: bool = False
    clarification_message: str | None = None
    normalization_notes: list[str] = field(default_factory=list)
    raw_response: dict[str, Any] | None = None


def load_planner_system_prompt() -> str:
    """Load the versioned planner prompt template from disk."""
    if not PLANNER_PROMPT_PATH.exists():
        raise FileNotFoundError(f"Planner prompt template not found at {PLANNER_PROMPT_PATH}")
    return PLANNER_PROMPT_PATH.read_text(encoding="utf-8")


def format_catalog_summary(catalog: FieldCatalog) -> str:
    """Generate concise catalog summary for the system prompt."""
    lines: list[str] = []
    lines.append("AVAILABLE SNAPSHOT FIELDS:")
    for name, info in catalog.fields.items():
        unit_str = f" [{info.unit}]" if info.unit else ""
        caveat_str = f" (CAVEAT: {info.caveat})" if info.caveat else ""
        allowed_str = ""
        if info.is_categorical and info.allowed_values:
            # show representative allowed values
            sample_vals = info.allowed_values[:10]
            val_strs = [f"'{v}'" for v in sample_vals]
            if len(info.allowed_values) > 10:
                val_strs.append(f"... (+{len(info.allowed_values) - 10} more)")
            allowed_str = f" | Allowed: {', '.join(val_strs)}"

        lines.append(f"- `{name}` ({info.data_type}){unit_str}{allowed_str}{caveat_str}")
    return "\n".join(lines)


class QueryPlanner:
    """Translates natural language questions into validated QueryPlan models via an LLM."""

    def __init__(
        self,
        llm_client: LLMClient,
        catalog: FieldCatalog | None = None,
        store: ExperimentStore | None = None,
    ) -> None:
        self.llm_client = llm_client
        self._store = store

        if catalog is not None:
            self.catalog = catalog
        else:
            # Load catalog from store
            if self._store is not None:
                cur = self._store.get_cursor()
                self.catalog = build_field_catalog(cur)
            else:
                with ExperimentStore() as temp_store:
                    cur = temp_store.get_cursor()
                    self.catalog = build_field_catalog(cur)

        # Precompute vocabulary lookups for fuzzy matching
        self._vocab_maps: dict[str, list[str]] = {}
        for fname in ("fuel_material", "dataset_family", "gravity_condition", "extinction_outcome"):
            finfo = self.catalog.get_field(fname)
            if finfo and finfo.allowed_values:
                self._vocab_maps[fname] = [str(v) for v in finfo.allowed_values if v is not None]

        self._system_prompt_template = load_planner_system_prompt()
        self._rendered_system_prompt = self._system_prompt_template.replace(
            "{{catalog_summary}}",
            format_catalog_summary(self.catalog),
        )

    def normalize_filter_values(
        self,
        filters: list[FilterCondition],
    ) -> tuple[list[FilterCondition], list[str], bool, str | None]:
        """Normalize filter values against catalog vocabularies using explicit fuzzy matching.

        Returns:
            (normalized_filters, normalization_notes, clarification_needed, clarification_message)
        """
        normalized: list[FilterCondition] = []
        notes: list[str] = []
        clarification_needed = False
        clarification_msg: str | None = None

        for cond in filters:
            field_name = cond.field
            op = cond.op
            val = cond.value

            # If it's an equality or in filter on a known categorical field with a string value
            if (
                field_name in self._vocab_maps
                and op in (FilterOperator.EQ, FilterOperator.CONTAINS)
                and isinstance(val, str)
            ):
                allowed = self._vocab_maps[field_name]
                # Check exact case match
                if val in allowed:
                    normalized.append(cond)
                    continue

                # Check case-insensitive exact match
                ci_matches = [cand for cand in allowed if cand.lower() == val.lower()]
                if len(ci_matches) == 1:
                    resolved = ci_matches[0]
                    notes.append(
                        f"Exact case-insensitive match for {field_name}: '{val}' -> '{resolved}'"
                    )
                    normalized.append(FilterCondition(field=field_name, op=op, value=resolved))
                    continue

                # Fuzzy substring / similarity match
                # e.g., 'PMMA' matching 'PMMA (Acrylic)'
                substr_matches = [cand for cand in allowed if val.lower() in cand.lower()]
                if len(substr_matches) == 1:
                    resolved = substr_matches[0]
                    notes.append(
                        f"Unambiguous substring match for {field_name}: '{val}' -> '{resolved}'"
                    )
                    normalized.append(FilterCondition(field=field_name, op=op, value=resolved))
                    continue
                elif len(substr_matches) > 1:
                    # Surface ambiguity as clarification flag rather than guessing
                    clarification_needed = True
                    clarification_msg = (
                        f"Ambiguous value '{val}' for field '{field_name}'. "
                        f"Matches multiple variants: {substr_matches[:5]}"
                    )
                    notes.append(
                        f"Ambiguity detected for {field_name}='{val}': matches {substr_matches[:5]}"
                    )
                    # Keep original or best similarity candidate
                    close = difflib.get_close_matches(val, allowed, n=1, cutoff=0.6)
                    target_val = close[0] if close else val
                    normalized.append(FilterCondition(field=field_name, op=op, value=target_val))
                    continue

                # Similarity match using difflib
                close_matches = difflib.get_close_matches(val, allowed, n=3, cutoff=0.7)
                if len(close_matches) == 1:
                    resolved = close_matches[0]
                    notes.append(f"Fuzzy match for {field_name}: '{val}' -> '{resolved}'")
                    normalized.append(FilterCondition(field=field_name, op=op, value=resolved))
                    continue
                elif len(close_matches) > 1:
                    clarification_needed = True
                    clarification_msg = (
                        f"Ambiguous value '{val}' for field '{field_name}'. "
                        f"Candidate variants: {close_matches}"
                    )
                    notes.append(f"Ambiguous fuzzy match for {field_name}='{val}': {close_matches}")
                    normalized.append(
                        FilterCondition(field=field_name, op=op, value=close_matches[0])
                    )
                    continue

            normalized.append(cond)

        return normalized, notes, clarification_needed, clarification_msg

    def plan(self, question: str) -> PlannerResult:
        """Translate user question into a validated QueryPlan."""
        tool_schema = QueryPlan.model_json_schema()
        tool_name = "QueryPlan"
        tool_description = (
            "Formulate a structured deterministic query plan for "
            "NASA/JAXA microgravity combustion data."
        )

        user_prompt = f"Question: {question}"

        # Attempt 1: Call LLM with tool
        try:
            resp = self.llm_client.complete_structured(
                system_prompt=self._rendered_system_prompt,
                user_message=user_prompt,
                tool_name=tool_name,
                tool_description=tool_description,
                tool_schema=tool_schema,
            )
            raw_args = resp.arguments
        except Exception as err:
            logger.warning("LLM completion failed: %s", err)
            return PlannerResult(
                plan=QueryPlan(intent=PlanIntent.OUT_OF_SCOPE),
                clarification_needed=True,
                clarification_message=f"LLM interaction failed: {err}",
            )

        # Validate with QueryPlan model
        try:
            parsed_plan = QueryPlan.model_validate(raw_args)
        except (PlanValidationError, ValueError, Exception) as first_err:
            logger.info(
                "Plan validation failed on first attempt: %s. Retrying with error feedback...",
                first_err,
            )
            # Attempt 2: Retry once feeding back the error
            retry_message = (
                f"Question: {question}\n\n"
                f"Your previous QueryPlan was invalid and raised this error:\n{first_err}\n\n"
                f"Previous arguments:\n{json.dumps(raw_args, indent=2)}\n\n"
                f"Please correct the error and invoke QueryPlan with valid parameters."
            )
            try:
                resp2 = self.llm_client.complete_structured(
                    system_prompt=self._rendered_system_prompt,
                    user_message=retry_message,
                    tool_name=tool_name,
                    tool_description=tool_description,
                    tool_schema=tool_schema,
                )
                raw_args = resp2.arguments
                parsed_plan = QueryPlan.model_validate(raw_args)
            except Exception as second_err:
                logger.warning(
                    "Plan validation failed on second attempt: %s. Emitting out_of_scope.",
                    second_err,
                )
                return PlannerResult(
                    plan=QueryPlan(intent=PlanIntent.OUT_OF_SCOPE),
                    clarification_needed=True,
                    clarification_message=f"Validation error on retry: {second_err}",
                    raw_response=raw_args,
                )

        # Apply vocabulary normalization
        if parsed_plan.filters:
            norm_filters, notes, clar_needed, clar_msg = self.normalize_filter_values(
                parsed_plan.filters
            )
            # Reconstruct plan with normalized filters
            parsed_plan = QueryPlan(
                intent=parsed_plan.intent,
                filters=norm_filters,
                group_by=parsed_plan.group_by,
                aggregates=parsed_plan.aggregates,
                select_fields=parsed_plan.select_fields,
                sort=parsed_plan.sort,
                limit=parsed_plan.limit,
                include_modeled=parsed_plan.include_modeled,
                experiment_ids=parsed_plan.experiment_ids,
                allow_cross_family_aggregate=parsed_plan.allow_cross_family_aggregate,
            )
            return PlannerResult(
                plan=parsed_plan,
                clarification_needed=clar_needed,
                clarification_message=clar_msg,
                normalization_notes=notes,
                raw_response=raw_args,
            )

        return PlannerResult(
            plan=parsed_plan,
            raw_response=raw_args,
        )


__all__ = [
    "PlannerResult",
    "QueryPlanner",
    "format_catalog_summary",
    "load_planner_system_prompt",
]
