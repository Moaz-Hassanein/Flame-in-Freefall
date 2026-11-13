"""End-to-end RAG pipeline: plan → retrieve → generate → guard → assemble.

The ask() function is the single entry point. It orchestrates all pipeline
stages and always returns a typed AskResponse — never raises to the caller.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from flame.llm.client import LLMClient, LLMError
from flame.rag.generator import EVIDENCE_ROW_CAP, AnswerGenerator
from flame.rag.guardrails import run_guardrails
from flame.rag.planner import QueryPlanner
from flame.retrieval.catalog import FieldCatalog
from flame.retrieval.store import ExperimentStore
from flame.retrieval.structured import AggregateResult
from flame.schemas.answer import AnswerStatus, AskResponse, CitationRecord
from flame.schemas.query_plan import PlanIntent

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Runtime configuration for the ask() pipeline."""

    evidence_row_cap: int = EVIDENCE_ROW_CAP


def _build_caveats(
    plan_intent: PlanIntent,
    include_modeled: bool,
    aggregates: list[AggregateResult],
    catalog: FieldCatalog,
) -> list[str]:
    """Compile the list of data caveats to inject into the generator prompt."""
    caveats: list[str] = []

    if include_modeled:
        caveats.append(
            "Some evidence rows are MODELED (is_modeled=True), not directly measured. "
            "These come from the 'Partial-g Bounded' and 'LUCI / FM2 (Future Partial-g)' "
            "families. The answer must clearly label modeled data as such."
        )

    has_airflow_null = any(
        agg.field == "airflow_velocity_cms" and agg.n_null_excluded > 0 for agg in aggregates
    )
    if has_airflow_null:
        caveats.append(
            "airflow_velocity_cms is NULL for 42 BASS-II rows where raw readings exceeded "
            "1000 cm/s and were quarantined as unreliable (flag: AIRFLOW_QUARANTINED). "
            "These rows are excluded from airflow aggregates."
        )

    has_burning_rate = any(agg.field == "burning_rate_mms" for agg in aggregates)
    if has_burning_rate:
        caveats.append(
            "burning_rate_mms is semantically different across dataset families: "
            "droplet regression in FLEX, solid slab spread in BASS-II, smoldering foam in others. "
            "Do not compare this value across families."
        )

    caveats.append(
        "Only experiments in the Flame in Freefall dataset are indexed. "
        "No external literature or other databases are queried."
    )

    return caveats


def _lookup_citation_meta(
    experiment_id: str, evidence_rows: list[dict[str, Any]]
) -> CitationRecord:
    """Build a CitationRecord from evidence rows for a given experiment_id."""
    for row in evidence_rows:
        if str(row.get("experiment_id", "")) == experiment_id:
            src_url = row.get("source_url")
            inv_id = row.get("investigation_id")
            fam = row.get("dataset_family")
            return CitationRecord(
                experiment_id=experiment_id,
                source_url=str(src_url) if src_url is not None else None,
                investigation_id=str(inv_id) if inv_id is not None else None,
                dataset_family=str(fam) if fam is not None else None,
            )
    # Fallback: ID was cited but row not in evidence (should not happen post-guardrails)
    return CitationRecord(experiment_id=experiment_id)


def ask(
    question: str,
    llm_client: LLMClient,
    store: ExperimentStore,
    catalog: FieldCatalog,
    config: PipelineConfig | None = None,
) -> AskResponse:
    """Execute the full RAG pipeline and return a typed AskResponse.

    Stages:
    1. PLAN — translate question to QueryPlan via LLM
    2. RETRIEVE — execute plan against DuckDB store
    3. GENERATE — call LLM with capped evidence to produce grounded answer
    4. GUARDRAILS — verify citations and numeric grounding deterministically
    5. ASSEMBLE — build AskResponse with all metadata

    Never raises; maps all errors to AnswerStatus.error or appropriate status.
    """
    cfg = config or PipelineConfig()
    t0 = time.monotonic()
    timings: dict[str, float] = {}

    # Dataset version for traceability
    version_info = store.dataset_version
    dataset_version: str | None = None
    if version_info.parquet_sha256:
        dataset_version = version_info.parquet_sha256[:8]

    # ── 1. PLAN ──────────────────────────────────────────────────────────────
    try:
        planner = QueryPlanner(llm_client=llm_client, catalog=catalog, store=store)
        plan_result = planner.plan(question)
    except Exception as err:
        logger.exception("Planning stage failed: %s", err)
        timings["total_s"] = time.monotonic() - t0
        return AskResponse(
            question=question,
            status=AnswerStatus.error,
            limitations=[f"Planning failed: {err}"],
            dataset_version=dataset_version,
            timings=timings,
        )

    timings["plan_s"] = time.monotonic() - t0

    # ── 2. Early exits before retrieval ──────────────────────────────────────
    if plan_result.clarification_needed:
        timings["total_s"] = time.monotonic() - t0
        msg = plan_result.clarification_message or "Clarification required."
        return AskResponse(
            question=question,
            answer_markdown=msg,
            plan=plan_result.plan.model_dump(),
            status=AnswerStatus.clarification_needed,
            limitations=[],
            warnings=plan_result.normalization_notes,
            dataset_version=dataset_version,
            timings=timings,
        )

    if plan_result.plan.intent == PlanIntent.OUT_OF_SCOPE:
        timings["total_s"] = time.monotonic() - t0
        return AskResponse(
            question=question,
            answer_markdown=(
                "This question is outside the scope of the Flame in Freefall dataset. "
                "Only questions about indexed microgravity combustion experiments can be answered."
            ),
            plan=plan_result.plan.model_dump(),
            status=AnswerStatus.out_of_scope,
            limitations=[],
            warnings=plan_result.normalization_notes,
            dataset_version=dataset_version,
            timings=timings,
        )

    # ── 3. RETRIEVE ───────────────────────────────────────────────────────────
    t_retrieve = time.monotonic()
    try:
        retrieval_result = store.execute_plan(plan_result.plan)
    except Exception as err:
        logger.exception("Retrieval stage failed: %s", err)
        timings["total_s"] = time.monotonic() - t0
        return AskResponse(
            question=question,
            plan=plan_result.plan.model_dump(),
            status=AnswerStatus.error,
            limitations=[f"Retrieval failed: {err}"],
            dataset_version=dataset_version,
            timings=timings,
        )

    timings["retrieval_s"] = time.monotonic() - t_retrieve

    # Zero rows and zero aggregates → insufficient evidence
    if retrieval_result.is_empty:
        timings["total_s"] = time.monotonic() - t0
        return AskResponse(
            question=question,
            plan=plan_result.plan.model_dump(),
            status=AnswerStatus.insufficient_evidence,
            limitations=["No matching experiments found in the dataset."],
            warnings=list(retrieval_result.warnings),
            dataset_version=dataset_version,
            timings=timings,
        )

    # ── 4. BUILD CAVEATS ─────────────────────────────────────────────────────
    caveats = _build_caveats(
        plan_result.plan.intent,
        plan_result.plan.include_modeled,
        retrieval_result.aggregates,
        catalog,
    )

    # ── 5. GENERATE ───────────────────────────────────────────────────────────
    t_generate = time.monotonic()
    generator = AnswerGenerator(llm_client=llm_client)
    try:
        gen_result = generator.generate(
            question=question,
            plan=plan_result.plan,
            retrieval_result=retrieval_result,
            caveats=caveats,
        )
    except LLMError as err:
        logger.warning("Generation LLM call failed: %s", err)
        timings["generate_s"] = time.monotonic() - t_generate
        timings["total_s"] = time.monotonic() - t0
        return AskResponse(
            question=question,
            plan=plan_result.plan.model_dump(),
            evidence=retrieval_result.rows[: cfg.evidence_row_cap],
            aggregates=[a.model_dump() for a in retrieval_result.aggregates],
            status=AnswerStatus.error,
            limitations=[f"Answer generation failed: {err}"],
            warnings=list(retrieval_result.warnings),
            dataset_version=dataset_version,
            timings=timings,
        )
    except Exception as err:
        logger.exception("Unexpected error in generation: %s", err)
        timings["generate_s"] = time.monotonic() - t_generate
        timings["total_s"] = time.monotonic() - t0
        return AskResponse(
            question=question,
            plan=plan_result.plan.model_dump(),
            evidence=retrieval_result.rows[: cfg.evidence_row_cap],
            aggregates=[a.model_dump() for a in retrieval_result.aggregates],
            status=AnswerStatus.error,
            limitations=[f"Unexpected generation error: {err}"],
            warnings=list(retrieval_result.warnings),
            dataset_version=dataset_version,
            timings=timings,
        )

    timings["generate_s"] = time.monotonic() - t_generate

    # ── 6. GUARDRAILS ─────────────────────────────────────────────────────────
    t_guard = time.monotonic()
    guard_result = run_guardrails(
        answer_text=gen_result.answer_text,
        cited_ids=gen_result.cited_ids,
        limitations=gen_result.limitations,
        evidence_rows=retrieval_result.rows,
        aggregates=retrieval_result.aggregates,
        plan=plan_result.plan,
        catalog=catalog,
    )

    # If citation guardrail failed: retry generation once with error context
    if not guard_result.passed:
        logger.info(
            "Guardrail check failed (%s failures). Retrying generation...",
            len(guard_result.failures),
        )
        try:
            retry_caveats = [
                *caveats,
                f"Previous generation had these failures: {'; '.join(guard_result.failures)}. "
                "Please ensure all cited IDs exist in the evidence rows provided.",
            ]
            gen_result2 = generator.generate(
                question=question,
                plan=plan_result.plan,
                retrieval_result=retrieval_result,
                caveats=retry_caveats,
            )
            guard_result = run_guardrails(
                answer_text=gen_result2.answer_text,
                cited_ids=gen_result2.cited_ids,
                limitations=gen_result2.limitations,
                evidence_rows=retrieval_result.rows,
                aggregates=retrieval_result.aggregates,
                plan=plan_result.plan,
                catalog=catalog,
            )
        except (LLMError, Exception) as err:
            logger.warning("Generation retry failed: %s", err)
            # Downgrade to the first (corrected) guard result
            guard_result.warnings.append(f"Generation retry failed: {err}")

    timings["guard_s"] = time.monotonic() - t_guard
    timings["total_s"] = time.monotonic() - t0

    # ── 7. ASSEMBLE ───────────────────────────────────────────────────────────
    citations: list[CitationRecord] = [
        _lookup_citation_meta(eid, retrieval_result.rows) for eid in guard_result.cited_ids
    ]

    all_warnings: list[str] = list(retrieval_result.warnings) + guard_result.warnings
    all_limitations: list[str] = guard_result.limitations

    return AskResponse(
        question=question,
        answer_markdown=guard_result.answer_text,
        citations=citations,
        evidence=retrieval_result.rows[: cfg.evidence_row_cap],
        aggregates=[a.model_dump() for a in retrieval_result.aggregates],
        plan=plan_result.plan.model_dump(),
        limitations=all_limitations,
        warnings=all_warnings,
        status=AnswerStatus.answered,
        dataset_version=dataset_version,
        timings=timings,
    )


__all__ = [
    "PipelineConfig",
    "ask",
]
