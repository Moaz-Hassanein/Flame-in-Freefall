"""Integration tests for ExperimentStore lifecycle, versioning, and concurrency."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from flame.config import get_settings
from flame.retrieval.store import ExperimentStore
from flame.schemas.query_plan import (
    AggregateFunction,
    AggregateSpec,
    FilterCondition,
    FilterOperator,
    PlanIntent,
    QueryPlan,
)


def test_store_loads_dataset_version_from_manifest() -> None:
    settings = get_settings()
    with ExperimentStore() as store:
        version = store.dataset_version
        assert version.parquet_path == str(settings.dataset_output_path)
        assert version.total_rows == 892
        assert version.raw_rebuild_rows == 450
        assert version.canonical_legacy_rows == 442
        assert version.flags.get("AIRFLOW_QUARANTINED") == 42
        assert len(version.source_policy.get("raw_rebuild", [])) == 18
        assert len(version.source_policy.get("canonical_legacy", [])) == 12


def test_store_concurrency_parallel_queries() -> None:
    """Verify thread safety with concurrent queries using fresh cursors."""
    queries = [
        ("Methanol", 21.0),
        ("n-Heptane", 21.0),
        ("Ethanol", 21.0),
        ('1/4" black rod', None),
        ("PMMA", 21.0),
    ]

    def run_worker(query_tuple: tuple[str, float | None]) -> int:
        fuel, o2 = query_tuple
        filters = [FilterCondition(field="fuel_material", op=FilterOperator.CONTAINS, value=fuel)]
        if o2 is not None:
            filters.append(FilterCondition(field="oxygen_pct", op=FilterOperator.EQ, value=o2))

        plan = QueryPlan(intent=PlanIntent.LOOKUP, filters=filters, limit=500)
        with ExperimentStore() as store:
            result = store.execute_plan(plan)
            return len(result.rows)

    with ThreadPoolExecutor(max_workers=5) as pool:
        counts = list(pool.map(run_worker, queries * 4))  # 20 concurrent tasks

    assert len(counts) == 20
    assert all(c >= 0 for c in counts)


def test_methanol_droplets_at_21_pct_o2_acceptance_criterion() -> None:
    """Acceptance criterion: query for methanol droplets at 21% O2."""
    settings = get_settings()
    raw_df = pd.read_parquet(settings.dataset_output_path)

    # Independent computation in pandas:
    # Modeled rows excluded by default
    # Fuel contains 'Methanol' case-insensitively, oxygen_pct == 21.0
    pandas_filtered = raw_df[
        (~raw_df["is_modeled"])
        & (raw_df["fuel_material"].str.contains("methanol", case=False, na=False))
        & (raw_df["oxygen_pct"] == 21.0)
    ]
    expected_ids = set(pandas_filtered["experiment_id"].tolist())
    expected_mean = pandas_filtered[pandas_filtered["dataset_family"] == "FLEX"][
        "burning_rate_mms"
    ].mean()

    with ExperimentStore() as store:
        plan = QueryPlan(
            intent=PlanIntent.AGGREGATE,
            filters=[
                FilterCondition(
                    field="fuel_material", op=FilterOperator.CONTAINS, value="Methanol"
                ),
                FilterCondition(field="oxygen_pct", op=FilterOperator.EQ, value=21.0),
            ],
            aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="burning_rate_mms")],
            limit=100,
        )
        result = store.execute_plan(plan)

        # 1. Matching rows check
        retrieved_ids = {r["experiment_id"] for r in result.rows}
        assert retrieved_ids == expected_ids
        assert len(result.rows) == 30  # 29 FLEX + 1 GRC Drop Tower

        # 2. Mean burning rate check:
        # Since burning_rate_mms is semantically different across families,
        # retrieval grouped by dataset_family by default
        flex_agg = next(
            agg
            for agg in result.aggregates
            if agg.group_key and agg.group_key.get("dataset_family") == "FLEX"
        )
        assert flex_agg.value == pytest.approx(expected_mean, rel=1e-5)
        assert flex_agg.n_used == 26
        assert flex_agg.n_null_excluded == 3
        assert flex_agg.n_quarantined_excluded == 0
        assert any("semantically different" in w for w in result.warnings)
