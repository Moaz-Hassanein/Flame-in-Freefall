"""Unit tests for airflow quarantine and pressure/burn-time flags."""

from __future__ import annotations

import pandas as pd
import pytest

from flame.ingestion.clean import (
    FLAG_AIRFLOW_QUARANTINED,
    FLAG_BURN_TIME_IMPLAUSIBLE,
    FLAG_BURN_TIME_ZERO,
    FLAG_PRESSURE_KPA_MISSING,
    FLAG_PRESSURE_MMHG_ZERO,
    flag_pressure_and_burn_time,
    quarantine_airflow,
)


def _airflow_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "experiment_id": ["a", "b", "c", "d"],
            "dataset_family": ["F", "F", "G", "G"],
            "source_file": ["raw.csv"] * 4,
            "source_row": [2, 3, 4, 5],
            "airflow_velocity_cms": [0.0, 1000.0, 1000.1, None],
        }
    )


def test_airflow_above_threshold_is_quarantined() -> None:
    cleaned, stats = quarantine_airflow(_airflow_frame(), threshold_cms=1000.0)

    airflow = cleaned["airflow_velocity_cms"].tolist()
    assert airflow[:2] == [0.0, 1000.0]
    assert pd.isna(airflow[2])
    assert pd.isna(airflow[3])
    assert cleaned["airflow_velocity_cms"].isna().sum() == 2
    assert cleaned["airflow_velocity_cms_raw"].tolist()[2] == 1000.1
    assert cleaned["_flags"].tolist()[2] == [FLAG_AIRFLOW_QUARANTINED]
    assert len(stats.quarantined) == 1
    assert stats.quarantined[0].experiment_id == "c"
    assert stats.quarantined[0].value == pytest.approx(1000.1)
    assert stats.missing == 1


def test_airflow_threshold_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        quarantine_airflow(_airflow_frame(), threshold_cms=0)


def test_pressure_and_burn_time_are_flagged_but_not_altered() -> None:
    frame = pd.DataFrame(
        {
            "experiment_id": ["a", "b", "c", "d", "e"],
            "pressure_mmhg": [0.0, 760.0, 760.0, 760.0, 760.0],
            "pressure_kpa": [101.3, None, 101.3, 101.3, 101.3],
            "burn_time_s": [10.0, 10.0, 0.0, 4000.0, None],
        }
    )

    cleaned, stats = flag_pressure_and_burn_time(frame, burn_time_max_s=3600.0)

    pd.testing.assert_series_equal(cleaned["pressure_mmhg"], frame["pressure_mmhg"])
    pd.testing.assert_series_equal(cleaned["burn_time_s"], frame["burn_time_s"])
    assert cleaned["_flags"].tolist() == [
        [FLAG_PRESSURE_MMHG_ZERO],
        [FLAG_PRESSURE_KPA_MISSING],
        [FLAG_BURN_TIME_ZERO],
        [FLAG_BURN_TIME_IMPLAUSIBLE],
        [],
    ]
    assert stats.counts == {
        FLAG_PRESSURE_MMHG_ZERO: 1,
        FLAG_PRESSURE_KPA_MISSING: 1,
        FLAG_BURN_TIME_ZERO: 1,
        FLAG_BURN_TIME_IMPLAUSIBLE: 1,
    }
    assert stats.burn_time_implausible == (("d", 4000.0),)


def test_burn_time_max_must_be_positive() -> None:
    frame = pd.DataFrame(
        {
            "experiment_id": ["a"],
            "pressure_mmhg": [760.0],
            "pressure_kpa": [101.3],
            "burn_time_s": [1.0],
        }
    )

    with pytest.raises(ValueError, match="must be positive"):
        flag_pressure_and_burn_time(frame, burn_time_max_s=0)
