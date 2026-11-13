"""End-to-end build test on a tiny synthetic fixture.

The fixture reproduces the structural shape of the real inputs (one schema-style
raw file, one legacy canonical file, and the three versioned mapping files) so
the full pipeline can be exercised without touching the real data.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from flame.ingestion.canonicalize import sha256_file
from flame.ingestion.pipeline import (
    PipelineConfig,
    build_manifest,
    build_quality_report,
    run_pipeline,
    write_manifest,
    write_parquet,
)
from flame.schemas.experiment import CANONICAL_COLUMNS

pytestmark = pytest.mark.integration

_GENERATED_AT = datetime(2026, 1, 1, tzinfo=UTC)

_RAW_COLUMNS = (
    "experiment_id",
    "investigation_id",
    "dataset_family",
    "fuel_material",
    "material_category",
    "oxygen_pct",
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
    "co_ppm",
    "test_date",
    "source_name",
    "source_url",
    "notes",
)

_SOURCE_POLICY = """\
version: 1
raw_source_files:
  - file: fixture_raw.csv
    encoding: utf-8
    families: [FixtureRaw, FixtureModeled]
raw_rebuild:
  description: fixture
  families: [FixtureRaw, FixtureModeled]
  columns_from_raw:
    - experiment_id
    - investigation_id
    - dataset_family
    - fuel_material
    - material_category
    - oxygen_pct
    - pressure_kpa
    - burn_time_s
    - extinction_outcome
    - extinction_diameter_mm
    - initial_diameter_mm
    - burning_rate_mms
    - airflow_velocity_cms
    - flame_temp_k
    - gravity_condition
    - ignition_power_w
    - ignition_time_s
    - co2_pct
    - co_ppm
    - test_date
    - source_name
    - source_url
    - notes
  columns_carried_from_legacy:
    - sample_description
    - facility_hardware
    - he_pct
  derived_columns:
    original_test_id: experiment_id
    pressure_mmhg: round(pressure_kpa * 7.50061683, 1)
canonical_legacy:
  description: fixture
  families: [FixtureLegacy]
  raw_inputs_not_used_for_rebuild: []
"""

_VOCABULARIES = """\
version: 2
extinction_outcome:
  mappings:
    "Self-extinguished":
      to: "Self-Extinguished"
      reason: "case-only fixture variant"
material_category:
  mappings: {}
fuel_material:
  mappings:
    "1/4 blac rod":
      to: '1/4" black rod'
      reason: "fixture spelling repair"
gravity_condition:
  mappings:
    "microgravity":
      to: "Microgravity (~0g)"
      reason: "fixture case normalisation"
proposed_not_applied: {}
"""

_MODELED_RULES = """\
version: 1
rules:
  - id: fixture_modeled
    description: fixture partial-gravity bounding row
    dataset_family_in: [FixtureModeled]
    gravity_condition_prefix: "Partial-g Bounded Model"
"""


def _raw_row(experiment_id: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "experiment_id": experiment_id,
        "investigation_id": "INV-FIXTURE",
        "dataset_family": "FixtureRaw",
        "fuel_material": "Kevlar",
        "material_category": "Fabric",
        "oxygen_pct": 21.0,
        "pressure_kpa": 101.3,
        "burn_time_s": 10.0,
        "extinction_outcome": "Extinction",
        "extinction_diameter_mm": 1.0,
        "initial_diameter_mm": 2.0,
        "burning_rate_mms": 0.5,
        "airflow_velocity_cms": 12.0,
        "flame_temp_k": 1200.0,
        "gravity_condition": "microgravity",
        "ignition_power_w": 50.0,
        "ignition_time_s": 2.0,
        "co2_pct": 0.5,
        "co_ppm": 10.0,
        "test_date": "2020-01-02",
        "source_name": "Fixture source",
        "source_url": "https://example.invalid/fixture",
        "notes": "fixture note",
    }
    row.update(overrides)
    return row


def _canonical_row(
    experiment_id: str,
    family: str,
    *,
    test_date: object = "2020-01-02",
) -> dict[str, object]:
    return {
        "experiment_id": experiment_id,
        "dataset_family": family,
        "investigation_id": "INV-FIXTURE",
        "original_test_id": experiment_id,
        "fuel_material": "Kevlar",
        "material_category": "Fabric",
        "sample_description": "Fixture specimen",
        "oxygen_pct": 21.0,
        "pressure_mmhg": 760.0,
        "pressure_kpa": 101.3,
        "burn_time_s": 10.0,
        "extinction_outcome": "Extinction",
        "extinction_diameter_mm": 1.0,
        "initial_diameter_mm": 2.0,
        "burning_rate_mms": 0.5,
        "airflow_velocity_cms": 12.0,
        "flame_temp_k": 1200.0,
        "gravity_condition": "Microgravity (~0g)",
        "ignition_power_w": 50.0,
        "ignition_time_s": 2.0,
        "co2_pct": 0.5,
        "he_pct": 0.0,
        "co_ppm": 10.0,
        "test_date": test_date,
        "source_name": "Fixture source",
        "source_url": "https://example.invalid/fixture",
        "notes": "fixture note",
        "facility_hardware": "Fixture rig",
    }


def _write_fixture(tmp_path: Path) -> PipelineConfig:
    raw_dir = tmp_path / "raw"
    mappings = tmp_path / "mappings"
    raw_dir.mkdir()
    mappings.mkdir()

    raw_rows = [
        _raw_row(
            "R-001",
            fuel_material="1/4 blac rod",
            extinction_outcome="Self-extinguished",
        ),
        _raw_row(
            "R-002",
            pressure_kpa=0.0,
            burn_time_s=0.0,
            airflow_velocity_cms=54321.0,
            test_date="1/2/20",
        ),
        _raw_row(
            "R-003",
            dataset_family="FixtureModeled",
            pressure_kpa=None,
            burn_time_s=10003.4,
            airflow_velocity_cms=0.0,
            gravity_condition="Partial-g Bounded Model: Lunar (0.16g)",
            test_date="2017-2024",
        ),
    ]
    pd.DataFrame(raw_rows, columns=list(_RAW_COLUMNS)).to_csv(
        raw_dir / "fixture_raw.csv", index=False
    )

    canonical_rows = [
        _canonical_row("R-001", "FixtureRaw"),
        _canonical_row("R-002", "FixtureRaw"),
        _canonical_row("R-003", "FixtureModeled"),
        _canonical_row(
            "L-001",
            "FixtureLegacy",
            test_date=None,
        )
        | {
            "fuel_material": "Methanol",
            "material_category": "Liquid",
            "sample_description": "Droplet specimen",
            "notes": "PI: Bhattacharyya. Sample #147.",
            "facility_hardware": "ISS CIR",
        },
    ]
    pd.DataFrame(canonical_rows, columns=list(CANONICAL_COLUMNS)).to_csv(
        tmp_path / "canonical.csv", index=False
    )

    (mappings / "source_policy.yaml").write_text(_SOURCE_POLICY, encoding="utf-8")
    (mappings / "vocabularies.yaml").write_text(_VOCABULARIES, encoding="utf-8")
    (mappings / "modeled_rows.yaml").write_text(_MODELED_RULES, encoding="utf-8")

    return PipelineConfig(
        raw_dir=raw_dir,
        canonical_path=tmp_path / "canonical.csv",
        source_policy_path=mappings / "source_policy.yaml",
        vocabularies_path=mappings / "vocabularies.yaml",
        modeled_rules_path=mappings / "modeled_rows.yaml",
        canonical_diff_path=tmp_path / "canonical_diff.csv",
        airflow_threshold_cms=1000.0,
        burn_time_max_s=3600.0,
        project_root=tmp_path,
    )


def test_build_from_fixture_produces_expected_rows_and_flags(tmp_path: Path) -> None:
    config = _write_fixture(tmp_path)

    result = run_pipeline(config)

    frame = result.frame
    assert len(frame) == 4
    assert set(frame["experiment_id"]) == {"R-001", "R-002", "R-003", "L-001"}
    assert frame["experiment_id"].is_unique
    sources = frame.set_index("experiment_id")["record_source"]
    assert sources["R-001"] == "raw_rebuild"
    assert sources["L-001"] == "canonical_legacy"

    # Explicit vocabulary mapping and preserved raw value.
    r1 = frame.loc[frame["experiment_id"] == "R-001"].iloc[0]
    assert r1["fuel_material"] == '1/4" black rod'
    assert r1["fuel_material_raw"] == "1/4 blac rod"
    assert r1["extinction_outcome"] == "Self-Extinguished"
    assert r1["extinction_outcome_raw"] == "Self-extinguished"
    assert r1["gravity_condition"] == "Microgravity (~0g)"

    # Date normalisation: ISO, two-digit-US, and campaign-range null.
    dates = frame.set_index("experiment_id")["test_date"]
    assert dates["R-001"] == "2020-01-02"
    assert dates["R-002"] == "2020-01-02"
    assert pd.isna(dates["R-003"])
    assert pd.isna(dates["L-001"])

    # Airflow quarantine preserves the raw reading.
    r2 = frame.loc[frame["experiment_id"] == "R-002"].iloc[0]
    assert pd.isna(r2["airflow_velocity_cms"])
    assert r2["airflow_velocity_cms_raw"] == pytest.approx(54321.0)
    assert "AIRFLOW_QUARANTINED" in r2["data_quality_flags"]
    assert len(result.airflow_stats.quarantined) == 1

    # Modeled row is selected by family and gravity, not by identifier.
    labeled = frame.set_index("experiment_id")["is_modeled"]
    assert bool(labeled["R-003"]) is True
    assert bool(labeled["R-001"]) is False
    assert result.modeled_stats.total == 1
    assert result.modeled_stats.rule_counts == {"fixture_modeled": 1}

    # Flag but do not alter zero and implausible numeric values.
    r2_row = frame.loc[frame["experiment_id"] == "R-002"].iloc[0]
    assert r2_row["burn_time_s"] == 0.0
    assert "BURN_TIME_ZERO" in r2_row["data_quality_flags"]
    assert r2_row["pressure_mmhg"] == 0.0
    assert "PRESSURE_MMHG_ZERO" in r2_row["data_quality_flags"]
    r3_row = frame.loc[frame["experiment_id"] == "R-003"].iloc[0]
    assert r3_row["burn_time_s"] == pytest.approx(10003.4)
    assert "BURN_TIME_IMPLAUSIBLE" in r3_row["data_quality_flags"]
    assert "PRESSURE_KPA_MISSING" in r3_row["data_quality_flags"]
    assert "TEST_DATE_CAMPAIGN_RANGE" in r3_row["data_quality_flags"]

    # PI extraction is deterministic for the legacy BASS-II-style row.
    l1 = frame.loc[frame["experiment_id"] == "L-001"].iloc[0]
    assert l1["pi_name"] == "Bhattacharyya"

    assert result.flag_counts["AIRFLOW_QUARANTINED"] == 1
    assert result.flag_counts["BURN_TIME_ZERO"] == 1
    assert result.flag_counts["BURN_TIME_IMPLAUSIBLE"] == 1
    assert result.flag_counts["TEST_DATE_CAMPAIGN_RANGE"] == 1
    assert result.flag_counts["TEST_DATE_MISSING"] == 1


def test_manifest_and_quality_report_describe_the_fixture_build(tmp_path: Path) -> None:
    config = _write_fixture(tmp_path)
    result = run_pipeline(config)
    parquet_path = tmp_path / "experiments.parquet"
    parquet_sha256 = write_parquet(result.frame, parquet_path)

    manifest = build_manifest(
        result,
        generated_at=_GENERATED_AT,
        commit="fixture-commit",
        parquet_sha256=parquet_sha256,
        thresholds={
            "airflow_quarantine_threshold_cms": 1000.0,
            "burn_time_max_s": 3600.0,
        },
    )
    manifest_path = tmp_path / "provenance_manifest.json"
    write_manifest(manifest, manifest_path)

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["pipeline"]["version"]
    assert payload["git_commit"] == "fixture-commit"
    assert payload["outputs"]["rows"] == 4
    assert payload["outputs"]["parquet_sha256"] == sha256_file(parquet_path)
    assert payload["row_counts"]["total"] == 4
    assert payload["row_counts"]["raw_rebuild"] == 3
    assert payload["row_counts"]["canonical_legacy"] == 1
    assert payload["is_modeled"]["count"] == 1
    assert payload["quarantined_airflow"] == {
        "count": 1,
        "threshold_cms": 1000.0,
    }
    assert payload["flags"]["AIRFLOW_QUARANTINED"] == 1

    # One raw file, one canonical file, three mapping files.
    assert len(payload["inputs"]) == 5
    for item in payload["inputs"]:
        assert len(item["sha256"]) == 64
        int(item["sha256"], 16)
    assert {item["kind"] for item in payload["inputs"]} == {
        "raw",
        "canonical_legacy",
        "mapping",
    }

    report = build_quality_report(
        result,
        generated_at=_GENERATED_AT,
        commit="fixture-commit",
        manifest=payload,
    )
    assert "**4**" in report
    assert "`AIRFLOW_QUARANTINED`" in report
    assert "`Self-extinguished`" in report
    assert "`1/4 blac rod`" in report
    assert "`fixture_modeled`" in report
    assert "R-002" in report
    assert "Threshold: **1000 cm/s**" in report


def test_pipeline_is_deterministic_for_identical_input(tmp_path: Path) -> None:
    config = _write_fixture(tmp_path)

    first = run_pipeline(config)
    first_path = tmp_path / "first.parquet"
    first_hash = write_parquet(first.frame, first_path)

    second = run_pipeline(config)
    second_path = tmp_path / "second.parquet"
    second_hash = write_parquet(second.frame, second_path)

    assert first_hash == second_hash
    assert first_path.read_bytes() == second_path.read_bytes()
    pd.testing.assert_frame_equal(first.frame, second.frame)
