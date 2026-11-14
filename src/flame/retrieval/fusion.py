"""Fusion engine combining structured DuckDB retrieval with Qdrant hybrid semantic search.

Semantic retrieval is gated: used ONLY for qualitative and explain_experiment intents.
Structured retrieval remains completely authoritative for numeric lookups and aggregations.
"""

from __future__ import annotations

import logging
from typing import Any

from flame.config import Settings, get_settings
from flame.retrieval.semantic import SemanticRetriever
from flame.retrieval.store import ExperimentStore
from flame.retrieval.structured import RetrievalResult
from flame.schemas.query_plan import PlanIntent, QueryPlan

logger = logging.getLogger("flame.retrieval.fusion")


class StaleIndexError(RuntimeError):
    """Raised when the semantic index is stale relative to the Parquet dataset version."""


def fuse_retrieval(
    question: str,
    plan: QueryPlan,
    store: ExperimentStore,
    semantic_retriever: SemanticRetriever | None = None,
    settings: Settings | None = None,
) -> RetrievalResult:
    """Execute fused retrieval: structured retrieval augmented by semantic search."""
    cfg = settings or get_settings()

    # 1. Structured retrieval is always executed
    structured_result = store.execute_plan(plan)

    # 2. Gate semantic retrieval: only if enabled and intent is qualitative or explain_experiment
    if not cfg.enable_semantic_retrieval:
        return structured_result

    if plan.intent not in (PlanIntent.QUALITATIVE, PlanIntent.EXPLAIN_EXPERIMENT):
        return structured_result

    retriever = semantic_retriever or SemanticRetriever(settings=cfg)

    # 3. Check for index freshness
    manifest_sha256 = store.dataset_version.parquet_sha256
    if not retriever.verify_index_version(manifest_sha256):
        logger.warning(
            "Semantic index is stale or unindexed relative to dataset snapshot %s. "
            "Falling back to structured retrieval.",
            manifest_sha256,
        )
        return structured_result

    # 4. Perform hybrid search
    try:
        ranked_eids = retriever.search_hybrid(
            query_text=question,
            plan=plan,
            limit=cfg.semantic_top_k,
        )
    except Exception as err:
        logger.warning("Hybrid semantic search failed: %s; falling back to structured.", err)
        return structured_result

    if not ranked_eids:
        return structured_result

    # 5. Fetch full rows from DuckDB in ranked order
    cur = store.get_cursor()
    try:
        # Parameterized fetch of the matched IDs
        cur.execute(
            "SELECT * FROM experiments WHERE experiment_id IN (SELECT unnest(?))",
            [ranked_eids],
        )
        raw_rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        row_map = {}
        for raw_tuple in raw_rows:
            d = dict(zip(col_names, raw_tuple, strict=True))
            row_map[d["experiment_id"]] = d

        # Order rows by semantic rank
        ordered_rows: list[dict[str, Any]] = []
        for eid in ranked_eids:
            if eid in row_map:
                item = row_map[eid]
                item["is_modeled"] = bool(item.get("is_modeled", False))
                flags = item.get("data_quality_flags")
                item["data_quality_flags"] = list(flags) if isinstance(flags, (list, tuple)) else []
                ordered_rows.append(item)
    finally:
        cur.close()

    # Prepend or substitute semantic rows
    fused_rows: list[dict[str, Any]] = list(ordered_rows)
    # Append any structured rows that weren't in semantic top-k
    seen_eids = set(ranked_eids)
    for struct_row in structured_result.rows:
        if struct_row["experiment_id"] not in seen_eids:
            fused_rows.append(struct_row)

    return RetrievalResult(
        rows=fused_rows,
        aggregates=structured_result.aggregates,
        warnings=list(structured_result.warnings),
        total_matching_rows=len(fused_rows),
    )


__all__ = [
    "StaleIndexError",
    "fuse_retrieval",
]
