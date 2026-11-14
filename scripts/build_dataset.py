#!/usr/bin/env python
"""Build the trusted experiment dataset and its provenance artifacts.

Usage:
    uv run python scripts/build_dataset.py
    uv run python scripts/build_dataset.py --airflow-threshold 1000

The command is deterministic for a fixed ``SOURCE_DATE_EPOCH``. It never
modifies ``data/raw`` or the legacy canonical CSV.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flame.config import PROJECT_ROOT, Settings
from flame.ingestion.errors import PipelineError
from flame.ingestion.pipeline import (
    PipelineConfig,
    build_manifest,
    build_quality_report,
    generated_at_from_environment,
    git_commit,
    run_pipeline,
    write_manifest,
    write_parquet,
)
from flame.observability.logging import configure_logging


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--canonical", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--diff", type=Path, default=None)
    parser.add_argument("--airflow-threshold", type=float, default=None)
    parser.add_argument("--burn-time-max", type=float, default=None)
    parser.add_argument("--log-level", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = Settings(_env_file=None)

    raw_dir = args.raw_dir or settings.data_raw_dir
    canonical = args.canonical or settings.canonical_dataset_path
    output = args.output or settings.dataset_output_path
    manifest_path = args.manifest or settings.provenance_manifest_path
    report_path = args.report or settings.quality_report_path
    diff_path = args.diff or settings.canonical_diff_path
    airflow_threshold = (
        args.airflow_threshold
        if args.airflow_threshold is not None
        else settings.airflow_quarantine_threshold_cms
    )
    burn_time_max = (
        args.burn_time_max if args.burn_time_max is not None else settings.burn_time_max_s
    )

    configure_logging(args.log_level or settings.log_level)

    config = PipelineConfig(
        raw_dir=Path(raw_dir),
        canonical_path=Path(canonical),
        source_policy_path=settings.mappings_dir / "source_policy.yaml",
        vocabularies_path=settings.mappings_dir / "vocabularies.yaml",
        modeled_rules_path=settings.mappings_dir / "modeled_rows.yaml",
        canonical_diff_path=Path(diff_path),
        airflow_threshold_cms=float(airflow_threshold),
        burn_time_max_s=float(burn_time_max),
        project_root=PROJECT_ROOT,
    )

    try:
        result = run_pipeline(config)
        generated_at = generated_at_from_environment()
        parquet_sha256 = write_parquet(result.frame, Path(output))
        manifest = build_manifest(
            result,
            generated_at=generated_at,
            commit=git_commit(PROJECT_ROOT),
            parquet_sha256=parquet_sha256,
            thresholds={
                "airflow_quarantine_threshold_cms": config.airflow_threshold_cms,
                "burn_time_max_s": config.burn_time_max_s,
            },
        )
        write_manifest(manifest, Path(manifest_path))
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(
            build_quality_report(
                result,
                generated_at=generated_at,
                commit=git_commit(PROJECT_ROOT),
                manifest=manifest,
            ),
            encoding="utf-8",
        )
    except PipelineError as error:
        print(f"build failed: {error}", file=sys.stderr)
        return 1

    print(
        f"wrote {len(result.frame)} rows to {output}; "
        f"is_modeled={result.modeled_stats.total}; "
        f"quarantined_airflow={len(result.airflow_stats.quarantined)}; "
        f"parquet_sha256={parquet_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
