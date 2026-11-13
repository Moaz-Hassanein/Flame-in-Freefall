"""Deterministic post-generation guardrails for citation and numeric grounding.

Four mandatory checks applied after every LLM generation:
1. Citation validity  — every [EXP-ID] in text must exist in evidence rows.
2. Numeric grounding  — every number in text must match evidence/aggregate values.
3. Modeled disclosure — if modeled rows are included, text must say so.
4. Exclusion auto-caveats — null/quarantined exclusions trigger automatic limitations.
5. Cross-family semantic caveat — multi-family burning_rate_mms aggregation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from flame.retrieval.catalog import FieldCatalog
from flame.retrieval.structured import AggregateResult
from flame.schemas.query_plan import QueryPlan

logger = logging.getLogger(__name__)

# Regex to find inline citation markers like [FLEX-001] or [BASS-I-042]
_CITATION_RE = re.compile(r"\[([A-Z0-9][-A-Z0-9_/]*)\]")

# Regex to extract standalone numbers (integers and decimals)
_NUMBER_RE = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)(?!\w)")

# Field known to be semantically incomparable across dataset families
_CROSS_FAMILY_INCOMPATIBLE_FIELDS = frozenset({"burning_rate_mms"})


@dataclass
class GuardrailResult:
    """Result of running all deterministic guardrail checks."""

    answer_text: str
    cited_ids: list[str]
    limitations: list[str]
    warnings: list[str] = field(default_factory=list)
    passed: bool = True
    failures: list[str] = field(default_factory=list)


def _extract_cited_ids_from_text(text: str) -> set[str]:
    """Return all experiment IDs referenced via [EXP-ID] markers in the answer text."""
    return set(_CITATION_RE.findall(text))


def _remove_invalid_citations(
    answer_text: str,
    cited_ids: list[str],
    valid_ids: set[str],
) -> tuple[str, list[str], list[str]]:
    """Strip citations not in valid_ids from text and cited_ids list.

    Returns (cleaned_text, cleaned_cited_ids, warnings_about_removed).
    """
    warnings: list[str] = []
    all_in_text = _extract_cited_ids_from_text(answer_text)
    invalid_in_text = all_in_text - valid_ids
    invalid_in_list = set(cited_ids) - valid_ids

    removed = invalid_in_text | invalid_in_list
    if removed:
        for rid in sorted(removed):
            warnings.append(f"Citation [{rid}] removed: not found in evidence rows.")
            logger.warning("Guardrail: removed invalid citation [%s]", rid)
        # Strip invalid markers from text
        for rid in invalid_in_text:
            answer_text = answer_text.replace(f"[{rid}]", "")
        # Strip from list
        cited_ids = [cid for cid in cited_ids if cid in valid_ids]

    return answer_text, cited_ids, warnings


def _check_numeric_grounding(
    answer_text: str,
    evidence_rows: list[dict[str, Any]],
    aggregates: list[AggregateResult],
    tol: float = 1e-4,
) -> list[str]:
    """Check that every number in the answer text matches evidence or aggregates.

    Returns a list of warning strings for numbers that could not be matched.
    Year-like four-digit integers (1900-2100) are excluded from checking.
    """
    # Collect all numeric values from evidence rows
    evidence_values: set[float] = set()
    for row in evidence_rows:
        for v in row.values():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                evidence_values.add(float(v))

    # Collect from aggregates
    for agg in aggregates:
        if agg.value is not None:
            evidence_values.add(float(agg.value))
        evidence_values.add(float(agg.n_used))
        evidence_values.add(float(agg.n_null_excluded))
        evidence_values.add(float(agg.n_quarantined_excluded))

    warnings: list[str] = []
    raw_numbers = _NUMBER_RE.findall(answer_text)

    for num_str in raw_numbers:
        try:
            num = float(num_str)
        except ValueError:
            continue

        # Exclude year-like integers
        if num_str.isdigit() and 1900 <= int(num_str) <= 2100:
            continue

        # Check if this number matches any evidence value within tolerance
        matched = False
        for ev in evidence_values:
            matched = abs(num) <= tol if abs(ev) < 1e-9 else abs(num - ev) / abs(ev) <= tol
            if matched:
                break

        if not matched:
            warnings.append(
                f"Number {num_str} in answer could not be matched to evidence or aggregates "
                f"(within {tol:.0e} relative tolerance)."
            )

    return warnings


def _check_modeled_disclosure(
    answer_text: str,
    evidence_rows: list[dict[str, Any]],
) -> str | None:
    """Return a warning if modeled rows are present but the answer does not disclose it."""
    has_modeled = any(row.get("is_modeled") for row in evidence_rows)
    if not has_modeled:
        return None
    text_lower = answer_text.lower()
    if "model" not in text_lower:
        return (
            "Answer includes modeled (not measured) rows but does not disclose this. "
            "Mandatory statement appended."
        )
    return None


def _build_exclusion_limitations(aggregates: list[AggregateResult]) -> list[str]:
    """Auto-generate limitation strings from aggregate null/quarantine exclusion counts."""
    limitations: list[str] = []
    for agg in aggregates:
        parts: list[str] = []
        if agg.n_null_excluded > 0:
            parts.append(f"{agg.n_null_excluded} null value(s) excluded")
        if agg.n_quarantined_excluded > 0:
            parts.append(f"{agg.n_quarantined_excluded} quarantined value(s) excluded")
        if parts:
            group_str = ""
            if agg.group_key:
                kv = ", ".join(f"{k}={v!r}" for k, v in agg.group_key.items())
                group_str = f" (group: {kv})"
            limitations.append(
                f"{agg.fn}({agg.field}){group_str}: {', '.join(parts)} "
                "from the aggregate computation."
            )
    return limitations


def _check_cross_family_caveat(
    plan: QueryPlan,
    aggregates: list[AggregateResult],
) -> str | None:
    """Return a caveat if multi-family burning_rate_mms aggregation is detected."""
    agg_fields = {agg.field for agg in aggregates}
    if not agg_fields.intersection(_CROSS_FAMILY_INCOMPATIBLE_FIELDS):
        return None

    # Check if the plan spans multiple families (no dataset_family equality filter)
    family_filter_values: set[str] = set()
    for f in plan.filters:
        if f.field == "dataset_family":
            if isinstance(f.value, str):
                family_filter_values.add(f.value)
            elif isinstance(f.value, list):
                family_filter_values.update(str(v) for v in f.value)

    # If the plan filters to exactly one family, no caveat needed
    if len(family_filter_values) == 1:
        return None

    # Check actual group keys in results
    group_families: set[str] = set()
    for agg in aggregates:
        if agg.group_key and "dataset_family" in agg.group_key:
            fv = agg.group_key["dataset_family"]
            if fv is not None:
                group_families.add(str(fv))

    if len(group_families) > 1 or (not group_families and len(family_filter_values) != 1):
        return (
            "burning_rate_mms is semantically incomparable across dataset families: "
            "it measures droplet regression rate in FLEX, solid slab spread rate in BASS-II, "
            "and smoldering foam rate in other families. "
            "Cross-family comparisons of this field are not valid."
        )
    return None


def run_guardrails(
    answer_text: str,
    cited_ids: list[str],
    limitations: list[str],
    evidence_rows: list[dict[str, Any]],
    aggregates: list[AggregateResult],
    plan: QueryPlan,
    catalog: FieldCatalog,
) -> GuardrailResult:
    """Apply all deterministic guardrails to a generated answer.

    Checks are applied in order:
    1. Citation validity (remove invalid citations)
    2. Numeric grounding (warn on unmatched numbers)
    3. Modeled row disclosure (append mandatory statement if missing)
    4. Exclusion auto-caveats (add limitations for null/quarantine exclusions)
    5. Cross-family semantic caveat (burning_rate_mms across families)

    Returns a GuardrailResult with updated text, cited_ids, limitations, warnings,
    a passed flag, and a list of failure descriptions.
    """
    warnings: list[str] = []
    failures: list[str] = []
    limitations = list(limitations)  # make mutable copy

    # 1. Citation validity
    valid_ids: set[str] = {str(row.get("experiment_id", "")) for row in evidence_rows} - {""}
    answer_text, cited_ids, citation_warnings = _remove_invalid_citations(
        answer_text, cited_ids, valid_ids
    )
    if citation_warnings:
        warnings.extend(citation_warnings)
        failures.append(f"Invalid citations removed: {citation_warnings}")

    # 2. Numeric grounding
    numeric_warnings = _check_numeric_grounding(answer_text, evidence_rows, aggregates)
    if numeric_warnings:
        warnings.extend(numeric_warnings)
        # Numeric mismatches are warnings, not hard failures, to avoid over-rejection
        # of correctly rounded/formatted numbers
        logger.warning("Guardrail: numeric grounding warnings: %s", numeric_warnings)

    # 3. Modeled row disclosure
    modeled_warning = _check_modeled_disclosure(answer_text, evidence_rows)
    if modeled_warning is not None:
        warnings.append(modeled_warning)
        failures.append("Modeled row disclosure missing from answer.")
        answer_text += (
            "\n\n> **Note:** Some rows in the supporting evidence are "
            "**modeled** (not directly measured) and should be interpreted accordingly."
        )

    # 4. Exclusion auto-caveats
    excl_limitations = _build_exclusion_limitations(aggregates)
    limitations.extend(excl_limitations)

    # 5. Cross-family caveat
    cross_family_caveat = _check_cross_family_caveat(plan, aggregates)
    if cross_family_caveat is not None:
        limitations.append(cross_family_caveat)

    passed = len(failures) == 0

    return GuardrailResult(
        answer_text=answer_text,
        cited_ids=cited_ids,
        limitations=limitations,
        warnings=warnings,
        passed=passed,
        failures=failures,
    )


__all__ = [
    "GuardrailResult",
    "run_guardrails",
]
