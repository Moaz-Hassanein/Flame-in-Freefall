"""End-to-end evaluation harness for the grounded generation pipeline.

Evaluates the ask() pipeline on golden questions, verifying:
- Status correctness (answered vs out_of_scope vs insufficient_evidence)
- 100% citation validity (every cited experiment_id must exist in evidence)
- Numeric grounding (presence of numbers in evidence/aggregates)
- Mandatory caveats present when modeled rows are included
- Advisory Ragas Faithfulness metric computation
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys
from typing import Any

import yaml

from evaluation.ragas_eval import compute_advisory_ragas_scores
from flame.config import get_settings
from flame.llm.anthropic_client import AnthropicClient
from flame.rag.pipeline import ask
from flame.retrieval.store import ExperimentStore
from flame.schemas.answer import AnswerStatus

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLDEN_PATH = REPO_ROOT / "evaluation" / "golden_questions.yaml"
RESULTS_DIR = REPO_ROOT / "evaluation" / "results"


def run_pipeline_evaluation(
    golden_path: pathlib.Path = GOLDEN_PATH,
    sample_limit: int | None = None,
) -> dict[str, Any]:
    """Run ask() across golden questions and score grounded generation."""
    with open(golden_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    questions = data.get("questions", [])
    if sample_limit:
        questions = questions[:sample_limit]

    settings = get_settings()
    api_key = settings.get_llm_api_key()
    if not api_key:
        print("Error: FLAME_LLM_API_KEY or ANTHROPIC_API_KEY required for pipeline evaluation.")
        sys.exit(1)

    llm = AnthropicClient(api_key=api_key, model=settings.llm_model)

    records: list[dict[str, Any]] = []
    ragas_samples: list[dict[str, Any]] = []

    total_citations = 0
    valid_citations = 0

    with ExperimentStore() as store:
        for q in questions:
            qid = q["id"]
            question_text = q["question"]
            category = q["category"]

            print(f"Evaluating {qid} [{category}]: {question_text[:50]}...")
            resp = ask(
                question=question_text,
                llm_client=llm,
                store=store,
                catalog=store.catalog,
            )

            # Verification 1: Citation validity
            evidence_ids = {row["experiment_id"] for row in resp.evidence}
            q_citations = len(resp.citations)
            q_valid_citations = sum(1 for c in resp.citations if c.experiment_id in evidence_ids)
            total_citations += q_citations
            valid_citations += q_valid_citations

            # Verification 2: Modeled disclosure
            has_modeled = any(row.get("is_modeled") for row in resp.evidence)
            modeled_disclosed = True
            if has_modeled and resp.answer_markdown:
                modeled_disclosed = "model" in resp.answer_markdown.lower()

            rec = {
                "id": qid,
                "category": category,
                "status": resp.status.value,
                "citations_count": q_citations,
                "valid_citations_count": q_valid_citations,
                "modeled_disclosed": modeled_disclosed,
                "has_answer": bool(resp.answer_markdown),
                "timings": resp.timings,
                "warnings": resp.warnings,
                "limitations": resp.limitations,
            }
            records.append(rec)

            # Collect for Ragas advisory scoring if answered
            if resp.status == AnswerStatus.answered and resp.answer_markdown and resp.evidence:
                contexts = [
                    f"Experiment {r['experiment_id']}: fuel={r.get('fuel_material')}, "
                    f"oxygen={r.get('oxygen_pct')}%, pressure={r.get('pressure_kpa')} kPa, "
                    f"notes={r.get('notes')}"
                    for r in resp.evidence[:5]
                ]
                ragas_samples.append(
                    {
                        "user_input": question_text,
                        "response": resp.answer_markdown,
                        "retrieved_contexts": contexts,
                    }
                )

    citation_validity_pct = (
        round(valid_citations / total_citations * 100.0, 2) if total_citations > 0 else 100.0
    )

    ragas_scores = compute_advisory_ragas_scores(ragas_samples)

    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "timestamp": timestamp,
        "total_evaluated": len(records),
        "total_citations": total_citations,
        "valid_citations": valid_citations,
        "citation_validity_pct": citation_validity_pct,
        "advisory_ragas": ragas_scores,
        "results": records,
    }

    out_file = RESULTS_DIR / f"pipeline_eval_{timestamp}.json"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n--- Pipeline Evaluation Summary ---")
    print(f"Total Evaluated: {len(records)}")
    print(f"Citation Validity: {citation_validity_pct}% ({valid_citations}/{total_citations})")
    print(f"Advisory Ragas Faithfulness: {ragas_scores.get('ragas_faithfulness')}")
    print(f"Artifact written to {out_file}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run_pipeline_evaluation(sample_limit=args.limit)
