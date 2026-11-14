"""Advisory Ragas evaluation integration for faithfulness and context precision.

Ragas is used purely as an advisory metric layer and is skipped gracefully if
no LLM API key is present or if Ragas raises an evaluation error.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def compute_advisory_ragas_scores(
    dataset_records: list[dict[str, Any]],
) -> dict[str, float | None]:
    """Compute Faithfulness and ContextPrecision scores across answered questions.

    Each record in `dataset_records` should contain:
    - 'user_input': question string
    - 'response': answer string
    - 'retrieved_contexts': list of context strings
    """
    if not dataset_records:
        return {"ragas_faithfulness": None, "ragas_context_precision": None}

    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import faithfulness

        ds = Dataset.from_list(dataset_records)
        results = evaluate(
            ds,
            metrics=[faithfulness],
            raise_exceptions=False,
        )

        faithfulness_score = results.get("faithfulness")
        if faithfulness_score is not None and not isinstance(faithfulness_score, float):
            try:
                faithfulness_score = float(faithfulness_score)
            except (ValueError, TypeError):
                faithfulness_score = None

        return {
            "ragas_faithfulness": faithfulness_score,
            "ragas_context_precision": None,  # ContextPrecision requires ground truth context
        }
    except Exception as err:
        logger.info("Advisory Ragas evaluation skipped: %s", err)
        return {"ragas_faithfulness": None, "ragas_context_precision": None}


__all__ = ["compute_advisory_ragas_scores"]
