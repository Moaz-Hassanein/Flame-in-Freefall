"""FastAPI endpoints under /api/v1."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from flame.api.rate_limit import InMemoryRateLimiter
from flame.api.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    MetaResponse,
    PaginatedExperimentsResponse,
    ReadyResponse,
)
from flame.llm.client import LLMClient
from flame.observability.logging import get_request_id
from flame.rag.pipeline import ask
from flame.retrieval.store import ExperimentStore
from flame.schemas.query_plan import FilterCondition, FilterOperator, PlanIntent, QueryPlan

logger = logging.getLogger("flame.api.routes")

router = APIRouter(prefix="/api/v1")


def get_store(request: Request) -> ExperimentStore:
    return request.app.state.store  # type: ignore[no-any-return]


def get_llm_client(request: Request) -> LLMClient | None:
    return getattr(request.app.state, "llm_client", None)


def get_rate_limiter(request: Request) -> InMemoryRateLimiter:
    return request.app.state.rate_limiter  # type: ignore[no-any-return]


StoreDep = Annotated[ExperimentStore, Depends(get_store)]
LimiterDep = Annotated[InMemoryRateLimiter, Depends(get_rate_limiter)]


@router.get("/health", response_model=HealthResponse, tags=["Observability"])
def health() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse, tags=["Observability"])
def ready(request: Request, store: StoreDep) -> ReadyResponse:
    """Readiness probe checking snapshot accessibility and manifest."""
    manifest_loaded = store.dataset_version.manifest_path is not None
    total_rows = store.dataset_version.total_rows
    dataset_loaded = total_rows > 0
    llm_configured = get_llm_client(request) is not None

    is_ready = dataset_loaded and manifest_loaded
    return ReadyResponse(
        status="ready" if is_ready else "not_ready",
        dataset_loaded=dataset_loaded,
        manifest_loaded=manifest_loaded,
        total_rows=total_rows,
        llm_configured=llm_configured,
    )


@router.get("/meta", response_model=MetaResponse, tags=["Metadata"])
def get_meta(store: StoreDep) -> MetaResponse:
    """Return dataset metadata, catalog definitions, and UI constraints."""
    catalog = store.catalog
    version_info = store.dataset_version

    # Collect distinct dataset families
    fam_field = catalog.get_field("dataset_family")
    families = (
        [str(v) for v in (fam_field.allowed_values or []) if v is not None]
        if fam_field and fam_field.allowed_values
        else []
    )

    # Modeled rows count from store
    cur = store.get_cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM experiments WHERE is_modeled = true")
        res = cur.fetchone()
        modeled_count = int(res[0]) if res is not None else 0
    finally:
        cur.close()

    data_limitations = [
        "Modeled rows (is_modeled=True) originate from computational extrapolations "
        "(Partial-g Bounded, LUCI / FM2) and are not measured physical experiments.",
        "42 BASS-II experiments had anomalous airflow velocity readings (>1000 cm/s) "
        "and were quarantined to NULL (AIRFLOW_QUARANTINED).",
        "burning_rate_mms is semantically incomparable across dataset families "
        "(droplet regression vs solid slab spread vs foam smolder).",
        "Only NASA/JAXA microgravity combustion datasets indexed in Flame in Freefall are queried.",
    ]

    return MetaResponse(
        version_info=version_info,
        field_catalog=catalog,
        dataset_families=families,
        modeled_rows_count=modeled_count,
        data_limitations=data_limitations,
    )


@router.get("/experiments", response_model=PaginatedExperimentsResponse, tags=["Experiments"])
def list_experiments(
    store: StoreDep,
    dataset_family: str | None = Query(None, description="Filter by dataset family."),
    fuel_material: str | None = Query(None, description="Filter by fuel material."),
    is_modeled: bool | None = Query(None, description="Filter modeled status."),
    limit: int = Query(50, ge=1, le=1000, description="Page limit."),
    offset: int = Query(0, ge=0, description="Page offset."),
) -> PaginatedExperimentsResponse:
    """Filtered, paginated experiment records using QueryPlan validation."""
    filters: list[FilterCondition] = []
    if dataset_family:
        filters.append(
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value=dataset_family)
        )
    if fuel_material:
        filters.append(
            FilterCondition(field="fuel_material", op=FilterOperator.EQ, value=fuel_material)
        )
    if is_modeled is not None:
        filters.append(FilterCondition(field="is_modeled", op=FilterOperator.EQ, value=is_modeled))

    plan = QueryPlan(
        intent=PlanIntent.LOOKUP,
        filters=filters,
        limit=offset + limit,
        include_modeled=is_modeled is True,
    )

    result = store.execute_plan(plan)
    # Apply offset slicing over result rows
    paged_rows = result.rows[offset : offset + limit]

    # Total matching rows for query filters without limit
    count_plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=filters,
        aggregates=[{"fn": "count", "field": "experiment_id"}],
        include_modeled=is_modeled is True,
    )
    count_result = store.execute_plan(count_plan)
    total_count = (
        int(count_result.aggregates[0].value or 0) if count_result.aggregates else len(result.rows)
    )

    return PaginatedExperimentsResponse(
        items=paged_rows,
        total=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/experiments/{experiment_id}", response_model=dict[str, Any], tags=["Experiments"])
def get_experiment_by_id(
    experiment_id: str,
    store: StoreDep,
) -> dict[str, Any]:
    """Retrieve full experiment record with provenance links and flags."""
    plan = QueryPlan(
        intent=PlanIntent.EXPLAIN_EXPERIMENT,
        experiment_ids=[experiment_id],
        include_modeled=True,
    )
    result = store.execute_plan(plan)
    if not result.rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found.",
        )
    return result.rows[0]


@router.post("/ask", response_model=AskResponse, tags=["RAG"])
def ask_question(
    body: AskRequest,
    request: Request,
    store: StoreDep,
    limiter: LimiterDep,
) -> AskResponse:
    """Process natural-language question through the RAG pipeline."""
    # 1. Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    allowed, _ = limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before making more requests.",
        )

    # 2. Check LLM client configuration
    llm = get_llm_client(request)
    if llm is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM client is not configured on this server.",
        )

    cfg = request.app.state.settings
    truncated_question = (
        body.question[: cfg.max_log_text_length]
        if len(body.question) > cfg.max_log_text_length
        else body.question
    )

    req_id = get_request_id() or "unknown"
    logger.info(
        "Processing /ask: %s",
        truncated_question,
        extra={"request_id": req_id, "question_length": len(body.question)},
    )

    # 3. Call pipeline.ask
    try:
        response = ask(
            question=body.question,
            llm_client=llm,
            store=store,
            catalog=store.catalog,
        )
    except Exception as err:
        logger.exception("Unexpected error inside pipeline: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the question.",
        ) from err

    # 4. Structured ask logging
    logger.info(
        "Ask completed: status=%s, rows_retrieved=%d, latency=%.2fs",
        response.status.value,
        len(response.evidence),
        response.timings.get("total_s", 0.0),
        extra={
            "request_id": req_id,
            "status": response.status.value,
            "evidence_count": len(response.evidence),
            "citations_count": len(response.citations),
            "timings": response.timings,
        },
    )

    return response


__all__ = ["router"]
