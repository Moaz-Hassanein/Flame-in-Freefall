"""Grounded answer generator: formats evidence and calls LLM with AnswerContent tool.

Caps evidence rows at EVIDENCE_ROW_CAP and formats them into a compact
summary for the LLM context window. The generator only calls the LLM for
intents that require text synthesis (lookup, aggregate, explain_experiment,
qualitative). It never calls the LLM for out_of_scope or clarification_needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flame.llm.client import LLMClient, LLMError, TokenUsage
from flame.retrieval.structured import AggregateResult, RetrievalResult
from flame.schemas.query_plan import QueryPlan

logger = logging.getLogger(__name__)

EVIDENCE_ROW_CAP = 20

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
GENERATOR_PROMPT_PATH = PROMPTS_DIR / "generator_system.txt"

# Fields included in the evidence summary sent to the LLM
_SUMMARY_FIELDS = (
    "experiment_id",
    "dataset_family",
    "investigation_id",
    "fuel_material",
    "gravity_condition",
    "oxygen_pct",
    "pressure_kpa",
    "initial_diameter_mm",
    "extinction_diameter_mm",
    "burning_rate_mms",
    "airflow_velocity_cms",
    "burn_time_s",
    "extinction_outcome",
    "is_modeled",
    "notes",
    "sample_description",
    "source_url",
    "data_quality_flags",
)


def load_generator_system_prompt() -> str:
    """Load the versioned generator prompt template from disk."""
    if not GENERATOR_PROMPT_PATH.exists():
        raise FileNotFoundError(f"Generator prompt template not found at {GENERATOR_PROMPT_PATH}")
    return GENERATOR_PROMPT_PATH.read_text(encoding="utf-8")


def _format_row(row: dict[str, Any]) -> str:
    """Format a single evidence row as a compact key=value string."""
    parts: list[str] = []
    for key in _SUMMARY_FIELDS:
        val = row.get(key)
        if val is None:
            continue
        if isinstance(val, list):
            if val:
                parts.append(f"{key}={val}")
        elif isinstance(val, bool):
            parts.append(f"{key}={val}")
        elif isinstance(val, float):
            parts.append(f"{key}={val:.4g}")
        else:
            parts.append(f"{key}={val!r}")
    return "  " + ", ".join(parts)


def format_evidence_summary(rows: list[dict[str, Any]], cap: int = EVIDENCE_ROW_CAP) -> str:
    """Format evidence rows as a numbered list for the generator prompt."""
    if not rows:
        return "(no rows retrieved)"
    capped = rows[:cap]
    lines: list[str] = []
    for i, row in enumerate(capped, start=1):
        lines.append(f"{i}. {_format_row(row)}")
    return "\n".join(lines)


def format_aggregate_summary(aggregates: list[AggregateResult]) -> str:
    """Format computed aggregates as a readable list for the generator prompt."""
    if not aggregates:
        return "(no aggregates computed)"
    lines: list[str] = []
    for agg in aggregates:
        group_str = ""
        if agg.group_key:
            kv = ", ".join(f"{k}={v!r}" for k, v in agg.group_key.items())
            group_str = f" [group: {kv}]"
        val_str = str(agg.value) if agg.value is not None else "NULL"
        excl_parts: list[str] = []
        if agg.n_null_excluded > 0:
            excl_parts.append(f"{agg.n_null_excluded} null excluded")
        if agg.n_quarantined_excluded > 0:
            excl_parts.append(f"{agg.n_quarantined_excluded} quarantined excluded")
        excl_str = f" ({', '.join(excl_parts)})" if excl_parts else ""
        lines.append(
            f"- {agg.fn}({agg.field}){group_str} = {val_str}  [n_used={agg.n_used}{excl_str}]"
        )
    return "\n".join(lines)


# JSON schema for the AnswerContent tool
_ANSWER_CONTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer_text": {
            "type": "string",
            "description": (
                "Complete markdown answer with inline [EXP-ID] citation markers. "
                "Every number must come from the evidence or aggregates."
            ),
        },
        "cited_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of experiment_id strings cited in the answer.",
        },
        "limitations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Explicit limitations the user should be aware of.",
        },
    },
    "required": ["answer_text", "cited_ids", "limitations"],
    "additionalProperties": False,
}


@dataclass
class GeneratorResult:
    """Output of the AnswerGenerator."""

    answer_text: str
    cited_ids: list[str]
    limitations: list[str]
    usage: TokenUsage = field(default_factory=TokenUsage)


class AnswerGenerator:
    """Calls the LLM with capped evidence and aggregates to produce a grounded answer."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client
        self._system_prompt_template = load_generator_system_prompt()

    def generate(
        self,
        question: str,
        plan: QueryPlan,
        retrieval_result: RetrievalResult,
        caveats: list[str],
    ) -> GeneratorResult:
        """Generate a grounded answer from evidence rows and computed aggregates.

        Caps evidence rows at EVIDENCE_ROW_CAP and always adds a limitation if
        truncation occurs. Never invents content; relies on the LLM following
        the prompt rules plus downstream guardrails.
        """
        rows = retrieval_result.rows
        cap = EVIDENCE_ROW_CAP
        truncated = len(rows) > cap

        evidence_summary = format_evidence_summary(rows, cap=cap)
        aggregate_summary = format_aggregate_summary(retrieval_result.aggregates)
        caveats_text = "\n".join(f"- {c}" for c in caveats) if caveats else "(none)"

        system_prompt = (
            self._system_prompt_template.replace("{{question}}", question)
            .replace("{{evidence_summary}}", evidence_summary)
            .replace("{{aggregate_summary}}", aggregate_summary)
            .replace("{{caveats}}", caveats_text)
        )

        try:
            resp = self.llm_client.complete_structured(
                system_prompt=system_prompt,
                user_message=f"Question: {question}",
                tool_name="AnswerContent",
                tool_description=(
                    "Provide the grounded answer text with inline citations, "
                    "the list of cited experiment IDs, and any stated limitations."
                ),
                tool_schema=_ANSWER_CONTENT_SCHEMA,
                max_tokens=4096,
            )
        except LLMError:
            raise

        args = resp.arguments
        answer_text = str(args.get("answer_text", ""))
        cited_ids: list[str] = [str(x) for x in args.get("cited_ids", [])]
        limitations: list[str] = [str(x) for x in args.get("limitations", [])]

        if truncated:
            limitations.append(
                f"Evidence was capped at {cap} rows "
                f"(total matching: {retrieval_result.total_matching_rows}). "
                "Some experiments may not be reflected in this answer."
            )

        return GeneratorResult(
            answer_text=answer_text,
            cited_ids=cited_ids,
            limitations=limitations,
            usage=resp.usage,
        )


__all__ = [
    "EVIDENCE_ROW_CAP",
    "AnswerGenerator",
    "GeneratorResult",
    "format_aggregate_summary",
    "format_evidence_summary",
    "load_generator_system_prompt",
]
