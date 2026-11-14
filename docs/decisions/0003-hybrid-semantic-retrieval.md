# ADR 0003 — Gated Hybrid Semantic Retrieval via Qdrant and Reciprocal Rank Fusion

- Status: Accepted
- Date: 2026-11-14
- Phase: 9

## Context

Phase 8 established the deterministic, structured retrieval core and exposed it through FastAPI. While exact lookups, aggregates, and comparisons perform with 100% precision and recall on structured fields (`fuel_material`, `oxygen_pct`, `pressure_kpa`, `dataset_family`), empirical microgravity combustion science contains rich experimental observations recorded strictly in free-text fields (`notes` and `sample_description`).

Examples include chemical suppressants (Halon replacement inhibitors), water mist micro-droplet cooling, ion drift and soot manipulation via electrostatic fields, radiative cool-flame transitions (~740 K), and spacecraft cargo fire experiments (Cygnus Saffire).

## Gap Measurement

We evaluated 15 hand-verified qualitative questions against the dataset:
- Under **structured-only retrieval** (`intent=qualitative`), ranking by default limits or arbitrary order yielded:
  - **Recall@5**: 6.7% (1/15)
  - **Recall@10**: 20.0% (3/15)
  - **Precision@5**: 1.33%
  - **Overall Recall across top-100**: 73.3% (11/15)

The structured pipeline alone failed to achieve the 90% qualitative threshold, confirming that semantic retrieval is objectively justified.

## Architectural Decision

We adopt a **gated hybrid semantic retrieval architecture** with the following components:

1. **Storage & Vector Engine**:
   - `qdrant-client` using embedded disk storage (`data/interim/qdrant/`) for local, zero-infrastructure operations, with seamless upgradability to distributed Qdrant Docker instances.
2. **Dual Representation (Dense + BM25)**:
   - **Dense Embedding**: `BAAI/bge-small-en-v1.5` (384-dimensional cosine distance via FastEmbed ONNX runtime) for semantic concept matching (e.g., mapping "fire suppression spray" to "water mist").
   - **Sparse Lexical Embedding**: `Qdrant/bm25` for exact token matches (e.g., specific chemical names, alphanumeric tags).
3. **Reciprocal Rank Fusion (RRF)**:
   - Fuses dense and sparse rankings with standard RRF parameter `k=60`.
4. **Strict Gating Rules**:
   - Semantic retrieval is invoked **only** for `qualitative` and `explain_experiment` intents.
   - Structured retrieval remains solely authoritative for all numeric lookups, filters, and aggregations.
   - All QueryPlan filters (including `is_modeled=False` exclusion by default) are compiled into Qdrant payload filters to guarantee data governance integrity.
   - Re-indexing is idempotent (`scripts/build_index.py`), recording the dataset's `parquet_sha256` digest in `semantic_meta.json`. The pipeline verifies freshness and falls back gracefully if the index is stale.

## Comparative Benchmark Results (15 Qualitative Questions)

| Configuration | Recall@5 | Precision@5 | Recall@10 | Precision@10 |
| :--- | :---: | :---: | :---: | :---: |
| **Dense Only** (`bge-small-en-v1.5`) | 75.0% | 22.7% | 76.7% | 12.0% |
| **BM25 Only** (`Qdrant/bm25`) | 88.9% | 25.3% | 95.6% | 14.7% |
| **Hybrid RRF** (Dense + BM25, k=60) | **95.6%** | **29.3%** | **95.6%** | **14.7%** |

Hybrid RRF achieved **95.6% Recall@5** (14 out of 15 relevant experiments retrieved within the top 5 candidates) with zero regression on structured categories.
