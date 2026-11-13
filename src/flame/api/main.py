"""FastAPI application factory, lifespan management, and global exception handlers."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from flame.api.middleware import RequestContextMiddleware
from flame.api.rate_limit import InMemoryRateLimiter
from flame.api.routes import router
from flame.config import Settings, get_settings
from flame.llm.anthropic_client import AnthropicClient
from flame.llm.client import LLMClient
from flame.observability.logging import configure_logging, get_request_id
from flame.retrieval.errors import PlanValidationError
from flame.retrieval.store import ExperimentStore

logger = logging.getLogger("flame.api")


def _get_active_request_id(request: Request) -> str:
    """Retrieve active correlation ID from request state, context, or headers."""
    return get_request_id() or request.headers.get("x-request-id") or "req_unknown"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application resources: DuckDB store and LLM client."""
    settings: Settings = getattr(app.state, "settings", None) or get_settings()
    app.state.settings = settings
    configure_logging(level=settings.log_level)

    logger.info("Initializing ExperimentStore from %s", settings.dataset_output_path)
    store = ExperimentStore(settings=settings)
    app.state.store = store

    # Initialize rate limiter
    app.state.rate_limiter = InMemoryRateLimiter(requests_per_minute=settings.rate_limit_per_minute)

    # Initialize LLM client if API key is provided
    if not hasattr(app.state, "llm_client") or app.state.llm_client is None:
        if settings.llm_api_key:
            logger.info("Configuring Anthropic LLM client (model=%s)", settings.llm_model)
            app.state.llm_client = AnthropicClient(
                settings=settings,
                model=settings.llm_model,
            )
        else:
            logger.warning("No LLM API key configured; /ask will be unavailable.")
            app.state.llm_client = None

    yield

    logger.info("Closing ExperimentStore")
    store.close()


def create_app(
    settings: Settings | None = None,
    llm_client: LLMClient | None = None,
) -> FastAPI:
    """Application factory for the Flame in Freefall API."""
    cfg = settings or get_settings()

    app = FastAPI(
        title=cfg.app_name,
        version=cfg.app_version,
        description=(
            "Deterministic structured retrieval and grounded RAG API for "
            "NASA/JAXA microgravity combustion experiment data."
        ),
        lifespan=lifespan,
    )

    # Store custom overrides in state
    app.state.settings = cfg
    if llm_client is not None:
        app.state.llm_client = llm_client

    # Initialize store and rate limiter on the app instance
    app.state.store = ExperimentStore(settings=cfg)
    app.state.rate_limiter = InMemoryRateLimiter(requests_per_minute=cfg.rate_limit_per_minute)

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # 2. Custom Request Context and Structured Access Logging Middleware
    app.add_middleware(RequestContextMiddleware)

    # 3. Global Exception Handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        req_id = _get_active_request_id(request)
        error_code = f"HTTP_{exc.status_code}"
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            error_code = "NOT_FOUND"
        elif exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            error_code = "RATE_LIMIT_EXCEEDED"
        elif exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            error_code = "SERVICE_UNAVAILABLE"

        headers = {"x-request-id": req_id}
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": error_code,
                "message": str(exc.detail),
                "request_id": req_id,
            },
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        req_id = _get_active_request_id(request)
        headers = {"x-request-id": req_id}
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error_code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "request_id": req_id,
                "details": exc.errors(),
            },
            headers=headers,
        )

    @app.exception_handler(PlanValidationError)
    async def plan_validation_exception_handler(
        request: Request, exc: PlanValidationError
    ) -> JSONResponse:
        req_id = _get_active_request_id(request)
        headers = {"x-request-id": req_id}
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error_code": "INVALID_QUERY_PLAN",
                "message": str(exc),
                "request_id": req_id,
            },
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = _get_active_request_id(request)
        logger.exception("Unhandled server error: %s", exc)
        headers = {"x-request-id": req_id}
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
                "request_id": req_id,
            },
            headers=headers,
        )

    # 4. Include API routers
    app.include_router(router)

    return app


# Default app instance for ASGI servers like uvicorn
app = create_app()

__all__ = ["app", "create_app"]
