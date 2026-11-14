#!/usr/bin/env python3
"""Build expected answers for the golden evaluation set using independent pandas code.

This script reads data/processed/experiments.parquet directly using pandas.
It must NOT call or import any code from src/flame/retrieval.
The computed results are written into evaluation/expected_answers.yaml and
can also update evaluation/golden_questions.yaml in place.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import pandas as pd
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PARQUET_PATH = REPO_ROOT / "data" / "processed" / "experiments.parquet"
GOLDEN_PATH = REPO_ROOT / "evaluation" / "golden_questions.yaml"
OUTPUT_PATH = REPO_ROOT / "evaluation" / "expected_answers.yaml"


def apply_pandas_filters(
    df: pd.DataFrame,
    filters: list[dict[str, Any]],
    include_modeled: bool = False,
) -> pd.DataFrame:
    """Filter DataFrame independently using pure pandas operations."""
    sub_df = df.copy()

    # Rule: Modeled rows are excluded by default unless include_modeled is true
    if not include_modeled:
        sub_df = sub_df[~sub_df["is_modeled"]]

    for f in filters:
        field = f["field"]
        op = f["op"]
        val = f.get("value")

        if op == "eq":
            sub_df = sub_df[sub_df[field] == val]
        elif op == "in":
            sub_df = sub_df[sub_df[field].isin(val)]
        elif op == "gte":
            sub_df = sub_df[sub_df[field] >= val]
        elif op == "lte":
            sub_df = sub_df[sub_df[field] <= val]
        elif op == "between":
            low, high = val
            sub_df = sub_df[(sub_df[field] >= low) & (sub_df[field] <= high)]
        elif op == "contains":
            # Case-insensitive substring match or list membership
            if field == "data_quality_flags":
                match_val = str(val).lower()
                sub_df = sub_df[
                    sub_df[field].apply(
                        lambda flags, target=match_val: (
                            any(target in str(flag).lower() for flag in flags)
                            if flags is not None
                            else False
                        )
                    )
                ]
            else:
                sub_df = sub_df[
                    sub_df[field]
                    .astype(str)
                    .str.contains(str(val), case=False, na=False, regex=False)
                ]
        elif op == "is_null":
            sub_df = sub_df[sub_df[field].isna()]
        elif op == "not_null":
            sub_df = sub_df[sub_df[field].notna()]
        else:
            raise ValueError(f"Unsupported independent filter op: {op}")

    return sub_df


def compute_expected_for_question(
    q: dict[str, Any],
    df: pd.DataFrame,
) -> dict[str, Any]:
    """Compute independent expected results for a single golden question."""
    qid = q["id"]
    category = q["category"]
    plan = q.get("plan", {})
    include_modeled = plan.get("include_modeled", False)
    filters = plan.get("filters", [])
    group_by = plan.get("group_by", [])
    aggregates = plan.get("aggregates", [])
    exp_ids = plan.get("experiment_ids")

    res: dict[str, Any] = {
        "id": qid,
        "category": category,
        "needs_expert": q.get("needs_expert", False),
    }

    if res["needs_expert"]:
        res["status"] = "needs_expert"
        res["expected_experiment_ids"] = []
        res["expected_aggregates"] = {}
        return res

    if category == "lookup":
        filtered = apply_pandas_filters(df, filters, include_modeled=include_modeled)
        res["expected_experiment_ids"] = sorted(filtered["experiment_id"].tolist())

    elif category == "aggregation":
        filtered = apply_pandas_filters(df, filters, include_modeled=include_modeled)
        expected_aggs: list[dict[str, Any]] = []

        if group_by:
            # Grouped aggregation
            grouped = filtered.groupby(group_by, dropna=False)
            for name, group in grouped:
                # pandas returns a tuple for each group name regardless of group_by length.
                # Unpack to scalars to match the DuckDB store's group_key format.
                name_tuple = name if isinstance(name, tuple) else (name,)
                group_key = dict(zip(group_by, name_tuple, strict=True))
                for agg in aggregates:
                    fn = agg["fn"]
                    field = agg["field"]

                    series = group[field]
                    # Exclude nulls
                    non_null = series.dropna()

                    # Handle quarantine exclusion for airflow
                    n_quarantined = 0
                    if field == "airflow_velocity_cms":
                        n_quarantined = int(
                            group["data_quality_flags"]
                            .apply(lambda flags: "AIRFLOW_QUARANTINED" in flags)
                            .sum()
                        )

                    n_null_total = int(series.isna().sum())
                    n_null_excluded = n_null_total - n_quarantined
                    n_used = len(non_null)

                    val: float | int | None = None
                    if n_used > 0:
                        if fn == "count":
                            val = len(group) if field == "experiment_id" else n_used
                        elif fn == "mean":
                            val = float(non_null.mean())
                        elif fn == "median":
                            val = float(non_null.median())
                        elif fn == "min":
                            val = float(non_null.min())
                        elif fn == "max":
                            val = float(non_null.max())

                    expected_aggs.append(
                        {
                            "fn": fn,
                            "field": field,
                            "value": val,
                            "n_used": n_used,
                            "n_null_excluded": n_null_excluded,
                            "n_quarantined_excluded": n_quarantined,
                            "group_key": group_key,
                        }
                    )
        else:
            # Ungrouped aggregation
            for agg in aggregates:
                fn = agg["fn"]
                field = agg["field"]

                series = filtered[field]
                non_null = series.dropna()

                n_quarantined = 0
                if field == "airflow_velocity_cms":
                    n_quarantined = int(
                        filtered["data_quality_flags"]
                        .apply(lambda flags: "AIRFLOW_QUARANTINED" in flags)
                        .sum()
                    )

                n_null_total = int(series.isna().sum())
                n_null_excluded = n_null_total - n_quarantined
                n_used = len(non_null)

                val = None
                if n_used > 0:
                    if fn == "count":
                        val = len(filtered) if field == "experiment_id" else n_used
                    elif fn == "mean":
                        val = float(non_null.mean())
                    elif fn == "median":
                        val = float(non_null.median())
                    elif fn == "min":
                        val = float(non_null.min())
                    elif fn == "max":
                        val = float(non_null.max())

                expected_aggs.append(
                    {
                        "fn": fn,
                        "field": field,
                        "value": val,
                        "n_used": n_used,
                        "n_null_excluded": n_null_excluded,
                        "n_quarantined_excluded": n_quarantined,
                        "group_key": None,
                    }
                )

        res["expected_aggregates"] = expected_aggs

    elif category == "explain_experiment":
        sub_df = df if include_modeled else df[~df["is_modeled"]]
        matched = sub_df[sub_df["experiment_id"].isin(exp_ids or [])]
        res["expected_experiment_ids"] = sorted(matched["experiment_id"].tolist())

    elif category in ("qualitative", "out_of_scope"):
        res["expected_experiment_ids"] = []
        res["expected_aggregates"] = []

    return res


def main() -> int:
    """Build expected answers and save to expected_answers.yaml."""
    if not PARQUET_PATH.exists():
        print(f"Error: {PARQUET_PATH} does not exist.", file=sys.stderr)
        return 1

    df = pd.read_parquet(PARQUET_PATH)

    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden_data = yaml.safe_load(f)

    questions = golden_data.get("questions", [])
    expected_results: dict[str, Any] = {}

    for q in questions:
        expected = compute_expected_for_question(q, df)
        expected_results[q["id"]] = expected

        # Update golden_questions entry with computed deterministic values
        if "expected_experiment_ids" in expected:
            q["expected_experiment_ids"] = expected["expected_experiment_ids"]
        if expected.get("expected_aggregates"):
            q["expected_aggregates"] = expected["expected_aggregates"]

    # Write independent expected_answers.yaml
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"expected": expected_results},
            f,
            sort_keys=False,
            default_flow_style=False,
        )

    # Re-save golden_questions.yaml with populated values
    with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            golden_data,
            f,
            sort_keys=False,
            default_flow_style=False,
        )

    print(
        f"Successfully computed independent expected values for {len(questions)} golden questions."
    )
    print(f"Artifacts saved to {OUTPUT_PATH} and {GOLDEN_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
