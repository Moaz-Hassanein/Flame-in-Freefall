"""RAG modules: structured query planning, generation, guardrails, and pipeline."""

from __future__ import annotations

from flame.rag.generator import AnswerGenerator, GeneratorResult
from flame.rag.guardrails import GuardrailResult, run_guardrails
from flame.rag.pipeline import PipelineConfig, ask
from flame.rag.planner import (
    PlannerResult,
    QueryPlanner,
    format_catalog_summary,
    load_planner_system_prompt,
)
from flame.schemas.answer import AnswerStatus, AskResponse, CitationRecord

__all__ = [
    "AnswerGenerator",
    "AnswerStatus",
    "AskResponse",
    "CitationRecord",
    "GeneratorResult",
    "GuardrailResult",
    "PipelineConfig",
    "PlannerResult",
    "QueryPlanner",
    "ask",
    "format_catalog_summary",
    "load_planner_system_prompt",
    "run_guardrails",
]
