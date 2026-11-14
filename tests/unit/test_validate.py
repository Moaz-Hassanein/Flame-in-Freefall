"""Unit tests for hard and soft dataset validation."""

from __future__ import annotations

import pandas as pd
import pytest

from flame.ingestion.errors import DataValidationError
from flame.ingestion.validate import (
    FLAG_BURNING_RATE_NEGATIVE,
    FLAG_OXYGEN_OUT_OF_RANGE,
    FLAG_PRESSURE_UNIT_MISMATCH,
    collect_soft_flags,
    validate_hard,
)
from flame.schemas.experiment import CANONICAL_COLUMNS


def _frame() -> pd.DataFrame:
    row: dict[str, object] = {
        "experiment_id": "EXP-001",
        "dataset_family": "FLEX",
        "investigation_id": "PSI-69",
        "original_test_id": "1",
        "fuel_material": "Methanol",
        "material_category": "Liquid Droplet",
        "sample_description": "Droplet",
        "oxygen_pct": 21.0,
        "pressure_mmhg": 760.0,
        "pressure_kpa": 101.32,
        "burn_time_s": 4.3,
        "extinction_outcome": "Extinction",
        "extinction_diameter_mm": 0.89,
        "initial_diameter_mm": 1.69,
        "burning_rate_mms": 0.52,
        "airflow_velocity_cms": 0.0,
        "flame_temp_k": 1250.0,
        "gravity_condition": "Microgravity (~0g)",
        "ignition_power_w": None,
        "ignition_time_s": None,
        "co2_pct": 0.0,
        "he_pct": 0.0,
        "co_ppm": None,
        "test_date": "2009-03-05",
        "source_name": "NASA PSI",
        "source_url": "https://example.invalid",
        "notes": "note",
        "facility_hardware": "ISS CIR",
        "is_modeled": False,
        "data_quality_flags": [],
        "test_date_raw": "3/5/2009",
        "extinction_outcome_raw": "Extinction",
        "material_category_raw": "Liquid Droplet",
        "fuel_material_raw": "Methanol",
        "airflow_velocity_cms_raw": 0.0,
        "specimen_length_cm": None,
        "specimen_width_cm": None,
        "specimen_thickness_cm": None,
        "flow_direction": None,
        "microgravity_duration_s": None,
        "pi_name": None,
        "source_file": "raw.csv",
        "source_row": 2,
        "record_source": "raw_rebuild",
    }
    return pd.DataFrame([row])


def test_hard_validation_passes_on_a_valid_frame() -> None:
    summary = validate_hard(_frame())

    assert summary.rows == 1
    assert summary.columns == len(CANONICAL_COLUMNS) + 16


def test_hard_validation_rejects_duplicate_ids() -> None:
    frame = pd.concat([_frame(), _frame()], ignore_index=True)
    frame.loc[1, "source_row"] = 3

    with pytest.raises(DataValidationError, match="hard validation failed") as error:
        validate_hard(frame)

    assert any("experiment_id" in failure for failure in error.value.failures)


def test_hard_validation_rejects_missing_columns() -> None:
    frame = _frame().drop(columns=["original_test_id"])

    with pytest.raises(DataValidationError, match="missing required columns"):
        validate_hard(frame)


def test_hard_validation_rejects_bad_record_source() -> None:
    frame = _frame()
    frame.loc[0, "record_source"] = "invented"

    with pytest.raises(DataValidationError) as error:
        validate_hard(frame)

    assert any("record_source" in failure for failure in error.value.failures)


def test_soft_violations_are_flags_not_edits() -> None:
    frame = _frame()
    frame.loc[0, "oxygen_pct"] = 101.0
    frame.loc[0, "burning_rate_mms"] = -0.1
    frame.loc[0, "pressure_mmhg"] = 800.0
    frame.loc[0, "pressure_kpa"] = 101.32

    flagged, stats = collect_soft_flags(frame)

    assert flagged.loc[0, "oxygen_pct"] == 101.0
    assert flagged.loc[0, "burning_rate_mms"] == -0.1
    assert set(flagged.loc[0, "_flags"]) == {
        FLAG_OXYGEN_OUT_OF_RANGE,
        FLAG_BURNING_RATE_NEGATIVE,
        FLAG_PRESSURE_UNIT_MISMATCH,
    }
    assert stats.counts == {
        FLAG_OXYGEN_OUT_OF_RANGE: 1,
        FLAG_BURNING_RATE_NEGATIVE: 1,
        FLAG_PRESSURE_UNIT_MISMATCH: 1,
    }


def test_soft_validation_is_clean_for_valid_values() -> None:
    flagged, stats = collect_soft_flags(_frame())

    assert flagged.loc[0, "_flags"] == []
    assert stats.counts == {}
