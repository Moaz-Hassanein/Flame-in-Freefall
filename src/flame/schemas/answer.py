"""Answer schema for the grounded generation pipeline.

AskResponse is the final output of the ask() pipeline, containing the
generated markdown answer, citations verified by deterministic guardrails,
raw evidence rows and computed aggregates, the interpreted QueryPlan, and
rich provenance metadata.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnswerStatus(StrEnum):
    """Status of the pipeline response."""

    answered = "answered"
    insufficient_evidence = "insufficient_evidence"
    out_of_scope = "out_of_scope"
    clarification_needed = "clarification_needed"
    error = "error"


class CitationRecord(BaseModel):
    """A verified citation linking an inline marker to an experiment record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str = Field(description="Unique experiment identifier.")
    source_url: str | None = Field(default=None, description="URL of the original data source.")
    investigation_id: str | None = Field(
        default=None, description="Investigation or campaign identifier."
    )
    dataset_family: str | None = Field(
        default=None, description="Dataset family the experiment belongs to."
    )


class AskResponse(BaseModel):
    """Full pipeline response for a natural-language question.

    Produced by ask() after planning, retrieval, generation, and guardrails.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str = Field(description="The original natural-language question.")

    answer_markdown: str | None = Field(
        default=None,
        description="Grounded markdown answer with inline [EXP-ID] citation markers.",
    )

    citations: list[CitationRecord] = Field(
        default_factory=list,
        description="Verified citations for every experiment_id referenced in the answer.",
    )

    evidence: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Capped evidence rows passed to the LLM (experiment_id, key fields, etc.).",
    )

    aggregates: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Computed aggregate results (AggregateResult dumps) with exclusion counts.",
    )

    plan: dict[str, Any] = Field(
        default_factory=dict,
        description="The interpreted QueryPlan echoed back for transparency.",
    )

    limitations: list[str] = Field(
        default_factory=list,
        description="Limitations the user must be aware of (exclusions, caps, caveats).",
    )

    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings raised during retrieval or guardrails.",
    )

    status: AnswerStatus = Field(description="Pipeline outcome status.")

    dataset_version: str | None = Field(
        default=None,
        description="First 8 chars of the Parquet SHA256 for data provenance tracing.",
    )

    timings: dict[str, float] = Field(
        default_factory=dict,
        description="Wall-clock seconds for each pipeline stage (plan_s, retrieval_s, etc.).",
    )


__all__ = [
    "AskResponse",
    "AnswerStatus",
    "CitationRecord",
]
