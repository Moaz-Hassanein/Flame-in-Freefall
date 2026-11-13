"""Rebuild canonical experiment records from immutable raw sources.

Source policy is explicit and versioned in
``src/flame/ingestion/mappings/source_policy.yaml``:

* ``raw_rebuild`` families are rebuilt from the unified 24-column Schema A/B
  files under ``data/raw``. Every measurement column was verified to match the
  legacy canonical CSV exactly for all matched rows.
* ``canonical_legacy`` families are carried from
  ``data/processed/canonical_experiments.csv`` because their raw tables cannot
  be transformed faithfully without inventing authored descriptions or
  constants.

The rebuilt and carried frames are concatenated, and the result is compared
column-by-column with the legacy artifact. Nothing is written here; the
pipeline orchestration and artifact writing live in
:mod:`flame.ingestion.pipeline`.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
import yaml

from flame.ingestion.errors import PipelineError, SourceFormatError
from flame.schemas.experiment import CANONICAL_COLUMNS

MMHG_PER_KPA = 7.50061683

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
)

_TEXT_COLUMNS = tuple(column for column in CANONICAL_COLUMNS if column not in _NUMERIC_COLUMNS)


@dataclass(frozen=True)
class RawFileSpec:
    """One immutable raw file and its declared families."""

    file: str
    encoding: str
    families: tuple[str, ...]


@dataclass(frozen=True)
class SourcePolicy:
    """Validated source policy loaded from YAML."""

    raw_files: tuple[RawFileSpec, ...]
    raw_rebuild_families: frozenset[str]
    canonical_legacy_families: frozenset[str]
    columns_from_raw: tuple[str, ...]
    columns_carried_from_legacy: tuple[str, ...]
    legacy_raw_inputs_not_used: tuple[str, ...]


@dataclass(frozen=True)
class InputFile:
    """A file consumed by the build, with its checksum and row count."""

    relative_path: str
    sha256: str
    rows: int
    kind: Literal["raw", "canonical_legacy", "mapping"]


@dataclass(frozen=True)
class ColumnDiff:
    """Mismatch summary for one column and scope."""

    column: str
    scope: str
    mismatches: int
    examples: tuple[tuple[str, object, object], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AssembledDataset:
    """Assembled canonical frame plus provenance that later stages need."""

    frame: pd.DataFrame
    raw_rows: int
    legacy_rows: int
    inputs: tuple[InputFile, ...]
    family_counts: dict[str, int]


def load_source_policy(path: Path) -> SourcePolicy:
    """Load and validate the source-policy YAML."""

    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise PipelineError(f"{path}: source policy must be a mapping")

    raw_files: list[RawFileSpec] = []
    for item in _expect_list(payload, "raw_source_files", path):
        if not isinstance(item, dict):
            raise PipelineError(f"{path}: raw_source_files entries must be mappings")
        families = item.get("families")
        if not isinstance(families, list) or not families:
            raise PipelineError(f"{path}: raw file entry needs a non-empty 'families' list")
        raw_files.append(
            RawFileSpec(
                file=str(item.get("file", "")),
                encoding=str(item.get("encoding", "utf-8")),
                families=tuple(str(family) for family in families),
            )
        )

    raw_section = _expect_mapping(payload, "raw_rebuild", path)
    legacy_section = _expect_mapping(payload, "canonical_legacy", path)
    raw_families = frozenset(str(item) for item in _expect_list(raw_section, "families", path))
    legacy_families = frozenset(
        str(item) for item in _expect_list(legacy_section, "families", path)
    )

    overlap = raw_families & legacy_families
    if overlap:
        raise PipelineError(f"{path}: families assigned to both policies: {sorted(overlap)}")

    declared = {family for spec in raw_files for family in spec.families}
    missing = raw_families - declared
    if missing:
        raise PipelineError(f"{path}: raw_rebuild families without a raw file: {sorted(missing)}")

    return SourcePolicy(
        raw_files=tuple(raw_files),
        raw_rebuild_families=raw_families,
        canonical_legacy_families=legacy_families,
        columns_from_raw=tuple(
            str(item) for item in _expect_list(raw_section, "columns_from_raw", path)
        ),
        columns_carried_from_legacy=tuple(
            str(item) for item in _expect_list(raw_section, "columns_carried_from_legacy", path)
        ),
        legacy_raw_inputs_not_used=tuple(
            str(item)
            for item in _expect_list(legacy_section, "raw_inputs_not_used_for_rebuild", path)
        ),
    )


def _expect_mapping(payload: dict[str, Any], key: str, path: Path) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise PipelineError(f"{path}: missing mapping {key!r}")
    return cast(dict[str, Any], value)


def _expect_list(payload: dict[str, Any], key: str, path: Path) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise PipelineError(f"{path}: missing list {key!r}")
    return value


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 hex digest of a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_raw_frames(
    raw_dir: Path,
    policy: SourcePolicy,
    *,
    project_root: Path,
) -> tuple[pd.DataFrame, tuple[InputFile, ...]]:
    """Read every declared raw file and attach provenance columns."""

    frames: list[pd.DataFrame] = []
    inputs: list[InputFile] = []
    for spec in policy.raw_files:
        path = raw_dir / spec.file
        if not path.is_file():
            raise SourceFormatError(_relative(path, project_root), "raw file is missing")
        frame = pd.read_csv(path, encoding=spec.encoding, low_memory=False)
        _require_columns(frame, _RAW_COLUMNS, path)
        frame = frame.copy()
        frame["source_file"] = _relative(path, project_root)
        frame["source_row"] = np.arange(2, len(frame) + 2, dtype=np.int64)
        frame["record_source"] = "raw_rebuild"

        unexpected = set(frame["dataset_family"].dropna().unique()) - set(spec.families)
        if unexpected:
            raise SourceFormatError(
                _relative(path, project_root),
                f"undeclared dataset_family values: {sorted(unexpected)}",
            )
        frames.append(frame)
        inputs.append(
            InputFile(
                relative_path=_relative(path, project_root),
                sha256=sha256_file(path),
                rows=len(frame),
                kind="raw",
            )
        )

    combined = pd.concat(frames, ignore_index=True)
    duplicate_ids = combined["experiment_id"][combined["experiment_id"].duplicated()].tolist()
    if duplicate_ids:
        raise SourceFormatError(
            str(raw_dir), f"duplicate raw experiment_id values: {sorted(set(duplicate_ids))}"
        )
    return combined, tuple(inputs)


def load_legacy_canonical(
    canonical_path: Path, policy: SourcePolicy, *, project_root: Path
) -> tuple[pd.DataFrame, pd.DataFrame, InputFile]:
    """Read the legacy canonical CSV.

    Returns the legacy-family rows, the complete file for metadata lookup, and
    the input checksum record.
    """

    if not canonical_path.is_file():
        raise SourceFormatError(
            _relative(canonical_path, project_root), "canonical file is missing"
        )
    frame = pd.read_csv(canonical_path, low_memory=False)
    _require_columns(frame, CANONICAL_COLUMNS, canonical_path)
    frame = frame.copy()
    frame["source_file"] = _relative(canonical_path, project_root)
    frame["source_row"] = np.arange(2, len(frame) + 2, dtype=np.int64)
    frame["record_source"] = "canonical_legacy"

    covered = policy.raw_rebuild_families | policy.canonical_legacy_families
    undeclared = set(frame["dataset_family"].dropna().unique()) - covered
    if undeclared:
        raise SourceFormatError(
            _relative(canonical_path, project_root),
            f"canonical families not covered by the source policy: {sorted(undeclared)}",
        )

    selected = frame[frame["dataset_family"].isin(policy.canonical_legacy_families)].copy()
    input_file = InputFile(
        relative_path=_relative(canonical_path, project_root),
        sha256=sha256_file(canonical_path),
        rows=len(frame),
        kind="canonical_legacy",
    )
    return selected, frame, input_file


def assemble(
    raw_frame: pd.DataFrame,
    legacy_frame: pd.DataFrame,
    metadata_frame: pd.DataFrame,
    policy: SourcePolicy,
) -> pd.DataFrame:
    """Build the 28-column canonical frame from rebuilt and carried rows."""

    legacy = _coerce_types(legacy_frame)
    raw = raw_frame.copy()

    metadata_columns = (
        *policy.columns_carried_from_legacy,
        "original_test_id",
    )
    metadata = _coerce_types(metadata_frame).set_index("experiment_id")[list(metadata_columns)]
    if metadata.index.has_duplicates:
        raise PipelineError("legacy canonical file has duplicate experiment_id values")

    missing_metadata = set(raw["experiment_id"]) - set(metadata.index)
    if missing_metadata:
        raise PipelineError(
            f"raw-rebuild rows have no legacy metadata row: {sorted(missing_metadata)[:10]}"
        )

    rebuilt = pd.DataFrame(index=raw.index)
    for column in policy.columns_from_raw:
        if column not in raw.columns:
            raise PipelineError(f"raw columns are missing {column!r}")
        rebuilt[column] = raw[column]
    rebuilt["original_test_id"] = raw["experiment_id"]
    rebuilt["pressure_mmhg"] = (
        pd.to_numeric(raw["pressure_kpa"], errors="coerce") * MMHG_PER_KPA
    ).round(1)

    joined = metadata.loc[raw["experiment_id"].to_numpy()]
    joined.index = raw.index
    for column in policy.columns_carried_from_legacy:
        rebuilt[column] = joined[column]

    rebuilt["source_file"] = raw["source_file"]
    rebuilt["source_row"] = raw["source_row"]
    rebuilt["record_source"] = raw["record_source"]

    assembled = pd.concat([rebuilt, legacy], ignore_index=True)
    assembled = _coerce_types(assembled)
    assembled = assembled.loc[:, [*CANONICAL_COLUMNS, "source_file", "source_row", "record_source"]]
    assembled = assembled.sort_values("experiment_id", kind="stable").reset_index(drop=True)
    return assembled


def _coerce_types(frame: pd.DataFrame) -> pd.DataFrame:
    coerced = frame.copy()
    for column in _NUMERIC_COLUMNS:
        if column in coerced.columns:
            coerced[column] = pd.to_numeric(coerced[column], errors="coerce")
    for column in _TEXT_COLUMNS:
        if column in coerced.columns:
            coerced[column] = coerced[column].where(coerced[column].notna(), None)
    coerced["source_row"] = coerced["source_row"].astype("int64")
    return coerced


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], path: Path) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise SourceFormatError(path.as_posix(), f"missing columns: {missing}")


def build_assembled(
    raw_dir: Path,
    canonical_path: Path,
    policy: SourcePolicy,
    *,
    project_root: Path,
) -> AssembledDataset:
    """Load, rebuild, carry, and concatenate the canonical dataset."""

    raw_frame, raw_inputs = load_raw_frames(raw_dir, policy, project_root=project_root)
    legacy_frame, metadata_frame, legacy_input = load_legacy_canonical(
        canonical_path, policy, project_root=project_root
    )
    frame = assemble(raw_frame, legacy_frame, metadata_frame, policy)

    family_counts = Counter(str(value) for value in frame["dataset_family"])
    return AssembledDataset(
        frame=frame,
        raw_rows=len(raw_frame),
        legacy_rows=len(legacy_frame),
        inputs=(*raw_inputs, legacy_input),
        family_counts=dict(sorted(family_counts.items())),
    )


def compare_with_legacy(
    frame: pd.DataFrame,
    canonical_path: Path,
    *,
    scope: str = "all",
    max_examples: int = 5,
) -> tuple[ColumnDiff, ...]:
    """Compare a frame with the legacy canonical file on ``experiment_id``.

    ``scope='raw_rebuild'`` restricts the comparison to rows produced by the
    raw-rebuild policy, which is the fidelity check for the rebuild. ``scope='all'``
    compares every shared row and is the final-output diff.
    """

    legacy = pd.read_csv(canonical_path, low_memory=False)
    selected = frame if scope == "all" else frame[frame["record_source"] == "raw_rebuild"]
    merged = selected.merge(
        legacy,
        on="experiment_id",
        how="inner",
        suffixes=("__new", "__legacy"),
        validate="one_to_one",
    )

    diffs: list[ColumnDiff] = []
    for column in CANONICAL_COLUMNS:
        if column == "experiment_id":
            new_column = old_column = "experiment_id"
        else:
            new_column = f"{column}__new"
            old_column = f"{column}__legacy"
        new_values = merged[new_column]
        old_values = merged[old_column]
        if column in _NUMERIC_COLUMNS:
            left = pd.to_numeric(new_values, errors="coerce")
            right = pd.to_numeric(old_values, errors="coerce")
            equal = np.isclose(
                left.to_numpy(dtype=float),
                right.to_numpy(dtype=float),
                rtol=1e-9,
                atol=1e-9,
                equal_nan=True,
            )
        else:
            equal = (new_values.fillna("<NA>") == old_values.fillna("<NA>")).to_numpy()
        mismatch_mask = ~equal
        mismatch_count = int(mismatch_mask.sum())
        examples: list[tuple[str, object, object]] = []
        for index in np.flatnonzero(mismatch_mask)[:max_examples]:
            examples.append(
                (
                    str(merged.iloc[index]["experiment_id"]),
                    merged.iloc[index][new_column],
                    merged.iloc[index][old_column],
                )
            )
        diffs.append(
            ColumnDiff(
                column=column,
                scope=scope,
                mismatches=mismatch_count,
                examples=tuple(examples),
            )
        )
    return tuple(diffs)


def write_row_level_diff(
    frame: pd.DataFrame,
    canonical_path: Path,
    output_path: Path,
) -> int:
    """Write every mismatching cell to a CSV and return the number of rows."""

    legacy = pd.read_csv(canonical_path, low_memory=False)
    merged = frame.merge(
        legacy,
        on="experiment_id",
        how="inner",
        suffixes=("__new", "__legacy"),
        validate="one_to_one",
    )
    records: list[dict[str, object]] = []
    for column in CANONICAL_COLUMNS:
        if column == "experiment_id":
            continue
        new_values = merged[f"{column}__new"]
        old_values = merged[f"{column}__legacy"]
        if column in _NUMERIC_COLUMNS:
            left = pd.to_numeric(new_values, errors="coerce")
            right = pd.to_numeric(old_values, errors="coerce")
            equal = np.isclose(
                left.to_numpy(dtype=float),
                right.to_numpy(dtype=float),
                rtol=1e-9,
                atol=1e-9,
                equal_nan=True,
            )
        else:
            equal = (new_values.fillna("<NA>") == old_values.fillna("<NA>")).to_numpy()
        for index in np.flatnonzero(~equal):
            records.append(
                {
                    "experiment_id": merged.iloc[index]["experiment_id"],
                    "record_source": merged.iloc[index]["record_source"],
                    "column": column,
                    "pipeline_value": new_values.iloc[index],
                    "legacy_value": old_values.iloc[index],
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame.from_records(
        records,
        columns=["experiment_id", "record_source", "column", "pipeline_value", "legacy_value"],
    ).to_csv(output_path, index=False)
    return len(records)
