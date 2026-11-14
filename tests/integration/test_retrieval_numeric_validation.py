"""Numeric validation tests: comparing store results with independent pandas computations.

Performs 16 independent numeric validation queries covering various campaigns,
regimes, fuels, and measurement fields.
"""

from __future__ import annotations

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


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    settings = get_settings()
    return pd.read_parquet(settings.dataset_output_path)


@pytest.fixture(scope="module")
def store() -> ExperimentStore:
    s = ExperimentStore()
    yield s
    s.close()


def test_numeric_01_flex_methanol_burning_rate(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 1. FLEX Methanol burning rate mean
    p_df = df[
        (~df["is_modeled"])
        & (df["dataset_family"] == "FLEX")
        & (df["fuel_material"].str.contains("methanol", case=False))
    ]
    expected_mean = p_df["burning_rate_mms"].mean()
    expected_count = p_df["burning_rate_mms"].count()
    expected_nulls = p_df["burning_rate_mms"].isna().sum()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="FLEX"),
            FilterCondition(field="fuel_material", op=FilterOperator.CONTAINS, value="Methanol"),
        ],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="burning_rate_mms")],
    )
    res = store.execute_plan(plan)
    agg = res.aggregates[0]
    assert agg.value == pytest.approx(expected_mean, rel=1e-5)
    assert agg.n_used == expected_count
    assert agg.n_null_excluded == expected_nulls


def test_numeric_02_grc_drop_tower_duration(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 2. GRC Drop Tower microgravity duration min, max, mean
    p_df = df[(~df["is_modeled"]) & (df["dataset_family"] == "GRC Drop Tower")]
    expected_mean = p_df["microgravity_duration_s"].mean()
    expected_min = p_df["microgravity_duration_s"].min()
    expected_max = p_df["microgravity_duration_s"].max()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="GRC Drop Tower")
        ],
        aggregates=[
            AggregateSpec(fn=AggregateFunction.MEAN, field="microgravity_duration_s"),
            AggregateSpec(fn=AggregateFunction.MIN, field="microgravity_duration_s"),
            AggregateSpec(fn=AggregateFunction.MAX, field="microgravity_duration_s"),
        ],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].value == pytest.approx(expected_mean, rel=1e-5)
    assert res.aggregates[1].value == pytest.approx(expected_min, rel=1e-5)
    assert res.aggregates[2].value == pytest.approx(expected_max, rel=1e-5)


def test_numeric_03_bass1_airflow_velocity(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 3. BASS-I airflow velocity mean
    p_df = df[(~df["is_modeled"]) & (df["dataset_family"] == "BASS-I")]
    expected_mean = p_df["airflow_velocity_cms"].mean()
    expected_count = p_df["airflow_velocity_cms"].count()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="BASS-I")],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="airflow_velocity_cms")],
    )
    res = store.execute_plan(plan)
    agg = res.aggregates[0]
    assert agg.value == pytest.approx(expected_mean, rel=1e-5)
    assert agg.n_used == expected_count


def test_numeric_04_flex_extinction_diameter(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 4. FLEX extinction diameter mean and min
    p_df = df[(~df["is_modeled"]) & (df["dataset_family"] == "FLEX")]
    expected_mean = p_df["extinction_diameter_mm"].mean()
    expected_min = p_df["extinction_diameter_mm"].min()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="FLEX")],
        aggregates=[
            AggregateSpec(fn=AggregateFunction.MEAN, field="extinction_diameter_mm"),
            AggregateSpec(fn=AggregateFunction.MIN, field="extinction_diameter_mm"),
        ],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].value == pytest.approx(expected_mean, rel=1e-5)
    assert res.aggregates[1].value == pytest.approx(expected_min, rel=1e-5)


def test_numeric_05_pmma_flame_temperature(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 5. PMMA flame temperature in BASS-II
    p_df = df[
        (~df["is_modeled"])
        & (df["dataset_family"] == "BASS-II")
        & (df["fuel_material"].str.contains("pmma", case=False))
    ]
    expected_mean = p_df["flame_temp_k"].mean()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="BASS-II"),
            FilterCondition(field="fuel_material", op=FilterOperator.CONTAINS, value="PMMA"),
        ],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="flame_temp_k")],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].value == pytest.approx(expected_mean, rel=1e-5)


def test_numeric_06_std6001_pressure(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 6. NASA-STD-6001 pressure kPa mean
    p_df = df[(~df["is_modeled"]) & (df["dataset_family"] == "NASA-STD-6001")]
    expected_mean = p_df["pressure_kpa"].mean()
    expected_count = p_df["pressure_kpa"].count()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="NASA-STD-6001")
        ],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="pressure_kpa")],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].value == pytest.approx(expected_mean, rel=1e-5)
    assert res.aggregates[0].n_used == expected_count


def test_numeric_07_radiative_extinction_burn_time(
    df: pd.DataFrame, store: ExperimentStore
) -> None:
    # 7. Radiative Extinction outcome burn_time_s median and mean in GRC Drop Tower
    p_df = df[
        (~df["is_modeled"])
        & (df["dataset_family"] == "GRC Drop Tower")
        & (df["extinction_outcome"] == "Radiative Extinction")
    ]
    expected_median = p_df["burn_time_s"].median()
    expected_mean = p_df["burn_time_s"].mean()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="GRC Drop Tower"),
            FilterCondition(
                field="extinction_outcome", op=FilterOperator.EQ, value="Radiative Extinction"
            ),
        ],
        aggregates=[
            AggregateSpec(fn=AggregateFunction.MEDIAN, field="burn_time_s"),
            AggregateSpec(fn=AggregateFunction.MEAN, field="burn_time_s"),
        ],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].value == pytest.approx(expected_median, rel=1e-5)
    assert res.aggregates[1].value == pytest.approx(expected_mean, rel=1e-5)


def test_numeric_08_mgm_oxygen_pct(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 8. MGM Smoldering combustion oxygen_pct min, max, mean
    p_df = df[(~df["is_modeled"]) & (df["dataset_family"] == "MGM (Smoldering)")]
    expected_min = p_df["oxygen_pct"].min()
    expected_max = p_df["oxygen_pct"].max()
    expected_mean = p_df["oxygen_pct"].mean()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="MGM (Smoldering)")
        ],
        aggregates=[
            AggregateSpec(fn=AggregateFunction.MIN, field="oxygen_pct"),
            AggregateSpec(fn=AggregateFunction.MAX, field="oxygen_pct"),
            AggregateSpec(fn=AggregateFunction.MEAN, field="oxygen_pct"),
        ],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].value == pytest.approx(expected_min, rel=1e-5)
    assert res.aggregates[1].value == pytest.approx(expected_max, rel=1e-5)
    assert res.aggregates[2].value == pytest.approx(expected_mean, rel=1e-5)


def test_numeric_09_acme_bre_flame_temp(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 9. ACME-BRE flame temperature mean and count
    p_df = df[(~df["is_modeled"]) & (df["dataset_family"] == "ACME-BRE")]
    expected_mean = p_df["flame_temp_k"].mean()
    expected_count = p_df["flame_temp_k"].count()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="ACME-BRE")],
        aggregates=[
            AggregateSpec(fn=AggregateFunction.MEAN, field="flame_temp_k"),
            AggregateSpec(fn=AggregateFunction.COUNT, field="flame_temp_k"),
        ],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].value == pytest.approx(expected_mean, rel=1e-5)
    assert res.aggregates[1].value == expected_count


def test_numeric_10_flex_initial_diameter_at_21_pct_o2(
    df: pd.DataFrame, store: ExperimentStore
) -> None:
    # 10. Initial diameter in FLEX at 21% O2
    p_df = df[(~df["is_modeled"]) & (df["dataset_family"] == "FLEX") & (df["oxygen_pct"] == 21.0)]
    expected_mean = p_df["initial_diameter_mm"].mean()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="FLEX"),
            FilterCondition(field="oxygen_pct", op=FilterOperator.EQ, value=21.0),
        ],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="initial_diameter_mm")],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].value == pytest.approx(expected_mean, rel=1e-5)


def test_numeric_11_airflow_velocity_between(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 11. Experiments with airflow between 5.0 and 20.0 cm/s
    p_df = df[
        (~df["is_modeled"])
        & (df["airflow_velocity_cms"] >= 5.0)
        & (df["airflow_velocity_cms"] <= 20.0)
    ]
    expected_count = len(p_df)
    expected_mean_o2 = p_df["oxygen_pct"].mean()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(
                field="airflow_velocity_cms", op=FilterOperator.BETWEEN, value=[5.0, 20.0]
            )
        ],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="oxygen_pct")],
    )
    res = store.execute_plan(plan)
    assert res.total_matching_rows == expected_count
    assert res.aggregates[0].value == pytest.approx(expected_mean_o2, rel=1e-5)


def test_numeric_12_liquid_droplet_category(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 12. Material category Liquid Droplet in FLEX count and mean burning rate
    p_df = df[
        (~df["is_modeled"])
        & (df["dataset_family"] == "FLEX")
        & (df["material_category"] == "Liquid Droplet")
    ]
    expected_mean_rate = p_df["burning_rate_mms"].mean()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="FLEX"),
            FilterCondition(
                field="material_category", op=FilterOperator.EQ, value="Liquid Droplet"
            ),
        ],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="burning_rate_mms")],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].value == pytest.approx(expected_mean_rate, rel=1e-5)


def test_numeric_13_low_oxygen_tests(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 13. Low oxygen tests (oxygen_pct <= 18.0) in BASS-II
    p_df = df[
        (~df["is_modeled"]) & (df["dataset_family"] == "BASS-II") & (df["oxygen_pct"] <= 18.0)
    ]
    expected_mean_temp = p_df["flame_temp_k"].mean()
    expected_count = len(p_df)

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="BASS-II"),
            FilterCondition(field="oxygen_pct", op=FilterOperator.LTE, value=18.0),
        ],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="flame_temp_k")],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].n_used == expected_count
    assert res.aggregates[0].value == pytest.approx(expected_mean_temp, rel=1e-5)


def test_numeric_14_high_pressure_tests(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 14. High pressure tests (pressure_kpa >= 100.0) in GRC Drop Tower
    p_df = df[
        (~df["is_modeled"])
        & (df["dataset_family"] == "GRC Drop Tower")
        & (df["pressure_kpa"] >= 100.0)
    ]
    expected_mean_burn_time = p_df["burn_time_s"].mean()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="GRC Drop Tower"),
            FilterCondition(field="pressure_kpa", op=FilterOperator.GTE, value=100.0),
        ],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="burn_time_s")],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].value == pytest.approx(expected_mean_burn_time, rel=1e-5)


def test_numeric_15_fuel_containing_rod(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 15. Fuel containing 'rod' in BASS-II
    p_df = df[
        (~df["is_modeled"])
        & (df["dataset_family"] == "BASS-II")
        & (df["fuel_material"].str.contains("rod", case=False))
    ]
    expected_mean_temp = p_df["flame_temp_k"].mean()
    expected_count = len(p_df)

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="BASS-II"),
            FilterCondition(field="fuel_material", op=FilterOperator.CONTAINS, value="rod"),
        ],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="flame_temp_k")],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].n_used == expected_count
    assert res.aggregates[0].value == pytest.approx(expected_mean_temp, rel=1e-5)


def test_numeric_16_grc_ignition_power(df: pd.DataFrame, store: ExperimentStore) -> None:
    # 16. Ignition power in GRC Drop Tower
    p_df = df[(~df["is_modeled"]) & (df["dataset_family"] == "GRC Drop Tower")]
    expected_mean = p_df["ignition_power_w"].mean()
    expected_count = p_df["ignition_power_w"].count()

    plan = QueryPlan(
        intent=PlanIntent.AGGREGATE,
        filters=[
            FilterCondition(field="dataset_family", op=FilterOperator.EQ, value="GRC Drop Tower")
        ],
        aggregates=[AggregateSpec(fn=AggregateFunction.MEAN, field="ignition_power_w")],
    )
    res = store.execute_plan(plan)
    assert res.aggregates[0].value == pytest.approx(expected_mean, rel=1e-5)
    assert res.aggregates[0].n_used == expected_count
