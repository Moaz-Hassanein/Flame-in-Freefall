"""Dataset validation: hard contracts fail the build, soft ranges become flags.

Hard constraints are structural: required columns exist, identifiers are
non-null and unique, types are correct, and provenance fields are populated.
Soft constraints are scientific plausibility ranges. A soft violation is never
fixed or dropped; it is attached to the row as a quality flag.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, cast

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaError, SchemaErrors

from flame.ingestion.clean import _append_flag
from flame.ingestion.errors import DataValidationError, PipelineError
from flame.schemas.experiment import CANONICAL_COLUMNS

FLAG_OXYGEN_OUT_OF_RANGE = "OXYGEN_OUT_OF_RANGE"
FLAG_PRESSURE_NEGATIVE = "PRESSURE_NEGATIVE"
FLAG_PRESSURE_UNIT_MISMATCH = "PRESSURE_UNIT_MISMATCH"
FLAG_BURN_TIME_NEGATIVE = "BURN_TIME_NEGATIVE"
FLAG_DIAMETER_NEGATIVE = "DIAMETER_NEGATIVE"
FLAG_BURNING_RATE_NEGATIVE = "BURNING_RATE_NEGATIVE"
FLAG_AIRFLOW_NEGATIVE = "AIRFLOW_NEGATIVE"
FLAG_FLAME_TEMP_OUT_OF_RANGE = "FLAME_TEMP_OUT_OF_RANGE"
FLAG_GAS_FRACTION_OUT_OF_RANGE = "GAS_FRACTION_OUT_OF_RANGE"
FLAG_EMISSIONS_NEGATIVE = "EMISSIONS_NEGATIVE"
FLAG_IGNITION_NEGATIVE = "IGNITION_NEGATIVE"

_MMHG_PER_KPA = 7.50061683
_PRESSURE_RATIO_TOLERANCE_MMHG = 1.0

_REQUIRED_NON_NULL = (
    "experiment_id",
    "dataset_family",
    "investigation_id",
    "original_test_id",
    "fuel_material",
    "material_category",
    "extinction_outcome",
    "gravity_condition",
    "source_name",
    "source_url",
    "notes",
    "facility_hardware",
    "source_file",
    "record_source",
    "is_modeled",
    "data_quality_flags",
)

_NUMERIC_COLUMNS = (
    "oxygen_pct",
    "pressure_mmhg",
    "pressure_kpa",
    "burn_time_s",
    "extinction_diameter_mm",
    "initial_diameter_mm",
    "burning_rate_mms",
    "airflow_velocity_cms",
    "flame_temp_k",
    "ignition_power_w",
    "ignition_time_s",
    "co2_pct",
    "he_pct",
    "co_ppm",
    "specimen_length_cm",
    "specimen_width_cm",
    "specimen_thickness_cm",
    "microgravity_duration_s",
)


@dataclass(frozen=True)
class SoftViolation:
    """One soft range violation."""

    flag: str
    experiment_id: str
    source_file: str
    source_row: int
    column: str
    value: float
    rule: str


@dataclass(frozen=True)
class SoftValidationStats:
    """All soft violations, grouped for the quality report."""

    counts: dict[str, int]
    violations: tuple[SoftViolation, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HardValidationSummary:
    """What the hard contract checked."""

    rows: int
    columns: int


def _build_hard_schema() -> pa.DataFrameSchema:
    columns: dict[str, Any] = {}
    for name in _REQUIRED_NON_NULL:
        columns[name] = pa.Column(nullable=False)

    columns["experiment_id"] = pa.Column(str, nullable=False, unique=True)
    columns["original_test_id"] = pa.Column(str, nullable=False)
    for name in _NUMERIC_COLUMNS:
        columns[name] = pa.Column(float, nullable=True, coerce=True)
    columns["source_row"] = pa.Column(int, nullable=False, checks=pa.Check.ge(0), coerce=True)
    columns["record_source"] = pa.Column(
        str,
        nullable=False,
        checks=pa.Check.isin(["raw_rebuild", "canonical_legacy"]),
    )
    columns["is_modeled"] = pa.Column(bool, nullable=False)
    columns["test_date"] = pa.Column(
        str,
        nullable=True,
        checks=pa.Check.str_matches(r"^\d{4}-\d{2}-\d{2}$"),
    )
    return pa.DataFrameSchema(columns, strict=False, coerce=True)


def validate_hard(frame: pd.DataFrame, *, context: str = "dataset") -> HardValidationSummary:
    """Validate hard structure and raise :class:`DataValidationError` on failure."""

    required = (*CANONICAL_COLUMNS, "source_file", "source_row")
    missing = [name for name in required if name not in frame]
    if missing:
        raise DataValidationError(
            f"{context}: missing required columns",
            failures=[f"missing column {name!r}" for name in missing],
        )

    schema = _build_hard_schema()
    try:
        schema.validate(frame, lazy=True)
    except (SchemaErrors, SchemaError) as error:
        failures = _format_schema_failures(frame, error)
        raise DataValidationError(
            f"{context}: hard validation failed", failures=failures
        ) from error

    return HardValidationSummary(rows=len(frame), columns=len(frame.columns))


def _format_schema_failures(frame: pd.DataFrame, error: Exception) -> list[str]:
    failures: list[str] = []
    cases = getattr(error, "failure_cases", None)
    if isinstance(cases, pd.DataFrame) and not cases.empty:
        for _, row in cases.head(20).iterrows():
            index = row.get("index")
            column = row.get("column")
            check = row.get("check")
            failure = row.get("failure_case")
            location = _row_location(frame, index)
            failures.append(f"{location}: column={column!r} check={check!r} value={failure!r}")
    else:
        failures.append(str(error).splitlines()[0])
    if isinstance(cases, pd.DataFrame) and len(cases) > 20:
        failures.append(f"... {len(cases) - 20} additional failure(s) omitted")
    return failures


def _row_location(frame: pd.DataFrame, index: object) -> str:
    try:
        row = frame.loc[cast(Any, index)]
    except (KeyError, TypeError):
        return f"row index={index!r}"
    experiment_id = row.get("experiment_id", "?")
    source_file = row.get("source_file", "?")
    source_row = row.get("source_row", "?")
    return f"source_file={source_file!r} source_row={source_row!r} experiment_id={experiment_id!r}"


def collect_soft_flags(frame: pd.DataFrame) -> tuple[pd.DataFrame, SoftValidationStats]:
    """Add a flag for every soft range violation, without altering values."""

    flagged = frame.copy()
    if "_flags" not in flagged.columns:
        flagged["_flags"] = pd.Series(
            [[] for _ in range(len(flagged))], index=flagged.index, dtype=object
        )
    violations: list[SoftViolation] = []
    counts: Counter[str] = Counter()

    oxygen = _numeric(flagged, "oxygen_pct")
    pressure_mmhg = _numeric(flagged, "pressure_mmhg")
    pressure_kpa = _numeric(flagged, "pressure_kpa")
    burn_time = _numeric(flagged, "burn_time_s")
    extinction_diameter = _numeric(flagged, "extinction_diameter_mm")
    initial_diameter = _numeric(flagged, "initial_diameter_mm")
    burning_rate = _numeric(flagged, "burning_rate_mms")
    airflow = _numeric(flagged, "airflow_velocity_cms")
    flame_temp = _numeric(flagged, "flame_temp_k")
    co2 = _numeric(flagged, "co2_pct")
    he = _numeric(flagged, "he_pct")
    co = _numeric(flagged, "co_ppm")
    ignition_power = _numeric(flagged, "ignition_power_w")
    ignition_time = _numeric(flagged, "ignition_time_s")

    rule_map: tuple[tuple[str, str, str, pd.Series], ...] = (
        (
            FLAG_OXYGEN_OUT_OF_RANGE,
            "oxygen_pct",
            "0 <= value <= 100",
            oxygen.notna() & ((oxygen < 0) | (oxygen > 100)),
        ),
        (
            FLAG_PRESSURE_NEGATIVE,
            "pressure_mmhg",
            "value >= 0",
            pressure_mmhg.notna() & (pressure_mmhg < 0),
        ),
        (
            FLAG_PRESSURE_NEGATIVE,
            "pressure_kpa",
            "value >= 0",
            pressure_kpa.notna() & (pressure_kpa < 0),
        ),
        (
            FLAG_BURN_TIME_NEGATIVE,
            "burn_time_s",
            "value >= 0",
            burn_time.notna() & (burn_time < 0),
        ),
        (
            FLAG_DIAMETER_NEGATIVE,
            "extinction_diameter_mm",
            "value >= 0",
            extinction_diameter.notna() & (extinction_diameter < 0),
        ),
        (
            FLAG_DIAMETER_NEGATIVE,
            "initial_diameter_mm",
            "value >= 0",
            initial_diameter.notna() & (initial_diameter < 0),
        ),
        (
            FLAG_BURNING_RATE_NEGATIVE,
            "burning_rate_mms",
            "value >= 0",
            burning_rate.notna() & (burning_rate < 0),
        ),
        (
            FLAG_AIRFLOW_NEGATIVE,
            "airflow_velocity_cms",
            "value >= 0",
            airflow.notna() & (airflow < 0),
        ),
        (
            FLAG_FLAME_TEMP_OUT_OF_RANGE,
            "flame_temp_k",
            "0 < value <= 5000",
            flame_temp.notna() & ((flame_temp <= 0) | (flame_temp > 5000)),
        ),
        (
            FLAG_GAS_FRACTION_OUT_OF_RANGE,
            "co2_pct",
            "0 <= value <= 100",
            co2.notna() & ((co2 < 0) | (co2 > 100)),
        ),
        (
            FLAG_GAS_FRACTION_OUT_OF_RANGE,
            "he_pct",
            "0 <= value <= 100",
            he.notna() & ((he < 0) | (he > 100)),
        ),
        (
            FLAG_EMISSIONS_NEGATIVE,
            "co_ppm",
            "value >= 0",
            co.notna() & (co < 0),
        ),
        (
            FLAG_IGNITION_NEGATIVE,
            "ignition_power_w",
            "value >= 0",
            ignition_power.notna() & (ignition_power < 0),
        ),
        (
            FLAG_IGNITION_NEGATIVE,
            "ignition_time_s",
            "value >= 0",
            ignition_time.notna() & (ignition_time < 0),
        ),
    )

    for flag, column, rule, mask in rule_map:
        _record_violations(
            flagged, violations, counts, flag=flag, column=column, rule=rule, mask=mask
        )

    ratio_mask = (
        pressure_mmhg.notna()
        & pressure_kpa.notna()
        & ((pressure_mmhg - pressure_kpa * _MMHG_PER_KPA).abs() > _PRESSURE_RATIO_TOLERANCE_MMHG)
    )
    _record_violations(
        flagged,
        violations,
        counts,
        flag=FLAG_PRESSURE_UNIT_MISMATCH,
        column="pressure_mmhg",
        rule=f"abs(mmhg - kpa * {_MMHG_PER_KPA}) <= {_PRESSURE_RATIO_TOLERANCE_MMHG}",
        mask=ratio_mask,
    )

    stats = SoftValidationStats(
        counts=dict(sorted(counts.items())),
        violations=tuple(
            sorted(violations, key=lambda item: (item.flag, item.experiment_id, item.column))
        ),
    )
    return flagged, stats


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(float("nan"), index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _record_violations(
    frame: pd.DataFrame,
    violations: list[SoftViolation],
    counts: Counter[str],
    *,
    flag: str,
    column: str,
    rule: str,
    mask: pd.Series,
) -> None:
    values = pd.to_numeric(frame[column], errors="coerce")
    for index in frame.index[mask]:
        _append_flag(frame, index, flag)
        counts[flag] += 1
        violations.append(
            SoftViolation(
                flag=flag,
                experiment_id=str(frame.at[index, "experiment_id"]),
                source_file=str(cast(Any, frame.at[index, "source_file"])),
                source_row=int(cast(Any, frame.at[index, "source_row"])),
                column=column,
                value=float(cast(Any, values.at[index])),
                rule=rule,
            )
        )


def require_verified_patterns(stats: object) -> None:
    """Fail if a text-extraction pattern did not verify against its candidates."""

    unverified: list[str] = []
    for attr in (
        "specimen_dimensions",
        "flow_direction",
        "microgravity_duration",
        "pi_name",
    ):
        pattern = getattr(stats, attr, None)
        if pattern is None:
            continue
        if not bool(getattr(pattern, "verified", False)):
            unverified.append(
                f"{getattr(pattern, 'name', attr)}: matched "
                f"{getattr(pattern, 'matched_rows', '?')} of "
                f"{getattr(pattern, 'candidate_rows', '?')} candidates"
            )
    if unverified:
        raise PipelineError("text extraction pattern failed verification: " + "; ".join(unverified))
