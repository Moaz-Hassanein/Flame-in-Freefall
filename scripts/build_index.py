"""Idempotent semantic index builder for Flame in Freefall.

Indexes all records in data/processed/experiments.parquet into Qdrant
with dense and BM25 sparse vectors, saving snapshot version metadata.
"""

from __future__ import annotations

import argparse
import json
import logging

import pandas as pd
from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models

from flame.config import Settings, get_settings
from flame.retrieval.semantic import COLLECTION_NAME, METADATA_FILE, build_document_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flame.scripts.build_index")


def build_semantic_index(
    settings: Settings | None = None,
    force_rebuild: bool = False,
) -> None:
    cfg = settings or get_settings()
    parquet_path = cfg.dataset_output_path
    if not parquet_path.exists():
        raise FileNotFoundError(f"Dataset snapshot not found at {parquet_path}")

    qdrant_dir = cfg.qdrant_path
    qdrant_dir.mkdir(parents=True, exist_ok=True)
    meta_path = qdrant_dir / METADATA_FILE

    # Load manifest to get parquet sha256
    parquet_sha256 = None
    if cfg.provenance_manifest_path.exists():
        with open(cfg.provenance_manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
            parquet_sha256 = manifest.get("outputs", {}).get("parquet_sha256")

    # Check if index is up to date
    if not force_rebuild and meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            existing_meta = json.load(f)
        if existing_meta.get("parquet_sha256") == parquet_sha256:
            logger.info("Semantic index is already up to date with dataset version.")
            return

    logger.info("Building semantic index from %s...", parquet_path)
    df = pd.read_parquet(parquet_path)

    dense_model = TextEmbedding(model_name=cfg.embedding_model)
    sparse_model = SparseTextEmbedding(model_name=cfg.sparse_model)

    docs = [build_document_text(row) for _, row in df.iterrows()]
    logger.info("Embedding %d documents (dense + sparse)...", len(docs))

    dense_embeddings = list(dense_model.embed(docs))
    sparse_embeddings = list(sparse_model.embed(docs))

    client = QdrantClient(path=str(qdrant_dir))
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={"dense": models.VectorParams(size=384, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams()},
    )

    points = []
    for i, (_, row) in enumerate(df.iterrows()):
        sp = sparse_embeddings[i]
        points.append(
            models.PointStruct(
                id=i,
                vector={
                    "dense": dense_embeddings[i].tolist(),
                    "sparse": models.SparseVector(
                        indices=sp.indices.tolist(),
                        values=sp.values.tolist(),
                    ),
                },
                payload={
                    "experiment_id": str(row["experiment_id"]),
                    "dataset_family": str(row["dataset_family"]),
                    "fuel_material": str(row["fuel_material"]),
                    "is_modeled": bool(row["is_modeled"]),
                    "text": docs[i],
                },
            )
        )

    # Batch upload points
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    logger.info("Uploaded %d points to Qdrant collection '%s'.", len(points), COLLECTION_NAME)

    # Write metadata
    meta = {
        "parquet_sha256": parquet_sha256,
        "dense_model": cfg.embedding_model,
        "sparse_model": cfg.sparse_model,
        "total_points": len(points),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    logger.info("Index metadata successfully written to %s", meta_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Qdrant semantic index.")
    parser.add_argument("--force", action="store_true", help="Force index rebuild.")
    args = parser.parse_args()
    build_semantic_index(force_rebuild=args.force)
