"""Unit tests for the Pydantic experiment schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flame.schemas.experiment import CANONICAL_COLUMNS, DatasetRecord, Experiment


def _valid_payload() -> dict[str, object]:
    return {
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
    }


def test_model_covers_all_28_canonical_columns() -> None:
    assert tuple(Experiment.model_fields) == CANONICAL_COLUMNS
    assert len(CANONICAL_COLUMNS) == 28


def test_valid_record_is_accepted() -> None:
    record = Experiment.model_validate(_valid_payload())

    assert record.experiment_id == "EXP-001"
    assert record.oxygen_pct == pytest.approx(21.0)


def test_units_live_in_field_metadata() -> None:
    assert Experiment.model_fields["oxygen_pct"].json_schema_extra == {
        "unit": "%",
        "range": [0.0, 100.0],
    }
    assert Experiment.model_fields["burn_time_s"].json_schema_extra is not None
    assert Experiment.model_fields["burn_time_s"].json_schema_extra["unit"] == "s"
    assert Experiment.model_fields["pressure_mmhg"].json_schema_extra["unit"] == "mmHg"


def test_required_fields_are_enforced() -> None:
    payload = _valid_payload()
    del payload["experiment_id"]

    with pytest.raises(ValidationError):
        Experiment.model_validate(payload)


def test_structural_nulls_are_allowed() -> None:
    payload = _valid_payload()
    payload["extinction_diameter_mm"] = None
    payload["ignition_power_w"] = None

    record = Experiment.model_validate(payload)

    assert record.extinction_diameter_mm is None
    assert record.ignition_power_w is None


def test_dataset_record_rejects_unknown_fields() -> None:
    payload = _valid_payload()
    payload.update(
        {
            "is_modeled": True,
            "data_quality_flags": ["A"],
            "source_file": "raw.csv",
            "source_row": 2,
            "record_source": "raw_rebuild",
        }
    )

    record = DatasetRecord.model_validate(payload)
    assert record.is_modeled is True
    assert record.data_quality_flags == ("A",)

    payload["unknown"] = 1
    with pytest.raises(ValidationError):
        DatasetRecord.model_validate(payload)
