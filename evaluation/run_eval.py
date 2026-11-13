#!/usr/bin/env python3
"""Evaluation harness for golden questions and deterministic retrieval scoring.

Runs each expected QueryPlan through ExperimentStore, scores exact ID match on
lookups and numeric tolerance on aggregates, and writes a timestamped JSON
artifact and a markdown summary under evaluation/results/.

Provides a pluggable question-to-plan interface `QuestionToPlanCallable`
so Phase 6 can plug in an LLM planner and score plan accuracy.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import pathlib
import sys
from collections.abc import Callable
from typing import Any

import yaml

from flame.retrieval.store import ExperimentStore
from flame.retrieval.structured import RetrievalResult
from flame.schemas.query_plan import QueryPlan

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLDEN_PATH = REPO_ROOT / "evaluation" / "golden_questions.yaml"
RESULTS_DIR = REPO_ROOT / "evaluation" / "results"

# Type alias for a pluggable planner callable
QuestionToPlanCallable = Callable[[str], QueryPlan]


def default_plan_from_question(question_text: str) -> QueryPlan:
    """Default stub planner: looks up the hand-written QueryPlan from the golden set."""
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for q in data.get("questions", []):
        if q.get("question") == question_text:
            return QueryPlan.model_validate(q["plan"])
    raise KeyError(f"Question not found in golden set: {question_text!r}")


def score_numeric_value(
    got: float | int | None,
    expected: float | int | None,
    tol: float = 1e-4,
) -> bool:
    """Check if numeric values match within relative/absolute tolerance."""
    if got is None and expected is None:
        return True
    if got is None or expected is None:
        return False
    if math.isnan(got) and math.isnan(expected):
        return True
    if abs(expected) < 1e-6:
        return abs(got - expected) <= tol
    return abs(got - expected) / abs(expected) <= tol


def evaluate_question(
    q: dict[str, Any],
    store: ExperimentStore,
    planner: QuestionToPlanCallable,
) -> dict[str, Any]:
    """Execute plan for a question and score against expected results."""
    qid = q["id"]
    category = q["category"]
    question_text = q["question"]
    needs_expert = q.get("needs_expert", False)

    record: dict[str, Any] = {
        "id": qid,
        "category": category,
        "question": question_text,
        "needs_expert": needs_expert,
        "status": "pending",
        "errors": [],
    }

    if needs_expert:
        record["status"] = "needs_expert"
        record["message"] = "Marked as requiring expert or unanswerable / out of scope."
        return record

    if category in ("qualitative", "out_of_scope"):
        record["status"] = "skipped_qualitative"
        return record

    try:
        plan = planner(question_text)
    except Exception as err:
        record["status"] = "fail"
        record["errors"].append(f"Planner failed to generate plan: {err}")
        return record

    try:
        result: RetrievalResult = store.execute_plan(plan)
    except Exception as err:
        record["status"] = "fail"
        record["errors"].append(f"Store execution failed: {err}")
        return record

    # Evaluate based on category
    if category == "lookup":
        retrieved_ids = sorted([r["experiment_id"] for r in result.rows])
        expected_ids = sorted(q.get("expected_experiment_ids", []))

        if retrieved_ids == expected_ids:
            record["status"] = "pass"
            record["count_matched"] = len(retrieved_ids)
        else:
            record["status"] = "fail"
            record["errors"].append(
                f"Mismatch in experiment IDs: got {len(retrieved_ids)}, "
                f"expected {len(expected_ids)}"
            )
            record["details"] = {
                "got_sample": retrieved_ids[:5],
                "expected_sample": expected_ids[:5],
            }

    elif category == "aggregation":
        expected_aggs = q.get("expected_aggregates", [])
        retrieved_aggs = result.aggregates

        all_matched = True
        agg_comparisons = []

        if len(retrieved_aggs) != len(expected_aggs):
            all_matched = False
            record["errors"].append(
                f"Aggregate count mismatch: got {len(retrieved_aggs)} aggregates, "
                f"expected {len(expected_aggs)}"
            )

        # Match aggregates by fn, field, and group_key
        for exp in expected_aggs:
            exp_fn = exp["fn"]
            exp_field = exp["field"]
            exp_gk = exp.get("group_key")
            exp_val = exp.get("value")
            exp_used = exp.get("n_used")

            # Find matching retrieved aggregate
            match = None
            for ret in retrieved_aggs:
                if ret.fn == exp_fn and ret.field == exp_field and ret.group_key == exp_gk:
                    match = ret
                    break

            if match is None:
                all_matched = False
                record["errors"].append(
                    f"Missing aggregate: fn={exp_fn}, field={exp_field}, group_key={exp_gk}"
                )
                continue

            val_ok = score_numeric_value(match.value, exp_val)
            used_ok = match.n_used == exp_used

            agg_comparisons.append(
                {
                    "fn": exp_fn,
                    "field": exp_field,
                    "group_key": exp_gk,
                    "got_value": match.value,
                    "expected_value": exp_val,
                    "got_n_used": match.n_used,
                    "expected_n_used": exp_used,
                    "value_match": val_ok,
                    "used_match": used_ok,
                }
            )

            if not (val_ok and used_ok):
                all_matched = False
                record["errors"].append(
                    f"Aggregate mismatch on {exp_fn}({exp_field}): "
                    f"got value={match.value} (n_used={match.n_used}), "
                    f"expected value={exp_val} (n_used={exp_used})"
                )

        record["comparisons"] = agg_comparisons
        record["status"] = "pass" if all_matched else "fail"

    elif category == "explain_experiment":
        retrieved_ids = sorted([r["experiment_id"] for r in result.rows])
        expected_ids = sorted(q.get("expected_experiment_ids", []))

        if retrieved_ids == expected_ids:
            record["status"] = "pass"
            record["count_matched"] = len(retrieved_ids)
        else:
            record["status"] = "fail"
            record["errors"].append(
                f"Explain experiment ID mismatch: got {retrieved_ids}, expected {expected_ids}"
            )

    return record


def run_evaluation(
    golden_path: pathlib.Path = GOLDEN_PATH,
    planner: QuestionToPlanCallable = default_plan_from_question,
) -> dict[str, Any]:
    """Run full evaluation suite and return summary dict."""
    with open(golden_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    questions = data.get("questions", [])
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    category_stats: dict[str, dict[str, int]] = {}

    with ExperimentStore() as store:
        for q in questions:
            cat = q["category"]
            if cat not in category_stats:
                category_stats[cat] = {
                    "total": 0,
                    "pass": 0,
                    "fail": 0,
                    "needs_expert": 0,
                    "skipped": 0,
                }
            category_stats[cat]["total"] += 1

            rec = evaluate_question(q, store, planner)
            results.append(rec)

            st = rec["status"]
            if st == "pass":
                category_stats[cat]["pass"] += 1
            elif st == "fail":
                category_stats[cat]["fail"] += 1
            elif st == "needs_expert":
                category_stats[cat]["needs_expert"] += 1
            else:
                category_stats[cat]["skipped"] += 1

    total_deterministic = sum(s["pass"] + s["fail"] for s in category_stats.values())
    total_passed = sum(s["pass"] for s in category_stats.values())
    pass_rate = (total_passed / total_deterministic * 100.0) if total_deterministic > 0 else 0.0

    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")

    summary = {
        "timestamp": timestamp,
        "total_questions": len(questions),
        "total_deterministic": total_deterministic,
        "total_passed": total_passed,
        "deterministic_pass_rate_pct": round(pass_rate, 2),
        "category_stats": category_stats,
        "results": results,
    }

    # Write JSON results
    json_path = RESULTS_DIR / f"{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Write Markdown summary
    md_path = RESULTS_DIR / f"{timestamp}.md"
    md_content = generate_markdown_report(summary, json_path.name)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Also symlink / write latest.json and latest.md
    with open(RESULTS_DIR / "latest.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(RESULTS_DIR / "latest.md", "w", encoding="utf-8") as f:
        f.write(md_content)

    return summary


def generate_markdown_report(summary: dict[str, Any], json_filename: str) -> str:
    """Generate markdown summary for evaluation run."""
    ts = summary["timestamp"]
    lines = [
        f"# Golden Set Evaluation Report — {ts}",
        "",
        f"- **Timestamp:** `{ts}`",
        f"- **Raw JSON Artifact:** `evaluation/results/{json_filename}`",
        f"- **Total Questions:** {summary['total_questions']}",
        f"- **Deterministic Questions Evaluated:** {summary['total_deterministic']}",
        f"- **Passed:** {summary['total_passed']} / {summary['total_deterministic']}",
        f"- **Deterministic Pass Rate:** **{summary['deterministic_pass_rate_pct']}%**",
        "",
        "## Category Performance Breakdown",
        "",
        "| Category | Total | Pass | Fail | Needs Expert | Skipped | Pass Rate (Det) |",
        "|:---|---:|---:|---:|---:|---:|---:|",
    ]

    for cat, s in summary["category_stats"].items():
        det_total = s["pass"] + s["fail"]
        cat_rate = f"{(s['pass'] / det_total * 100.0):.1f}%" if det_total > 0 else "N/A"
        lines.append(
            f"| `{cat}` | {s['total']} | {s['pass']} | {s['fail']} | "
            f"{s['needs_expert']} | {s['skipped']} | {cat_rate} |"
        )

    lines.extend(
        [
            "",
            "## Questions Marked `needs_expert` (Unanswerable / Out of Scope)",
            "",
            "These items reflect domain boundaries (e.g. uncalibrated gravity extrapolations, "
            "corrupted airflow fields, or cross-family invalid combinations):",
            "",
        ]
    )

    for r in summary["results"]:
        if r.get("needs_expert"):
            lines.append(f"- **{r['id']}** ({r['category']}): {r['question']}")

    lines.extend(
        [
            "",
            "## Failure Log",
            "",
        ]
    )

    failures = [r for r in summary["results"] if r.get("status") == "fail"]
    if not failures:
        lines.append("No failures! All deterministic items passed 100%.")
    else:
        for f in failures:
            lines.append(f"- **{f['id']}**: {f['question']}")
            for err in f.get("errors", []):
                lines.append(f"  - Error: `{err}`")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run golden evaluation harness.")
    parser.add_argument(
        "--golden",
        type=pathlib.Path,
        default=GOLDEN_PATH,
        help="Path to golden questions YAML",
    )
    args = parser.parse_args()

    summary = run_evaluation(golden_path=args.golden)
    print(f"Evaluation finished at {summary['timestamp']}")
    print(
        f"Pass Rate: {summary['deterministic_pass_rate_pct']}% "
        f"({summary['total_passed']}/{summary['total_deterministic']})"
    )

    # Print category scores
    for cat, stats in summary["category_stats"].items():
        det = stats["pass"] + stats["fail"]
        rate = f"{(stats['pass'] / det * 100):.1f}%" if det > 0 else "N/A"
        print(
            f"  - {cat:20s}: pass={stats['pass']}/{det} ({rate}), "
            f"needs_expert={stats['needs_expert']}"
        )

    return 0 if summary["total_passed"] == summary["total_deterministic"] else 1


if __name__ == "__main__":
    sys.exit(main())
