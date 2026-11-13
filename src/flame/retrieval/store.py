"""DuckDB-backed experiment store for deterministic retrieval over the Parquet snapshot."""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Any

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from flame.config import Settings, get_settings
from flame.retrieval.catalog import FieldCatalog, build_field_catalog
from flame.retrieval.errors import ExecutionError
from flame.retrieval.structured import RetrievalResult, execute_plan
from flame.schemas.query_plan import QueryPlan


class DatasetVersionInfo(BaseModel):
    """Dataset version and provenance information loaded from the manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    git_commit: str | None = Field(
        default=None, description="Git commit hash when the snapshot was generated."
    )
    generated_at: str | None = Field(
        default=None, description="ISO timestamp of snapshot generation."
    )
    parquet_path: str = Field(description="Filesystem path of the Parquet snapshot.")
    manifest_path: str | None = Field(
        default=None, description="Filesystem path of provenance manifest."
    )
    parquet_sha256: str | None = Field(
        default=None, description="SHA256 checksum of the Parquet snapshot."
    )
    total_rows: int = Field(default=0, description="Total rows in the snapshot.")
    raw_rebuild_rows: int = Field(default=0, description="Rows rebuilt from raw sources.")
    canonical_legacy_rows: int = Field(
        default=0, description="Rows carried from legacy canonical data."
    )
    flags: dict[str, int] = Field(default_factory=dict, description="Quality flag counts.")
    source_policy: dict[str, list[str]] = Field(
        default_factory=dict, description="Mapping of source policies to dataset families."
    )


class ExperimentStore:
    """Thread-safe, read-only DuckDB store querying the validated Parquet snapshot.

    Maintains one master DuckDB connection and creates a fresh cursor for each
    query request to avoid serializing queries across threads.
    """

    def __init__(
        self,
        parquet_path: Path | str | None = None,
        manifest_path: Path | str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self.parquet_path = Path(parquet_path) if parquet_path else cfg.dataset_output_path
        self.manifest_path = Path(manifest_path) if manifest_path else cfg.provenance_manifest_path

        if not self.parquet_path.is_file():
            raise FileNotFoundError(f"Parquet snapshot not found: {self.parquet_path}")

        # Open one DuckDB connection in memory and create a read-only view over Parquet
        self._conn = duckdb.connect(database=":memory:")
        self._table_name = "experiments"
        parquet_posix = self.parquet_path.as_posix()
        self._conn.execute(
            f"CREATE VIEW {self._table_name} AS SELECT * FROM read_parquet('{parquet_posix}')"
        )

        # Load dataset version information from the provenance manifest
        self._dataset_version = self._load_manifest_version()
        self._catalog: FieldCatalog | None = None

    def _load_manifest_version(self) -> DatasetVersionInfo:
        """Load and parse provenance manifest metadata if available."""
        if not self.manifest_path.is_file():
            # If no manifest, count rows directly from DuckDB
            cur = self._conn.cursor()
            try:
                res = cur.execute(f"SELECT COUNT(*) FROM {self._table_name}").fetchone()
                row_count = int(res[0]) if res is not None else 0
            finally:
                cur.close()

            return DatasetVersionInfo(
                parquet_path=str(self.parquet_path),
                total_rows=row_count,
            )

        try:
            with self.manifest_path.open("r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
        except Exception:
            return DatasetVersionInfo(
                parquet_path=str(self.parquet_path),
                manifest_path=str(self.manifest_path),
            )

        row_counts = data.get("row_counts", {})
        total_rows = int(row_counts.get("total", 0))
        raw_rebuild_rows = int(row_counts.get("raw_rebuild", 0))
        canonical_legacy_rows = int(row_counts.get("canonical_legacy", 0))
        flags = {str(k): int(v) for k, v in data.get("flags", {}).items()}
        source_policy = {
            str(k): [str(x) for x in v]
            for k, v in data.get("source_policy", {}).items()
            if isinstance(v, list)
        }

        # Look up parquet sha256 if present in outputs section
        outputs = data.get("outputs", {})
        sha256_val = outputs.get("parquet_sha256") if isinstance(outputs, dict) else None

        return DatasetVersionInfo(
            git_commit=data.get("git_commit"),
            generated_at=data.get("generated_at"),
            parquet_path=str(self.parquet_path),
            manifest_path=str(self.manifest_path),
            parquet_sha256=sha256_val,
            total_rows=total_rows,
            raw_rebuild_rows=raw_rebuild_rows,
            canonical_legacy_rows=canonical_legacy_rows,
            flags=flags,
            source_policy=source_policy,
        )

    @property
    def dataset_version(self) -> DatasetVersionInfo:
        """Structured version and provenance metadata from the manifest."""
        return self._dataset_version

    @property
    def catalog(self) -> FieldCatalog:
        """Cached field catalog describing all snapshot columns, types, and values."""
        if self._catalog is None:
            cur = self.get_cursor()
            try:
                self._catalog = build_field_catalog(cur, table_name=self._table_name)
            finally:
                cur.close()
        return self._catalog

    def get_cursor(self) -> duckdb.DuckDBPyConnection:
        """Create a fresh cursor from the underlying DuckDB connection."""
        return self._conn.cursor()

    def execute_plan(self, plan: QueryPlan) -> RetrievalResult:
        """Execute a QueryPlan using a fresh cursor per request."""
        cur = self.get_cursor()
        try:
            return execute_plan(cur, plan, table_name=self._table_name)
        except Exception as err:
            if isinstance(err, (duckdb.Error, RuntimeError)):
                raise ExecutionError(f"Database execution failed: {err}") from err
            raise
        finally:
            cur.close()

    def close(self) -> None:
        """Close the underlying DuckDB connection."""
        self._conn.close()

    def __enter__(self) -> ExperimentStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()


__all__ = [
    "DatasetVersionInfo",
    "ExperimentStore",
]
