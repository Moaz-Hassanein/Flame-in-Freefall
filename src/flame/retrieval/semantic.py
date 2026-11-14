"""Row-level document builder and Qdrant semantic index integration.

Builds structured textual representations of experiments and queries Qdrant
with dense (BGE-small), sparse (BM25), or hybrid RRF fusion.
Filters (including modeled-row exclusions) are strictly applied as payload filters.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd
from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models

from flame.config import Settings, get_settings
from flame.schemas.query_plan import FilterOperator, QueryPlan

logger = logging.getLogger("flame.retrieval.semantic")

COLLECTION_NAME = "experiments"
METADATA_FILE = "semantic_meta.json"


def build_document_text(row: dict[str, Any] | pd.Series) -> str:
    """Build a row-level retrieval document combining conditions and free-text notes."""
    eid = row.get("experiment_id", "")
    family = row.get("dataset_family", "")
    fuel = row.get("fuel_material", "")
    category = row.get("material_category", "")
    outcome = row.get("extinction_outcome", "")
    desc = row.get("sample_description", "")
    notes = row.get("notes", "")

    return (
        f"Experiment {eid}: family={family}, fuel={fuel}, category={category}, outcome={outcome}. "
        f"Description: {desc}. Notes: {notes}"
    )


class SemanticRetriever:
    """Manages Qdrant vector store and executes hybrid semantic search."""

    def __init__(
        self,
        client: QdrantClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or QdrantClient(path=str(self.settings.qdrant_path))
        self._dense_model: TextEmbedding | None = None
        self._sparse_model: SparseTextEmbedding | None = None

    @property
    def dense_model(self) -> TextEmbedding:
        if self._dense_model is None:
            self._dense_model = TextEmbedding(model_name=self.settings.embedding_model)
        return self._dense_model

    @property
    def sparse_model(self) -> SparseTextEmbedding:
        if self._sparse_model is None:
            self._sparse_model = SparseTextEmbedding(model_name=self.settings.sparse_model)
        return self._sparse_model

    def build_payload_filter(self, plan: QueryPlan) -> models.Filter:
        """Map QueryPlan filters to Qdrant payload filters."""
        must_conditions: list[models.Condition] = []

        # Rule: Exclude modeled rows unless explicitly included
        if not plan.include_modeled:
            must_conditions.append(
                models.FieldCondition(
                    key="is_modeled",
                    match=models.MatchValue(value=False),
                )
            )

        for f in plan.filters:
            field = f.field
            op = f.op
            val = f.value

            if op == FilterOperator.EQ:
                must_conditions.append(
                    models.FieldCondition(
                        key=field,
                        match=models.MatchValue(value=val),
                    )
                )
            elif op == FilterOperator.IN and isinstance(val, list):
                must_conditions.append(
                    models.FieldCondition(
                        key=field,
                        match=models.MatchAny(any=val),
                    )
                )

        return models.Filter(must=must_conditions if must_conditions else None)

    def search_hybrid(
        self,
        query_text: str,
        plan: QueryPlan,
        limit: int = 10,
    ) -> list[str]:
        """Perform hybrid RRF search (dense + BM25) and return ranked experiment IDs."""
        q_filter = self.build_payload_filter(plan)

        dense_vector = next(iter(self.dense_model.embed([query_text]))).tolist()
        sparse_vec = next(iter(self.sparse_model.embed([query_text])))

        sparse_query = models.SparseVector(
            indices=sparse_vec.indices.tolist(),
            values=sparse_vec.values.tolist(),
        )

        response = self.client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    filter=q_filter,
                    limit=limit * 2,
                ),
                models.Prefetch(
                    query=sparse_query,
                    using="sparse",
                    filter=q_filter,
                    limit=limit * 2,
                ),
            ],
            query=models.RrfQuery(rrf=models.Rrf(k=60)),
            limit=limit,
        )

        ranked_ids: list[str] = []
        for point in response.points:
            if point.payload and "experiment_id" in point.payload:
                ranked_ids.append(str(point.payload["experiment_id"]))

        return ranked_ids

    def verify_index_version(self, expected_sha256: str | None) -> bool:
        """Verify that index metadata matches the current Parquet snapshot version."""
        meta_path = self.settings.qdrant_path / METADATA_FILE
        if not meta_path.exists():
            return False
        try:
            with open(meta_path, encoding="utf-8") as f:
                data = json.load(f)
            return bool(data.get("parquet_sha256") == expected_sha256)
        except Exception:
            return False


__all__ = [
    "COLLECTION_NAME",
    "METADATA_FILE",
    "SemanticRetriever",
    "build_document_text",
]
