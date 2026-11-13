# ADR 0001 — Structured-first hybrid retrieval architecture

- Status: Accepted
- Date: 2026-11-13
- Phase: 2

## Context

The source material is a heterogeneous collection of NASA/JAXA microgravity combustion
experiment tables. Questions mix exact structured facts (oxygen percentage, pressure,
burning rate, gravity regime, outcome) with qualitative evidence (facility, material,
experiment notes). A pure vector-search RAG system cannot guarantee correct aggregates or
exact filters, and an LLM must never invent scientific values.

The Phase 1 audit established that the existing canonical CSV is not reproducible from
`data/raw`, contains modeled and templated values, and has corrupt fields. The architecture
must therefore keep provenance and validation at the center.

## Decisions

1. **Structured-first hybrid retrieval.** Structured queries are the primary retrieval
   path. Semantic retrieval is additive and optional.
2. **Typed query plans.** The LLM emits a typed, validated query plan (Pydantic v2), not
   SQL and not answers containing numbers. Unsupported or ambiguous requests are rejected
   or clarified.
3. **Parameterized DuckDB compilation.** Query plans compile to parameterized DuckDB SQL
   over a validated Parquet snapshot. This prevents SQL injection and keeps execution
   deterministic.
4. **Validated Parquet snapshot.** Ingestion produces a typed, validated snapshot with
   explicit nullability, units, vocabulary mappings, and provenance labels. Pandera and
   Pydantic guard the boundary.
5. **Grounded answers with verified citations.** The answer layer may summarize and explain,
   but every displayed number comes from deterministic query execution and every claim is
   linked to row-level lineage (`source_file`, `source_row`, `original_test_id`).
6. **Semantic retrieval is gated.** Qdrant hybrid retrieval is introduced only if measured
   evaluation shows a benefit over the structured-first baseline. It must not bypass the
   validated dataset.
7. **FastAPI backend.** The HTTP boundary is FastAPI with Pydantic request/response models,
   typed configuration, JSON structured logging, and request correlation.
8. **React + TypeScript + Vite frontend.** The UI consumes the API and never computes
   scientific values itself.

## Consequences

- The query-plan schema and snapshot schema are the central contracts; they must be
  versioned and tested.
- Provenance is a first-class filter: measured, modeled, derived, imputed, and unknown
  values are distinguishable, and measured-only aggregates are the default.
- Evaluation must cover both retrieval quality and numeric correctness.
- LLM providers are replaceable behind an interface; API keys live only in environment
  variables loaded by `flame.config`.
- The legacy print-based analytics scripts are not reused.

## Deferred

- Canonical snapshot re-derivation from `data/raw` (Phase 3+).
- Query-plan grammar and DuckDB compiler (later phase).
- Answer generation and citation verification (later phase).
- Semantic retrieval and its evaluation gate (later phase).
