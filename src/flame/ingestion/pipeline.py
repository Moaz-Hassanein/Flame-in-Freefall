"""End-to-end ingestion orchestration and deterministic artifact writers."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from flame.ingestion.canonicalize import (
    AssembledDataset,
    ColumnDiff,
    InputFile,
    build_assembled,
    compare_with_legacy,
    load_source_policy,
    sha256_file,
    write_row_level_diff,
)
from flame.ingestion.clean import (
    FLAG_AIRFLOW_QUARANTINED,
    FLAG_BURN_TIME_IMPLAUSIBLE,
    FLAG_BURN_TIME_ZERO,
    FLAG_PRESSURE_KPA_MISSING,
    FLAG_PRESSURE_MMHG_ZERO,
    FLAG_TEST_DATE_CAMPAIGN_RANGE,
    FLAG_TEST_DATE_MISSING,
    FLAG_TEST_DATE_UNPARSEABLE,
    AirflowStats,
    DateParseStats,
    NumericFlagStats,
    VocabularyStats,
    clean_test_dates,
    flag_pressure_and_burn_time,
    load_vocabulary_config,
    normalize_vocabulary,
    quarantine_airflow,
)
from flame.ingestion.enrich import (
    ExtractionStats,
    ModeledRuleStats,
    PatternStats,
    apply_modeled_rules,
    extract_text_facts,
    finalize_quality_flags,
    load_modeled_rules,
)
from flame.ingestion.errors import PipelineError
from flame.ingestion.validate import (
    FLAG_AIRFLOW_NEGATIVE,
    FLAG_BURN_TIME_NEGATIVE,
    FLAG_BURNING_RATE_NEGATIVE,
    FLAG_DIAMETER_NEGATIVE,
    FLAG_EMISSIONS_NEGATIVE,
    FLAG_FLAME_TEMP_OUT_OF_RANGE,
    FLAG_GAS_FRACTION_OUT_OF_RANGE,
    FLAG_IGNITION_NEGATIVE,
    FLAG_OXYGEN_OUT_OF_RANGE,
    FLAG_PRESSURE_NEGATIVE,
    FLAG_PRESSURE_UNIT_MISMATCH,
    SoftValidationStats,
    collect_soft_flags,
    require_verified_patterns,
    validate_hard,
)
from flame.schemas.experiment import CANONICAL_COLUMNS, ENRICHMENT_COLUMNS

PIPELINE_VERSION = "0.3.0"

FLAG_DESCRIPTIONS: dict[str, str] = {
    FLAG_TEST_DATE_MISSING: "test_date was empty.",
    FLAG_TEST_DATE_CAMPAIGN_RANGE: "test_date was a campaign range, not a date; nulled.",
    FLAG_TEST_DATE_UNPARSEABLE: "test_date did not match a supported format; nulled.",
    FLAG_AIRFLOW_QUARANTINED: "airflow_velocity_cms above the quarantine threshold; nulled.",
    FLAG_PRESSURE_MMHG_ZERO: "pressure_mmhg is zero; value retained.",
    FLAG_PRESSURE_KPA_MISSING: "pressure_kpa is null; value retained.",
    FLAG_BURN_TIME_ZERO: "burn_time_s is zero; value retained.",
    FLAG_BURN_TIME_IMPLAUSIBLE: "burn_time_s exceeds the plausibility maximum; value retained.",
    FLAG_OXYGEN_OUT_OF_RANGE: "oxygen_pct outside 0-100; value retained.",
    FLAG_PRESSURE_NEGATIVE: "A pressure value is negative; value retained.",
    FLAG_PRESSURE_UNIT_MISMATCH: "pressure_mmhg and pressure_kpa disagree beyond tolerance.",
    FLAG_BURN_TIME_NEGATIVE: "burn_time_s is negative; value retained.",
    FLAG_DIAMETER_NEGATIVE: "A diameter is negative; value retained.",
    FLAG_BURNING_RATE_NEGATIVE: "burning_rate_mms is negative; value retained.",
    FLAG_AIRFLOW_NEGATIVE: "airflow_velocity_cms is negative; value retained.",
    FLAG_FLAME_TEMP_OUT_OF_RANGE: (
        "flame_temp_k outside the soft plausibility window; value retained."
    ),
    FLAG_GAS_FRACTION_OUT_OF_RANGE: "A gas fraction is outside 0-100; value retained.",
    FLAG_EMISSIONS_NEGATIVE: "co_ppm is negative; value retained.",
    FLAG_IGNITION_NEGATIVE: "An ignition value is negative; value retained.",
}

_MEASUREMENT_COLUMNS = (
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

_VOCABULARY_COLUMNS = (
    "extinction_outcome",
    "material_category",
    "fuel_material",
    "gravity_condition",
)


@dataclass(frozen=True)
class PipelineConfig:
    """Files and thresholds needed for one build."""

    raw_dir: Path
    canonical_path: Path
    source_policy_path: Path
    vocabularies_path: Path
    modeled_rules_path: Path
    canonical_diff_path: Path
    airflow_threshold_cms: float
    burn_time_max_s: float
    project_root: Path


@dataclass(frozen=True)
class PipelineResult:
    """Everything the artifact writers and tests need from a build."""

    frame: pd.DataFrame
    assembled: AssembledDataset
    date_stats: DateParseStats
    vocabulary_stats: tuple[VocabularyStats, ...]
    airflow_stats: AirflowStats
    numeric_stats: NumericFlagStats
    modeled_stats: ModeledRuleStats
    extraction_stats: ExtractionStats
    soft_stats: SoftValidationStats
    flag_counts: dict[str, int]
    assembly_diffs: tuple[ColumnDiff, ...]
    final_diffs: tuple[ColumnDiff, ...]
    row_diff_records: int
    inputs: tuple[InputFile, ...]


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Rebuild, clean, enrich, validate, and compare the dataset."""

    policy = load_source_policy(config.source_policy_path)
    assembled = build_assembled(
        config.raw_dir,
        config.canonical_path,
        policy,
        project_root=config.project_root,
    )

    assembly_diffs = compare_with_legacy(
        assembled.frame, config.canonical_path, scope="raw_rebuild"
    )

    frame = assembled.frame.copy()

    frame, date_stats = clean_test_dates(frame)

    vocabulary_config = load_vocabulary_config(config.vocabularies_path)
    vocabulary_stats: list[VocabularyStats] = []
    for column in _VOCABULARY_COLUMNS:
        frame, stats = normalize_vocabulary(frame, column=column, config=vocabulary_config)
        vocabulary_stats.append(stats)

    frame, airflow_stats = quarantine_airflow(frame, threshold_cms=config.airflow_threshold_cms)
    frame, numeric_stats = flag_pressure_and_burn_time(
        frame, burn_time_max_s=config.burn_time_max_s
    )

    modeled_config = load_modeled_rules(config.modeled_rules_path)
    frame, modeled_stats = apply_modeled_rules(frame, modeled_config)
    frame, extraction_stats = extract_text_facts(frame)
    require_verified_patterns(extraction_stats)

    frame, soft_stats = collect_soft_flags(frame)
    frame, flag_counts = finalize_quality_flags(frame)

    validate_hard(frame, context="experiments dataset")

    final_diffs = compare_with_legacy(frame, config.canonical_path, scope="all")
    row_diff_records = write_row_level_diff(
        frame, config.canonical_path, config.canonical_diff_path
    )

    mapping_inputs = tuple(
        InputFile(
            relative_path=_relative(path, config.project_root),
            sha256=sha256_file(path),
            rows=0,
            kind="mapping",
        )
        for path in (
            config.source_policy_path,
            config.vocabularies_path,
            config.modeled_rules_path,
        )
    )

    return PipelineResult(
        frame=frame,
        assembled=assembled,
        date_stats=date_stats,
        vocabulary_stats=tuple(vocabulary_stats),
        airflow_stats=airflow_stats,
        numeric_stats=numeric_stats,
        modeled_stats=modeled_stats,
        extraction_stats=extraction_stats,
        soft_stats=soft_stats,
        flag_counts=flag_counts,
        assembly_diffs=assembly_diffs,
        final_diffs=final_diffs,
        row_diff_records=row_diff_records,
        inputs=(*assembled.inputs, *mapping_inputs),
    )


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def generated_at_from_environment() -> datetime:
    """Use ``SOURCE_DATE_EPOCH`` when set so repeated builds are byte-identical."""

    import os

    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is None:
        return datetime.now(tz=UTC).replace(microsecond=0)
    try:
        return datetime.fromtimestamp(int(epoch), tz=UTC)
    except ValueError as error:
        raise PipelineError(f"SOURCE_DATE_EPOCH must be an integer, got {epoch!r}") from error


def git_commit(project_root: Path) -> str | None:
    """Return the current commit hash, or ``None`` outside a git checkout."""

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    commit = completed.stdout.strip()
    return commit or None


def write_parquet(frame: pd.DataFrame, output_path: Path) -> str:
    """Write the dataset in a fixed column order and return its SHA-256."""

    column_order = [*CANONICAL_COLUMNS, *ENRICHMENT_COLUMNS]
    missing = [column for column in column_order if column not in frame.columns]
    if missing:
        raise PipelineError(f"cannot write parquet; missing columns: {missing}")

    ordered = frame.loc[:, column_order].copy()
    ordered = ordered.sort_values("experiment_id", kind="stable").reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ordered.to_parquet(output_path, index=False, compression="zstd")
    return sha256_file(output_path)


def build_manifest(
    result: PipelineResult,
    *,
    generated_at: datetime,
    commit: str | None,
    parquet_sha256: str,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    """Build the deterministic provenance manifest payload."""

    frame = result.frame
    row_counts = {
        "total": len(frame),
        "raw_rebuild": int((frame["record_source"] == "raw_rebuild").sum()),
        "canonical_legacy": int((frame["record_source"] == "canonical_legacy").sum()),
        "by_family": {
            str(family): int(count)
            for family, count in sorted(Counter(frame["dataset_family"]).items())
        },
    }
    inputs = [
        {
            "path": item.relative_path,
            "sha256": item.sha256,
            "rows": item.rows,
            "kind": item.kind,
        }
        for item in sorted(result.inputs, key=lambda item: item.relative_path)
    ]
    return {
        "pipeline": {
            "name": "flame-ingestion",
            "version": PIPELINE_VERSION,
        },
        "generated_at": generated_at.isoformat(),
        "git_commit": commit,
        "inputs": inputs,
        "outputs": {
            "parquet_path": "data/processed/experiments.parquet",
            "parquet_sha256": parquet_sha256,
            "rows": len(frame),
        },
        "row_counts": row_counts,
        "thresholds": thresholds,
        "is_modeled": {
            "count": result.modeled_stats.total,
            "rule_counts": result.modeled_stats.rule_counts,
        },
        "quarantined_airflow": {
            "count": len(result.airflow_stats.quarantined),
            "threshold_cms": result.airflow_stats.threshold_cms,
        },
        "flags": result.flag_counts,
        "source_policy": {
            "raw_rebuild": sorted(
                set(frame.loc[frame["record_source"] == "raw_rebuild", "dataset_family"])
            ),
            "canonical_legacy": sorted(
                set(frame.loc[frame["record_source"] == "canonical_legacy", "dataset_family"])
            ),
        },
    }


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    """Write the manifest with stable key order and a trailing newline."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_quality_report(
    result: PipelineResult,
    *,
    generated_at: datetime,
    commit: str | None,
    manifest: dict[str, Any],
) -> str:
    """Render the Markdown quality report."""

    frame = result.frame
    lines: list[str] = []
    lines.append("# Data quality report")
    lines.append("")
    lines.append(f"- Generated at: `{generated_at.isoformat()}`")
    lines.append(f"- Pipeline version: `{PIPELINE_VERSION}`")
    lines.append(f"- Git commit: `{commit or 'unknown'}`")
    lines.append(f"- Rows: **{len(frame)}**")
    lines.append("")

    lines.extend(_section_row_counts(result))
    lines.extend(_section_source_policy(result))
    lines.extend(_section_assembly_diff(result))
    lines.extend(_section_final_diff(result))
    lines.extend(_section_flags(result))
    lines.extend(_section_nulls(result))
    lines.extend(_section_vocabularies(result))
    lines.extend(_section_quarantine(result))
    lines.extend(_section_modeled(result))
    lines.extend(_section_extraction(result))
    lines.extend(_section_soft_violations(result))
    lines.extend(_section_inputs(manifest))
    lines.extend(_section_pending())
    return "\n".join(lines) + "\n"


def _section_row_counts(result: PipelineResult) -> list[str]:
    frame = result.frame
    lines = ["## Row counts", "", "| Group | Rows |", "|:--|--:|"]
    lines.append(f"| Total | {len(frame)} |")
    lines.append(f"| Rebuilt from raw | {(frame['record_source'] == 'raw_rebuild').sum()} |")
    legacy_count = int((frame["record_source"] == "canonical_legacy").sum())
    lines.append(f"| Carried from legacy canonical | {legacy_count} |")
    lines.append("")
    lines.append("| Family | Rows | Source |")
    lines.append("|:--|--:|:--|")
    for family, count in sorted(Counter(frame["dataset_family"]).items()):
        source = frame.loc[frame["dataset_family"] == family, "record_source"].iloc[0]
        lines.append(f"| {family} | {count} | {source} |")
    lines.append("")
    return lines


def _section_source_policy(result: PipelineResult) -> list[str]:
    assembled = result.assembled
    lines = [
        "## Source policy",
        "",
        "Raw-rebuild families were rebuilt from immutable Schema A/B files. Legacy "
        "families were carried from the existing canonical CSV because their raw "
        "tables are free-text logs with authored descriptions and constants that "
        "cannot be reconstructed without inventing transformations.",
        "",
        f"- Raw-rebuild rows: **{assembled.raw_rows}**",
        f"- Legacy-carried rows: **{assembled.legacy_rows}**",
        "",
    ]
    return lines


def _section_assembly_diff(result: PipelineResult) -> list[str]:
    lines = [
        "## Rebuild fidelity (raw-rebuild rows, before cleaning)",
        "",
        "Every measurement column is compared with the legacy canonical CSV on the "
        "450 rows rebuilt from raw. A non-zero count is a known provenance difference, "
        "not a silent loss.",
        "",
        "| Column | Mismatches | Example (experiment_id, pipeline, legacy) |",
        "|:--|--:|:--|",
    ]
    for difference in result.assembly_diffs:
        if difference.mismatches == 0:
            continue
        example = ""
        if difference.examples:
            experiment_id, new_value, old_value = difference.examples[0]
            example = f"`{experiment_id}`: `{new_value!r}` vs `{old_value!r}`"
        lines.append(f"| {difference.column} | {difference.mismatches} | {example} |")
    if all(difference.mismatches == 0 for difference in result.assembly_diffs):
        lines.append("| (none) | 0 | — |")
    lines.append("")
    return lines


def _section_final_diff(result: PipelineResult) -> list[str]:
    lines = [
        "## Final output versus legacy canonical",
        "",
        f"Row-level mismatches written to `data/reports/canonical_diff.csv`: "
        f"**{result.row_diff_records}** cells.",
        "",
        "| Column | Mismatches |",
        "|:--|--:|",
    ]
    for difference in result.final_diffs:
        if difference.mismatches:
            lines.append(f"| {difference.column} | {difference.mismatches} |")
    if all(difference.mismatches == 0 for difference in result.final_diffs):
        lines.append("| (none) | 0 |")
    lines.append("")
    lines.append(
        "Expected final-output differences are: date normalisation (M/D/YYYY and "
        "M/D/YY converted to ISO), nulled campaign-range dates, quarantined BASS-II "
        "airflow values, the explicit vocabulary mappings, and the SLICE source/notes "
        "wording that the raw file does not contain. Raw values remain in the `*_raw` "
        "columns."
    )
    lines.append("")
    return lines


def _section_flags(result: PipelineResult) -> list[str]:
    lines = ["## Quality flags", "", "| Flag | Count | Meaning |", "|:--|--:|:--|"]
    for flag, count in sorted(result.flag_counts.items()):
        meaning = FLAG_DESCRIPTIONS.get(flag, "Undocumented flag.")
        lines.append(f"| `{flag}` | {count} | {meaning} |")
    if not result.flag_counts:
        lines.append("| (none) | 0 | — |")
    lines.append("")
    return lines


def _section_nulls(result: PipelineResult) -> list[str]:
    frame = result.frame
    columns = [column for column in _MEASUREMENT_COLUMNS if column in frame.columns]
    lines = ["## Per-family null rates", "", "| Family | Rows | " + " | ".join(columns) + " |"]
    lines.append("|:--|--:|" + "|".join("--:" for _ in columns) + "|")
    for family, group in sorted(frame.groupby("dataset_family"), key=lambda item: str(item[0])):
        cells = [f"{group[column].isna().mean() * 100:.1f}%" for column in columns]
        lines.append(f"| {family} | {len(group)} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("Rates are percentages of null values within the family. No value was imputed.")
    lines.append("")
    return lines


def _section_vocabularies(result: PipelineResult) -> list[str]:
    lines = [
        "## Vocabulary mappings",
        "",
        "Only the entries below change a value. All other values pass through as identity.",
        "",
    ]
    for stats in result.vocabulary_stats:
        lines.append(f"### `{stats.column}` (mapping version {stats.mapping_version})")
        lines.append("")
        if stats.applied:
            lines.append("| Original | Normalised | Rows |")
            lines.append("|:--|:--|--:|")
            for source, target, count in stats.applied:
                lines.append(f"| `{source}` | `{target}` | {count} |")
        else:
            lines.append("No value is remapped in this build.")
        lines.append("")
        lines.append(
            f"- Non-null values: **{stats.total_non_null}**; null values: **{stats.null_count}**."
        )
        identity_values = ", ".join(f"`{value}`" for value in stats.identity)
        if identity_values:
            lines.append(f"- Identity values ({len(stats.identity)}): {identity_values}")
        else:
            lines.append("- Identity values: none")
        lines.append("")
    return lines


def _section_quarantine(result: PipelineResult) -> list[str]:
    stats = result.airflow_stats
    lines = [
        "## Quarantined airflow readings",
        "",
        f"Threshold: **{stats.threshold_cms:g} cm/s**. "
        f"Quarantined rows: **{len(stats.quarantined)}**. "
        f"Null before quarantine: **{stats.missing}**; "
        f"null after quarantine: **{stats.missing + len(stats.quarantined)}**.",
        "",
        "| experiment_id | Family | Source file | Row | Raw airflow (cm/s) |",
        "|:--|:--|:--|--:|--:|",
    ]
    for item in stats.quarantined:
        lines.append(
            f"| `{item.experiment_id}` | {item.dataset_family} | `{item.source_file}` | "
            f"{item.source_row} | {_format_number(item.value)} |"
        )
    if not stats.quarantined:
        lines.append("| (none) | — | — | — | — |")
    lines.append("")
    lines.append(
        "No repair is applied. The audit found these values originate from concatenated "
        "free-text `Fan display` / `Air display` fields and no documented rule separates them."
    )
    lines.append("")
    return lines


def _section_modeled(result: PipelineResult) -> list[str]:
    frame = result.frame
    modeled = frame[frame["is_modeled"]]
    lines = [
        "## Modeled rows",
        "",
        f"`is_modeled` is true for **{len(modeled)}** rows. Rules use family and gravity "
        "descriptors, never row identifiers.",
        "",
        "| Rule | Rows |",
        "|:--|--:|",
    ]
    for rule_id, count in result.modeled_stats.rule_counts.items():
        lines.append(f"| `{rule_id}` | {count} |")
    lines.append("")
    lines.append("| experiment_id | Family | Gravity condition |")
    lines.append("|:--|:--|:--|")
    for _, row in modeled.iterrows():
        lines.append(
            f"| `{row['experiment_id']}` | {row['dataset_family']} | {row['gravity_condition']} |"
        )
    lines.append("")
    return lines


def _section_extraction(result: PipelineResult) -> list[str]:
    lines = [
        "## Text extraction verification",
        "",
        "| Fact | Candidate rows | Matched rows | Verified | Unmatched values |",
        "|:--|--:|--:|:--:|:--|",
    ]
    for stats in (
        result.extraction_stats.specimen_dimensions,
        result.extraction_stats.flow_direction,
        result.extraction_stats.microgravity_duration,
        result.extraction_stats.pi_name,
    ):
        unmatched = _summarise_counter(stats)
        lines.append(
            f"| {stats.name} | {stats.candidate_rows} | {stats.matched_rows} | "
            f"{'yes' if stats.verified else 'no'} | {unmatched} |"
        )
    lines.append("")
    lines.append(
        "Patterns that did not verify cause the build to fail. Two SAFFIRE pre-test "
        "placeholder rows contain literal `Nonecm` dimensions and no numeric flow "
        "direction; they stay null and are counted as documented exceptions."
    )
    lines.append("")
    return lines


def _format_number(value: float) -> str:
    if value.is_integer():
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _summarise_counter(stats: PatternStats) -> str:
    parts: list[str] = []
    if stats.documented_exceptions:
        parts.append(
            "documented exceptions: "
            + ", ".join(
                f"`{value}` x {count}" for value, count in stats.documented_exceptions.items()
            )
        )
    if stats.unmatched_values:
        parts.append(
            "unmatched: "
            + ", ".join(f"`{value}` x {count}" for value, count in stats.unmatched_values.items())
        )
    return "; ".join(parts) if parts else "—"


def _section_soft_violations(result: PipelineResult) -> list[str]:
    lines = [
        "## Soft validation violations",
        "",
        "Soft violations are flagged, never fixed. Hard structural violations fail the build.",
        "",
        "| Flag | Rows |",
        "|:--|--:|",
    ]
    for flag, count in result.soft_stats.counts.items():
        lines.append(f"| `{flag}` | {count} |")
    if not result.soft_stats.counts:
        lines.append("| (none) | 0 |")
    lines.append("")
    return lines


def _section_inputs(manifest: dict[str, Any]) -> list[str]:
    lines = [
        "## Input checksums",
        "",
        "| Path | Kind | Rows | SHA-256 |",
        "|:--|:--|--:|:--|",
    ]
    for item in manifest["inputs"]:
        lines.append(f"| `{item['path']}` | {item['kind']} | {item['rows']} | `{item['sha256']}` |")
    lines.append("")
    return lines


def _section_pending() -> list[str]:
    return [
        "## Pending review",
        "",
        "The following decisions need owner approval before the dataset is treated as final:",
        "",
        "- The vocabulary mapping tables (see above). Semantic merges deliberately not applied "
        "are listed in `mappings/vocabularies.yaml` under `proposed_not_applied`.",
        "- The airflow quarantine threshold (default 1000 cm/s).",
        "- The burn-time plausibility maximum (default 3600 s).",
        "- The `UNVERIFIED` items in `docs/data_dictionary.md`, especially the cross-family "
        "meaning of `burning_rate_mms` and the provenance of `he_pct` for non-FLEX families.",
        "- Whether the 442 legacy-carried rows should ever be re-derived from their raw tables.",
        "",
    ]
