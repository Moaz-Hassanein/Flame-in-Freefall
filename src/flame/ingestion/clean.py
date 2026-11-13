"""Pure cleaning functions for canonical experiment records.

Every function takes a DataFrame and returns a new DataFrame plus an immutable
statistics object. Nothing is written to disk and no input frame is mutated.
Cleaning never imputes a scientific value: it normalises vocabularies, parses
dates, quarantines impossible airflow readings, and records flags for values a
reviewer must inspect.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml

FLAG_TEST_DATE_MISSING = "TEST_DATE_MISSING"
FLAG_TEST_DATE_CAMPAIGN_RANGE = "TEST_DATE_CAMPAIGN_RANGE"
FLAG_TEST_DATE_UNPARSEABLE = "TEST_DATE_UNPARSEABLE"
FLAG_AIRFLOW_QUARANTINED = "AIRFLOW_QUARANTINED"
FLAG_PRESSURE_MMHG_ZERO = "PRESSURE_MMHG_ZERO"
FLAG_PRESSURE_KPA_MISSING = "PRESSURE_KPA_MISSING"
FLAG_BURN_TIME_ZERO = "BURN_TIME_ZERO"
FLAG_BURN_TIME_IMPLAUSIBLE = "BURN_TIME_IMPLAUSIBLE"

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_US_DATE_4Y = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_US_DATE_2Y = re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$")
_CAMPAIGN_RANGE = re.compile(r"^\d{4}-\d{4}$")


@dataclass(frozen=True)
class DateParseStats:
    """Counts produced by :func:`clean_test_dates`."""

    total: int
    missing: int
    parsed: int
    converted: int
    campaign_ranges: dict[str, int] = field(default_factory=dict)
    unparseable: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class VocabularyStats:
    """Counts produced by :func:`normalize_vocabulary`."""

    column: str
    mapping_version: str
    total_non_null: int
    null_count: int
    applied: tuple[tuple[str, str, int], ...]
    identity: dict[str, int]


@dataclass(frozen=True)
class QuarantinedAirflow:
    """One airflow reading that exceeded the quarantine threshold."""

    experiment_id: str
    dataset_family: str
    source_file: str
    source_row: int
    value: float


@dataclass(frozen=True)
class AirflowStats:
    """Counts produced by :func:`quarantine_airflow`."""

    threshold_cms: float
    total: int
    missing: int
    quarantined: tuple[QuarantinedAirflow, ...]


@dataclass(frozen=True)
class NumericFlagStats:
    """Counts produced by :func:`flag_pressure_and_burn_time`."""

    counts: dict[str, int]
    pressure_zero: tuple[str, ...]
    pressure_kpa_missing: tuple[str, ...]
    burn_time_zero: tuple[str, ...]
    burn_time_implausible: tuple[tuple[str, float], ...]


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return bool(pd.isna(cast(Any, value)))


def parse_test_date(value: object) -> tuple[str | None, tuple[str, ...]]:
    """Parse one date value into an ISO date.

    Accepted formats are ``YYYY-MM-DD``, ``M/D/YYYY``, and ``M/D/YY``. Two-digit
    years use the explicit POSIX-style pivot in :func:`_expand_two_digit_year`.
    Campaign ranges (``2017-2024``) are not dates and become null. Anything
    else becomes null with a flag.

    Returns the ISO date (or ``None``) and a tuple of flags.
    """

    if _is_missing(value):
        return None, (FLAG_TEST_DATE_MISSING,)
    if not isinstance(value, str):
        return None, (FLAG_TEST_DATE_UNPARSEABLE,)

    text = value.strip()
    if not text:
        return None, (FLAG_TEST_DATE_MISSING,)

    if _CAMPAIGN_RANGE.fullmatch(text):
        return None, (FLAG_TEST_DATE_CAMPAIGN_RANGE,)

    try:
        if _ISO_DATE.fullmatch(text):
            return date.fromisoformat(text).isoformat(), ()
        if _US_DATE_4Y.fullmatch(text):
            return _parse_us_date(text, year_digits=4), ()
        if _US_DATE_2Y.fullmatch(text):
            return _parse_us_date(text, year_digits=2), ()
    except ValueError:
        return None, (FLAG_TEST_DATE_UNPARSEABLE,)

    return None, (FLAG_TEST_DATE_UNPARSEABLE,)


def _parse_us_date(text: str, *, year_digits: int) -> str:
    month, day, year_text = text.split("/")
    year = int(year_text)
    if year_digits == 2:
        year = _expand_two_digit_year(year)
    return date(year, int(month), int(day)).isoformat()


def _expand_two_digit_year(year: int) -> int:
    """Apply an explicit two-digit-year pivot.

    Values 00-68 map to 2000-2068 and 69-99 map to 1969-1999. The observed
    range in this dataset is 09-11, so every two-digit year becomes 2009-2011.
    The rule is stated in the data dictionary so it is never implicit.
    """

    if not 0 <= year <= 99:
        raise ValueError(f"Two-digit year out of range: {year}")
    return 2000 + year if year <= 68 else 1900 + year


def clean_test_dates(
    frame: pd.DataFrame, *, column: str = "test_date", raw_column: str = "test_date_raw"
) -> tuple[pd.DataFrame, DateParseStats]:
    """Parse ``column`` into ISO dates, retaining the original in ``raw_column``."""

    cleaned = frame.copy()
    originals = cleaned[column].tolist()
    parsed = [parse_test_date(value) for value in originals]

    cleaned[raw_column] = originals
    cleaned[column] = [item[0] for item in parsed]
    for index, (_, flags) in enumerate(parsed):
        for flag in flags:
            _append_flag(cleaned, index, flag)

    campaign_ranges: Counter[str] = Counter()
    unparseable: Counter[str] = Counter()
    missing = 0
    converted = 0
    for value, (iso_value, flags) in zip(originals, parsed, strict=True):
        if iso_value is not None and isinstance(value, str):
            text = value.strip()
            if _US_DATE_4Y.fullmatch(text) or _US_DATE_2Y.fullmatch(text):
                converted += 1
        for flag in flags:
            if flag == FLAG_TEST_DATE_MISSING:
                missing += 1
            elif flag == FLAG_TEST_DATE_CAMPAIGN_RANGE:
                campaign_ranges[str(value)] += 1
            elif flag == FLAG_TEST_DATE_UNPARSEABLE:
                unparseable[str(value)] += 1

    stats = DateParseStats(
        total=len(originals),
        missing=missing,
        parsed=sum(1 for iso_value, _ in parsed if iso_value is not None),
        converted=converted,
        campaign_ranges=dict(sorted(campaign_ranges.items())),
        unparseable=dict(sorted(unparseable.items())),
    )
    return cleaned, stats


def load_vocabulary_config(path: Path) -> dict[str, Any]:
    """Load the versioned vocabulary YAML file."""

    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: vocabulary mapping must be a mapping")
    version = payload.get("version")
    if not isinstance(version, int):
        raise ValueError(f"{path}: missing integer 'version'")
    return cast(dict[str, Any], payload)


def normalize_vocabulary(
    frame: pd.DataFrame,
    *,
    column: str,
    config: dict[str, Any],
    raw_column: str | None = None,
) -> tuple[pd.DataFrame, VocabularyStats]:
    """Apply one explicit vocabulary mapping from ``config``.

    The original column is preserved in ``{column}_raw``. Values without a
    mapping entry pass through unchanged and are reported as identity values.
    """

    section = config.get(column)
    if not isinstance(section, dict):
        raise ValueError(f"vocabulary config has no section for {column!r}")
    entries = section.get("mappings") or {}
    if not isinstance(entries, dict):
        raise ValueError(f"vocabulary config section {column!r} must contain a mapping")

    mapping: dict[str, str] = {}
    for key, value in entries.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise ValueError(f"invalid mapping entry for {column}: {key!r}")
        target = value.get("to")
        if not isinstance(target, str):
            raise ValueError(f"mapping entry {key!r} for {column} is missing string 'to'")
        mapping[key] = target

    version = str(config.get("version", "unknown"))
    cleaned = frame.copy()
    raw_name = raw_column or f"{column}_raw"
    originals = cleaned[column].tolist()
    cleaned[raw_name] = pd.Series(originals, index=cleaned.index, dtype=object)
    cleaned[column] = pd.Series(
        [_apply_mapping(value, mapping) for value in originals],
        index=cleaned.index,
        dtype=object,
    )

    applied_counter: Counter[tuple[str, str]] = Counter()
    identity_counter: Counter[str] = Counter()
    null_count = 0
    for value in originals:
        if _is_missing(value):
            null_count += 1
            continue
        text = str(value)
        if text in mapping:
            applied_counter[(text, mapping[text])] += 1
        else:
            identity_counter[text] += 1

    stats = VocabularyStats(
        column=column,
        mapping_version=version,
        total_non_null=sum(applied_counter.values()) + sum(identity_counter.values()),
        null_count=null_count,
        applied=tuple(
            (source, target, count) for (source, target), count in sorted(applied_counter.items())
        ),
        identity=dict(sorted(identity_counter.items())),
    )
    return cleaned, stats


def _apply_mapping(value: object, mapping: dict[str, str]) -> object:
    if _is_missing(value):
        return value
    if not isinstance(value, str):
        return value
    return mapping.get(value, value)


def quarantine_airflow(
    frame: pd.DataFrame,
    *,
    threshold_cms: float,
    column: str = "airflow_velocity_cms",
    raw_column: str = "airflow_velocity_cms_raw",
) -> tuple[pd.DataFrame, AirflowStats]:
    """Null airflow values above ``threshold_cms`` and preserve them raw.

    The threshold catches concatenated free-text readings (the 42 BASS-II
    values above 1000 cm/s). No repair is attempted: the audit found no
    documented basis for splitting the concatenated digits.
    """

    if threshold_cms <= 0:
        raise ValueError("airflow quarantine threshold must be positive")

    cleaned = frame.copy()
    originals = cleaned[column]
    cleaned[raw_column] = originals
    values = pd.to_numeric(originals, errors="coerce")
    mask = values.notna() & (values > threshold_cms)
    cleaned[column] = values.mask(mask)

    quarantined: list[QuarantinedAirflow] = []
    for index in cleaned.index[mask]:
        quarantined.append(
            QuarantinedAirflow(
                experiment_id=str(cleaned.at[index, "experiment_id"]),
                dataset_family=str(cleaned.at[index, "dataset_family"]),
                source_file=str(cleaned.at[index, "source_file"])
                if "source_file" in cleaned.columns
                else "",
                source_row=int(cast(Any, cleaned.at[index, "source_row"]))
                if "source_row" in cleaned.columns
                else -1,
                value=float(cast(Any, values.at[index])),
            )
        )

    for index in cleaned.index[mask]:
        _append_flag(cleaned, index, FLAG_AIRFLOW_QUARANTINED)

    stats = AirflowStats(
        threshold_cms=threshold_cms,
        total=len(cleaned),
        missing=int(values.isna().sum()),
        quarantined=tuple(quarantined),
    )
    return cleaned, stats


def flag_pressure_and_burn_time(
    frame: pd.DataFrame, *, burn_time_max_s: float
) -> tuple[pd.DataFrame, NumericFlagStats]:
    """Add flags for suspicious pressure and burn-time values without editing them."""

    if burn_time_max_s <= 0:
        raise ValueError("burn_time_max_s must be positive")

    cleaned = frame.copy()
    pressure_mmhg = pd.to_numeric(cleaned["pressure_mmhg"], errors="coerce")
    pressure_kpa = pd.to_numeric(cleaned["pressure_kpa"], errors="coerce")
    burn_time = pd.to_numeric(cleaned["burn_time_s"], errors="coerce")

    pressure_zero_mask = pressure_mmhg.fillna(-1.0) == 0.0
    kpa_missing_mask = pressure_kpa.isna()
    burn_zero_mask = burn_time.fillna(-1.0) == 0.0
    burn_large_mask = burn_time.notna() & (burn_time > burn_time_max_s)

    for mask, flag in (
        (pressure_zero_mask, FLAG_PRESSURE_MMHG_ZERO),
        (kpa_missing_mask, FLAG_PRESSURE_KPA_MISSING),
        (burn_zero_mask, FLAG_BURN_TIME_ZERO),
        (burn_large_mask, FLAG_BURN_TIME_IMPLAUSIBLE),
    ):
        for index in cleaned.index[mask]:
            _append_flag(cleaned, index, flag)

    pressure_zero = tuple(str(value) for value in cleaned.loc[pressure_zero_mask, "experiment_id"])
    pressure_kpa_missing = tuple(
        str(value) for value in cleaned.loc[kpa_missing_mask, "experiment_id"]
    )
    burn_time_zero = tuple(str(value) for value in cleaned.loc[burn_zero_mask, "experiment_id"])
    burn_time_implausible = tuple(
        (
            str(cleaned.at[index, "experiment_id"]),
            float(cast(Any, burn_time.at[index])),
        )
        for index in cleaned.index[burn_large_mask]
    )

    stats = NumericFlagStats(
        counts={
            FLAG_PRESSURE_MMHG_ZERO: int(pressure_zero_mask.sum()),
            FLAG_PRESSURE_KPA_MISSING: int(kpa_missing_mask.sum()),
            FLAG_BURN_TIME_ZERO: int(burn_zero_mask.sum()),
            FLAG_BURN_TIME_IMPLAUSIBLE: int(burn_large_mask.sum()),
        },
        pressure_zero=pressure_zero,
        pressure_kpa_missing=pressure_kpa_missing,
        burn_time_zero=burn_time_zero,
        burn_time_implausible=burn_time_implausible,
    )
    return cleaned, stats


def _append_flag(frame: pd.DataFrame, index: Any, flag: str) -> None:
    """Append a flag to the internal ``_flags`` list column."""

    if "_flags" not in frame.columns:
        frame["_flags"] = pd.Series(
            [[] for _ in range(len(frame))], index=frame.index, dtype=object
        )
    current: Any = frame.at[index, "_flags"]
    if not isinstance(current, list):
        current = []
    if flag not in current:
        frame.at[index, "_flags"] = cast(Any, sorted({*current, flag}))
