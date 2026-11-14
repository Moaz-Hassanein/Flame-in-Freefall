# Flame in Freefall

Structured-first hybrid RAG over NASA/JAXA microgravity combustion experiment data.

The project turns heterogeneous microgravity fire-safety experiments into a validated,
queryable dataset and answers natural-language questions with deterministic numbers and
verified citations.

## Architecture

1. An LLM produces a **typed query plan** (never raw SQL and never numbers).
2. The plan compiles to **parameterized DuckDB queries** over a validated **Parquet snapshot**.
3. A grounded answer is generated from the query results with **verified citations**.
4. Semantic retrieval (Qdrant hybrid) is **optional** and is gated by measured evaluation.

The backend is FastAPI. The planned frontend is React + TypeScript + Vite. The legacy
analytics scripts are not part of the product and have been removed.

## Data status

- `data/raw/` contains 17 source CSVs and is immutable.
- `data/processed/canonical_experiments.csv` is a **legacy artifact with unresolved provenance**.
  It is retained as a read-only reference until a deterministic ingestion pipeline re-derives
  a validated snapshot. See `docs/audit/repo_audit.md`.
- The audit found modeled partial-gravity rows, corrupt airflow values, mixed date formats,
  and templated values that must be labeled by provenance in later phases.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # optional local overrides; never commit .env
```

Run the quality gates:

```bash
uv run ruff check .
uv run mypy
uv run pytest
```

`uv sync` installs the project in editable mode, so `uv run python -c "import flame"` works.

## Layout

```text
src/flame/
├── config.py              # typed settings from environment and .env
├── schemas/               # Pydantic and Pandera data contracts
├── ingestion/             # raw ingestion and snapshot generation (later phase)
├── retrieval/             # typed query plans and DuckDB compilation (later phase)
├── rag/                   # grounded answers and citation verification (later phase)
├── llm/                   # provider abstractions and prompts (later phase)
├── api/                   # FastAPI application (later phase)
└── observability/         # JSON logging and request correlation

tests/unit/                # fast unit tests
tests/integration/         # cross-module smoke tests
evaluation/                # retrieval and answer-quality evaluation (later phases)
scripts/                   # operational scripts (later phases)
docs/decisions/            # architecture decision records
```

## Status

| Area | Status |
|:--|:--|
| Project foundation, configuration, logging, tooling | Complete (Phase 2) |
| Data ingestion and validated Parquet snapshot | Pending |
| Structured retrieval and query-plan compiler | Pending |
| Grounded answer generation and citations | Pending |
| Semantic retrieval and evaluation | Pending |
| FastAPI API and frontend | Pending |

## License

Apache-2.0. See `LICENSE`.

## Running the Application

The application consists of a FastAPI backend and a React + TypeScript frontend. Run each component in a separate terminal.

### 1. Start the Backend

From the project root, run:

```bash
uv run uvicorn flame.api.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at:

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs

### 2. Start the Frontend

Open a second terminal and navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev -- --host 0.0.0.0
```

The frontend will be available at:

- Frontend: http://localhost:5173

### 3. Stop the Application

Press `Ctrl + C` in each terminal to stop the backend and frontend servers.