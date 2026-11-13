"""Unit tests for FieldCatalog and metadata inspection."""

from __future__ import annotations

import duckdb
import pytest

from flame.config import get_settings
from flame.retrieval.catalog import build_field_catalog


@pytest.fixture
def cursor() -> duckdb.DuckDBPyConnection:
    settings = get_settings()
    conn = duckdb.connect(database=":memory:")
    parquet_posix = settings.dataset_output_path.as_posix()
    conn.execute(f"CREATE VIEW experiments AS SELECT * FROM read_parquet('{parquet_posix}')")
    cur = conn.cursor()
    yield cur
    cur.close()
    conn.close()


def test_catalog_build_and_coverage(cursor: duckdb.DuckDBPyConnection) -> None:
    catalog = build_field_catalog(cursor)
    assert len(catalog.fields) == 44
    assert len(catalog.field_names) == 44

    # Canonical and enrichment flags
    oxygen = catalog.get_field("oxygen_pct")
    assert oxygen is not None
    assert oxygen.is_canonical is True
    assert oxygen.is_enrichment is False
    assert oxygen.is_numeric is True
    assert oxygen.unit == "%"
    assert oxygen.min_value == 12.0
    assert oxygen.max_value == 85.0
    assert oxygen.null_count == 2

    # Enrichment field
    modeled = catalog.get_field("is_modeled")
    assert modeled is not None
    assert modeled.is_canonical is False
    assert modeled.is_enrichment is True
    assert modeled.data_type == "boolean"


def test_categorical_allowed_values(cursor: duckdb.DuckDBPyConnection) -> None:
    catalog = build_field_catalog(cursor)

    families = catalog.get_field("dataset_family")
    assert families is not None
    assert families.is_categorical is True
    assert families.allowed_values is not None
    assert len(families.allowed_values) == 30
    assert "FLEX" in families.allowed_values
    assert "BASS-II" in families.allowed_values

    outcomes = catalog.get_field("extinction_outcome")
    assert outcomes is not None
    assert outcomes.allowed_values is not None
    assert len(outcomes.allowed_values) == 70
    assert "Self-Extinguished" in outcomes.allowed_values


def test_summary_dict_serialization(cursor: duckdb.DuckDBPyConnection) -> None:
    catalog = build_field_catalog(cursor)
    summary = catalog.to_summary_dict()

    assert "burning_rate_mms" in summary
    assert summary["burning_rate_mms"]["unit"] == "mm/s"
    assert summary["burning_rate_mms"]["type"] == "float"
