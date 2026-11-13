"""HTTP API request models, response models, and error schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from flame.retrieval.catalog import FieldCatalog
from flame.retrieval.store import DatasetVersionInfo
from flame.schemas.answer import AskResponse


class ErrorResponse(BaseModel):
    """Standard error response format across all API endpoints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error_code: str = Field(description="Machine-readable error classification code.")
    message: str = Field(description="Human-readable explanation of the error.")
    request_id: str = Field(description="Correlation request identifier.")


class AskRequest(BaseModel):
    """Request body for the /ask endpoint."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        min_length=1,
        max_length=1000,
        description="Natural-language question about microgravity combustion experiments.",
    )


class HealthResponse(BaseModel):
    """Liveness probe response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(default="ok", description="Liveness status.")


class ReadyResponse(BaseModel):
    """Readiness probe response verifying storage and LLM configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(description="Readiness status ('ready' or 'not_ready').")
    dataset_loaded: bool = Field(description="True if Parquet snapshot is readable.")
    manifest_loaded: bool = Field(description="True if provenance manifest is loaded.")
    total_rows: int = Field(description="Total rows in the snapshot.")
    llm_configured: bool = Field(description="True if LLM provider and API key are configured.")


class PaginatedExperimentsResponse(BaseModel):
    """Paginated listing of experiments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[dict[str, Any]] = Field(description="List of experiment records.")
    total: int = Field(description="Total matching rows.")
    limit: int = Field(description="Pagination page size limit.")
    offset: int = Field(description="Pagination offset.")


class MetaResponse(BaseModel):
    """Dataset metadata, versions, and frontend display constraints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version_info: DatasetVersionInfo = Field(description="Provenance manifest metadata.")
    field_catalog: FieldCatalog = Field(
        description="Column definitions, units, and allowed values."
    )
    dataset_families: list[str] = Field(
        description="Distinct dataset families present in snapshot."
    )
    modeled_rows_count: int = Field(description="Count of rows marked with is_modeled=True.")
    data_limitations: list[str] = Field(
        description="Summary of critical scientific caveats for UI display."
    )


__all__ = [
    "AskRequest",
    "AskResponse",
    "ErrorResponse",
    "HealthResponse",
    "MetaResponse",
    "PaginatedExperimentsResponse",
    "ReadyResponse",
]
