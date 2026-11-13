"""Integration test: golden evaluation harness must achieve 100% on deterministic items.

Runs the full run_eval harness using the hand-written QueryPlans from the golden
set and asserts that every deterministic (non-expert, non-qualitative) item passes.
Items marked needs_expert are listed but excluded from the strict assertion.
"""

from __future__ import annotations

import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def test_golden_harness_deterministic_100_pct() -> None:
    """All deterministic golden questions must score 100% when plans are taken verbatim."""
    # Import here to keep test module importable even before evaluation/run_eval.py exists
    from evaluation.run_eval import run_evaluation  # type: ignore[import-not-found]

    summary = run_evaluation()

    # Collect any failures for a helpful error message
    failures = [r for r in summary["results"] if r.get("status") == "fail"]
    expert_items = [r for r in summary["results"] if r.get("needs_expert")]

    # Print expert items for the CI log
    if expert_items:
        print(f"\nItems requiring expert review ({len(expert_items)}):")
        for item in expert_items:
            print(f"  - {item['id']} ({item['category']}): {item['question']}")

    failure_lines = []
    for f in failures:
        failure_lines.append(f"  - {f['id']}: {f['question']}")
        for err in f.get("errors", []):
            failure_lines.append(f"    * {err}")

    assert summary["total_passed"] == summary["total_deterministic"], (
        f"Expected 100% pass rate on deterministic items but got "
        f"{summary['total_passed']}/{summary['total_deterministic']}.\n"
        f"Failures:\n" + "\n".join(failure_lines)
    )
    assert summary["deterministic_pass_rate_pct"] == 100.0, (
        f"Pass rate was {summary['deterministic_pass_rate_pct']}% instead of 100%."
    )


def test_golden_harness_expert_items_listed() -> None:
    """needs_expert items must be present and identifiable from the harness output."""
    from evaluation.run_eval import run_evaluation  # type: ignore[import-not-found]

    summary = run_evaluation()
    expert_ids = [r["id"] for r in summary["results"] if r.get("needs_expert")]

    assert len(expert_ids) == 6, (
        f"Expected exactly 6 needs_expert items, got {len(expert_ids)}: {expert_ids}"
    )
    assert set(expert_ids) == {"q45", "q46", "q47", "q48", "q49", "q50"}, (
        f"Unexpected expert IDs: {expert_ids}"
    )


def test_golden_harness_writes_results_artifacts() -> None:
    """The harness must write JSON and markdown artifacts to evaluation/results/."""
    from evaluation.run_eval import RESULTS_DIR, run_evaluation  # type: ignore[import-not-found]

    run_evaluation()

    latest_json = RESULTS_DIR / "latest.json"
    latest_md = RESULTS_DIR / "latest.md"

    assert latest_json.exists(), f"Expected {latest_json} to exist"
    assert latest_md.exists(), f"Expected {latest_md} to exist"
    assert latest_json.stat().st_size > 100, "latest.json is suspiciously small"
    assert latest_md.stat().st_size > 100, "latest.md is suspiciously small"
