"""Unit tests for ExperimentStore error branches and catalog property."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from flame.retrieval.errors import ExecutionError
from flame.retrieval.store import ExperimentStore
from flame.schemas.query_plan import PlanIntent, QueryPlan


def test_store_raises_file_not_found_on_missing_parquet(tmp_path: Path) -> None:
    missing_parquet = tmp_path / "non_existent.parquet"
    with pytest.raises(FileNotFoundError, match="Parquet snapshot not found"):
        ExperimentStore(parquet_path=missing_parquet)


def test_store_fallback_when_manifest_missing(tmp_path: Path) -> None:
    # Use real parquet but missing manifest
    missing_manifest = tmp_path / "missing_manifest.json"
    with ExperimentStore(manifest_path=missing_manifest) as store:
        v = store.dataset_version
        assert v.total_rows == 892
        assert v.manifest_path is None
        assert v.git_commit is None


def test_store_fallback_when_manifest_corrupted(tmp_path: Path) -> None:
    corrupt_manifest = tmp_path / "corrupt.json"
    corrupt_manifest.write_text("{invalid json", encoding="utf-8")
    with ExperimentStore(manifest_path=corrupt_manifest) as store:
        v = store.dataset_version
        assert v.total_rows == 0
        assert v.manifest_path == str(corrupt_manifest)


def test_store_catalog_property_and_caching() -> None:
    with ExperimentStore() as store:
        cat1 = store.catalog
        cat2 = store.catalog
        assert cat1 is cat2  # Cached
        assert len(cat1.fields) == 44


def test_store_raises_execution_error_on_db_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    with ExperimentStore() as store:
        # Mock get_cursor to return a cursor whose execute method raises a duckdb error
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("DuckDB connection failure simulation")
        monkeypatch.setattr(store, "get_cursor", lambda: mock_cursor)

        plan = QueryPlan(intent=PlanIntent.LOOKUP)
        with pytest.raises(ExecutionError, match="Database execution failed"):
            store.execute_plan(plan)
