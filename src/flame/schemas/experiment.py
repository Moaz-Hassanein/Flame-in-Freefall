"""Typed record schema for the trusted experiment dataset.

The 28 canonical columns keep the legacy column order so downstream code and
documentation stay readable. Units live in field metadata rather than in the
column names. Optionality reflects structural missingness: a field is optional
when a family does not measure it at all, not when a value happens to be absent.

No range constraints are enforced here. Type and identity constraints are hard
(Pandera and this model), while range checks are soft and become data-quality
flags in :mod:`flame.ingestion.validate`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CANONICAL_COLUMNS: tuple[str, ...] = (
    "experiment_id",
    "dataset_family",
    "investigation_id",
    "original_test_id",
    "fuel_material",
    "material_category",
    "sample_description",
    "oxygen_pct",
    "pressure_mmhg",
    "pressure_kpa",
    "burn_time_s",
    "extinction_outcome",
    "extinction_diameter_mm",
    "initial_diameter_mm",
    "burning_rate_mms",
    "airflow_velocity_cms",
    "flame_temp_k",
    "gravity_condition",
    "ignition_power_w",
    "ignition_time_s",
    "co2_pct",
    "he_pct",
    "co_ppm",
    "test_date",
    "source_name",
    "source_url",
    "notes",
    "facility_hardware",
)

ENRICHMENT_COLUMNS: tuple[str, ...] = (
    "is_modeled",
    "data_quality_flags",
    "test_date_raw",
    "extinction_outcome_raw",
    "material_category_raw",
    "fuel_material_raw",
    "airflow_velocity_cms_raw",
    "specimen_length_cm",
    "specimen_width_cm",
    "specimen_thickness_cm",
    "flow_direction",
    "microgravity_duration_s",
    "pi_name",
    "source_file",
    "source_row",
    "record_source",
)

class Experiment(BaseModel):
    """One experiment record with the 28 canonical columns."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str = Field(description="Stable pipeline identifier; unique.")
    dataset_family: str = Field(description="Experiment family or campaign.")
    investigation_id: str = Field(description="Owning investigation identifier.")
    original_test_id: str = Field(description="Test identifier used by the source.")
    fuel_material: str = Field(description="Fuel or specimen material label.")
    material_category: str = Field(description="Material class label.")
    sample_description: str | None = Field(
        default=None, description="Authored specimen description."
    )
    oxygen_pct: float | None = Field(
        default=None, json_schema_extra={"unit": "%", "range": [0.0, 100.0]}
    )
    pressure_mmhg: float | None = Field(
        default=None, json_schema_extra={"unit": "mmHg", "minimum": 0.0}
    )
    pressure_kpa: float | None = Field(
        default=None, json_schema_extra={"unit": "kPa", "minimum": 0.0}
    )
    burn_time_s: float | None = Field(
        default=None, json_schema_extra={"unit": "s", "minimum": 0.0}
    )
    extinction_outcome: str = Field(description="Normalised outcome label.")
    extinction_diameter_mm: float | None = Field(
        default=None, json_schema_extra={"unit": "mm", "minimum": 0.0}
    )
    initial_diameter_mm: float | None = Field(
        default=None, json_schema_extra={"unit": "mm", "minimum": 0.0}
    )
    burning_rate_mms: float | None = Field(
        default=None, json_schema_extra={"unit": "mm/s", "minimum": 0.0}
    )
    airflow_velocity_cms: float | None = Field(
        default=None, json_schema_extra={"unit": "cm/s", "minimum": 0.0}
    )
    flame_temp_k: float | None = Field(default=None, json_schema_extra={"unit": "K"})
    gravity_condition: str = Field(description="Gravity environment descriptor.")
    ignition_power_w: float | None = Field(
        default=None, json_schema_extra={"unit": "W", "minimum": 0.0}
    )
    ignition_time_s: float | None = Field(
        default=None, json_schema_extra={"unit": "s", "minimum": 0.0}
    )
    co2_pct: float | None = Field(
        default=None,
        json_schema_extra={
            "unit": "%",
            "caveat": "May be ambient CO2 or combustion CO2 depending on family.",
        },
    )
    he_pct: float | None = Field(
        default=None,
        json_schema_extra={
            "unit": "%",
            "caveat": "Carried from the legacy artifact; not present in Schema A/B raw files.",
        },
    )
    co_ppm: float | None = Field(default=None, json_schema_extra={"unit": "ppm"})
    test_date: str | None = Field(
        default=None,
        json_schema_extra={"format": "ISO 8601 date", "caveat": "Campaign ranges are nulled."},
    )
    source_name: str = Field(description="Human-readable source name.")
    source_url: str = Field(description="Source URL.")
    notes: str = Field(description="Source or authored notes.")
    facility_hardware: str = Field(description="Facility and hardware descriptor.")


class DatasetRecord(Experiment):
    """Canonical record plus provenance, quality, and extracted text facts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_modeled: bool = Field(
        default=False,
        description="True when the row is a partial-gravity bounding model or reference.",
    )
    data_quality_flags: tuple[str, ...] = Field(
        default_factory=tuple, description="Sorted quality flags for this record."
    )
    test_date_raw: str | None = Field(default=None, description="Original date text.")
    extinction_outcome_raw: str | None = Field(
        default=None, description="Value before vocabulary normalisation."
    )
    material_category_raw: str | None = Field(
        default=None, description="Value before vocabulary normalisation."
    )
    fuel_material_raw: str | None = Field(
        default=None, description="Value before vocabulary normalisation."
    )
    airflow_velocity_cms_raw: float | None = Field(
        default=None, description="Airflow before quarantine."
    )
    specimen_length_cm: float | None = Field(
        default=None, json_schema_extra={"unit": "cm", "source": "sample_description regex"}
    )
    specimen_width_cm: float | None = Field(
        default=None, json_schema_extra={"unit": "cm", "source": "sample_description regex"}
    )
    specimen_thickness_cm: float | None = Field(
        default=None, json_schema_extra={"unit": "cm", "source": "sample_description regex"}
    )
    flow_direction: str | None = Field(
        default=None, description="Concurrent or Opposed, extracted from sample_description."
    )
    microgravity_duration_s: float | None = Field(
        default=None,
        json_schema_extra={"unit": "s", "source": "notes regex", "family": "GRC Drop Tower"},
    )
    pi_name: str | None = Field(
        default=None, json_schema_extra={"source": "notes regex", "family": "BASS-II"}
    )
    source_file: str = Field(description="Input file this record came from.")
    source_row: int = Field(description="1-based data row in the input file.")
    record_source: Literal["raw_rebuild", "canonical_legacy"] = Field(
        description="Which source policy produced this record."
    )


__all__ = [
    "CANONICAL_COLUMNS",
    "ENRICHMENT_COLUMNS",
    "DatasetRecord",
    "Experiment",
]
