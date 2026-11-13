# Progress

## Phase status

| Phase | Status | Notes |
|:--:|:--|:--|
| 1 | **Complete** | Repository audit and agent rules. Dispositions approved at the start of Phase 2. |
| 2 | **Complete** | Project foundation, configuration, logging, and tooling. |
| 3 | **Complete** | Reproducible ingestion snapshot, validation, quality report, and data dictionary. |
| 4 | Not started | Scope defined by the Phase 4 prompt. |
| 5 | Not started | Scope defined by the Phase 5 prompt. |
| 6 | Not started | Scope defined by the Phase 6 prompt. |
| 7 | Not started | Scope defined by the Phase 7 prompt. |
| 8 | Not started | Scope defined by the Phase 8 prompt. |
| 9 | Not started | Scope defined by the Phase 9 prompt. |
| 10 | Not started | Scope defined by the Phase 10 prompt. |
| 11 | Not started | Scope defined by the Phase 11 prompt. |

## Phase log

### Phase 1 — Repository audit and agent rules

#### What was done

- Verified the repository state: branch `Moaz`, tracking `origin/Moaz`, clean working tree at audit start; no tags.
- Read all required non-data files in full: `main.py`, `exp.py`, `inventory_psi159.py`, `requirements.txt`, `.env.example`, `README.md`, `src/data/load_data.py`, and all three `src/analytics/*.py` files.
- Profiled all 17 raw CSVs for row count, columns, apparent units, schema family, and encoding.
- Validated the canonical CSV (`892 × 28`) against every known issue in the prompt, plus additional checks for row-count provenance, templated values, unit semantics, duplicate pressure columns, non-experiment rows, and date placeholders.
- Determined canonicalization reproducibility from the working tree and full git history.
- Reported the runtime environment (OS, Python, `uv`, Node, npm, pandas).
- Created `docs/AGENT_RULES.md` (verbatim rules), `docs/PROGRESS.md`, and `docs/audit/repo_audit.md`.

#### Files changed

- `docs/AGENT_RULES.md` (new)
- `docs/PROGRESS.md` (new)
- `docs/audit/repo_audit.md` (new)

No code, data, dependency, or configuration file was modified. Audit scripts were written under `/tmp/opencode` and are not part of the repository.

#### Tests run and results

- There is no automated test suite, test runner, or lint configuration in the repository, so no project tests could be run. This is itself recorded as a gap for later phases.
- `git status` and `git branch`: clean tree, branch `Moaz`, up to date with `origin/Moaz` — PASS.
- Read-only profiling scripts (`/tmp/opencode/audit_raw.py`, `audit_canonical.py`, `audit_canonical2.py`, `audit_canonical3.py`, `audit_canonical4.py`): all completed without error — PASS.
- Canonical shape assertion `(892, 28)`, unique-ID checks, `git log --all --name-only` provenance search — PASS.
- Documentation existence check after writing: all three files exist — PASS.

#### Acceptance criteria checked

1. `docs/AGENT_RULES.md`, `docs/PROGRESS.md`, `docs/audit/repo_audit.md` exist — **Met**.
2. The audit answers whether canonicalization is reproducible — **Met**: No; no generator exists in the tree or in any commit, and the canonical file contains values not present in `data/raw`.
3. The audit gives a disposition for every non-data file — **Met**: 13 non-data files (plus the packaging and data-directory entries) are covered in the disposition table.
4. `git status` shows only the three new docs files; commit locally and tag `phase-1-complete` — **Met at phase close**: only the three docs are added; the local commit and tag are created as the final action of this phase, and the working tree is clean afterward.

#### Issues found

- **Canonicalization is not reproducible.** No code reads `data/raw`; no pipeline script was ever committed (`assets/README.md` references a nonexistent `scripts/pipeline.py`); the canonical CSV and all raw files arrived in one commit.
- **Canonical row-count mismatch:** 890 raw rows plus 2 `NTRS` rows that exist in no raw file = 892.
- **BASS-II airflow corruption is confirmed:** 42 values > 1000 cm/s, max 5.105×10^15; caused by parsing multi-token `Fan display` / `Air display` text as single floats.
- **All six prompt-flagged issues are confirmed:** 52 modeled rows, corrupt airflow, mixed date formats, fragmented vocabularies (71/62/119 distinct labels), and structured family-specific nulls; the 892×28 shape is correct.
- **Additional serious issues:** campaign-level constant/templated values presented as measurements (e.g. BASS-II flame temperature has only two values for 129 rows; FLEX-2 burning rate is a constant `0.45`); burning rates with no source column (SAFFIRE, FLEX-2); implicit midpoint imputation for SAFFIRE-I oxygen; `co2_pct` conflating ambient diluent with combustion products; two non-experiment “pre-test flow visulation” rows; 12 zero-burning-rate placeholders; campaign-window dates used as test dates; 10 of 17 raw files already in canonical schema.
- **Documentation drift:** `assets/README.md` claims 29 investigations; the canonical file has 35.
- **Encoding trap:** `PSI-69_Experimental table_FLEX.csv` is `cp1252`, not UTF-8; naive ingestion fails.

#### Deviations from the prompt

- None in scope or constraints. The only additions beyond the literal task list are read-only checks for: templated/constant numeric infill, missing source columns, duplicate pressure representations, non-experiment rows, and per-file encodings. These directly support the disposition and reproducibility questions.
- The report is appended here as required by the agent rules; the physical file is one of the three permitted new files.

#### Remaining work

- Await user approval of the dispositions and of the canonicalization policy (re-derive from raw vs. preserve with provenance flags).
- Phase 2 must not consume the legacy canonical CSV as ground truth without the approved provenance policy.
- A test/lint configuration, typed package layout, and dependency manifest do not exist yet and must be introduced by the phase that owns them.

### Phase 2 — Restructure and project foundation

#### What was done

- Verified Phase 1 acceptance state: branch `Moaz`, clean tree, tag `phase-1-complete`, and the Phase 1 report.
- Applied the approved Phase 1 dispositions: removed the legacy scratch scripts, print-based analytics package, empty entry point, and old requirements file; rewrote the README and `.env.example`; corrected the dataset catalog; extended `.gitignore`.
- Replaced `requirements.txt` with a `uv`-managed `pyproject.toml` and committed `uv.lock`. Runtime dependencies are exactly the named set; development dependencies are exactly the named set. `requires-python = ">=3.11"`.
- Created the importable `src/flame/` package with `config.py`, `observability/logging.py`, and docstring-only `schemas`, `ingestion`, `retrieval`, `rag`, `llm`, and `api` packages.
- Implemented typed settings with `pydantic-settings`: environment-first loading, `.env` support, repository-root path resolution, validated log levels, masked LLM secrets, and a conditional rule requiring an API key when a provider is configured.
- Implemented JSON structured logging with stdlib `logging`, a request-id context variable, and recursive secret redaction for messages, structured extras, and exception text.
- Added `tests/unit` and `tests/integration`, `evaluation/`, `scripts/`, and `docs/decisions/0001-architecture.md`.
- Added ruff, strict mypy for `src/flame`, pytest/coverage configuration, `.pre-commit-config.yaml`, and a GitHub Actions lint/type/test workflow.
- Added `README.md` with purpose, architecture, setup, layout, and explicitly pending later-phase sections.

#### Files changed

New files:

- `pyproject.toml`, `uv.lock`
- `.pre-commit-config.yaml`, `.github/workflows/ci.yml`
- `src/flame/__init__.py`, `src/flame/config.py`
- `src/flame/schemas/__init__.py`, `src/flame/ingestion/__init__.py`, `src/flame/retrieval/__init__.py`, `src/flame/rag/__init__.py`, `src/flame/llm/__init__.py`, `src/flame/api/__init__.py`
- `src/flame/observability/__init__.py`, `src/flame/observability/logging.py`
- `tests/unit/test_config.py`, `tests/unit/test_logging.py`, `tests/integration/test_package_import.py`
- `evaluation/README.md`, `scripts/README.md`, `docs/decisions/0001-architecture.md`

Modified files:

- `README.md` (replaced with project documentation)
- `.env.example` (typed configuration keys, no real values)
- `.gitignore` (project caches, `.env`, `.venv`, `data/interim`, `node_modules`, `frontend/dist`, generated DuckDB files)
- `assets/README.md` (removed nonexistent `scripts/pipeline.py` claim, corrected 29 → 35 investigation identifiers, added provenance warning)
- `docs/PROGRESS.md` (status and this report)

Deleted files, contained in commit `d212447` (part of the Phase 2 work; recoverable from git history):

- `main.py` (empty placeholder; superseded by `src/flame/api/`)
- `exp.py` (scratch PSI downloader)
- `inventory_psi159.py` (one-off PSI-159 inventory)
- `requirements.txt` (replaced by `pyproject.toml` + `uv.lock`)
- `src/analytics/analytics.py`
- `src/analytics/advanced_analytics.py`
- `src/analytics/query_engine.py`
- `src/data/load_data.py` (path convention preserved in `flame.config`; loader belongs to the ingestion phase)

The new project structure, tooling, and documentation were captured in commit `cd5f1bd`. Both commits were created externally during this phase (see Issues). This report is the final `phase 2: project foundation and tooling` commit, and `phase-2-complete` tags the resulting tree.

#### Tests run and results

- Fresh environment: `rm -rf .venv && uv sync --locked` — **PASS**; uv selected managed CPython 3.12.13 and installed 58 resolved packages.
- `uv run ruff check .` — **PASS** (all checks passed).
- `uv run ruff format --check .` — **PASS** (21 files already formatted).
- `uv run mypy` — **PASS** (`Success: no issues found in 10 source files`; strict mode over `src/flame`).
- `uv run pytest` — **PASS** (25 passed; total coverage 95%; `config.py` 93%, `logging.py` 95%).
- `uv run python -c "import flame"` — **PASS**.
- Runtime/dev import smoke test (`pandas`, `pyarrow`, `duckdb`, `pandera`, `fastapi`, `uvicorn`, `httpx`, `pytest`, `pydantic_settings`) — **PASS**.
- `uv lock --check` — **PASS** (lockfile current).
- `uv run pre-commit validate-config .pre-commit-config.yaml` — **PASS**.
- GitHub Actions workflow YAML parse — **PASS**.
- Protected data integrity: SHA-256 checksums for all 17 `data/raw/*.csv` files and `data/processed/canonical_experiments.csv` are identical before and after; `git diff -- data/` is empty — **PASS**.

#### Acceptance criteria checked

1. `uv sync`, `ruff check`, `mypy`, and `pytest` all succeed — **Met**, verified from a fresh `.venv` with `--locked`.
2. `python -c "import flame"` works — **Met** under `uv run`.
3. `data/raw` and the canonical CSV are byte-identical to before — **Met**; all 18 SHA-256 hashes match and git reports no data diff.
4. No legacy analytics module remains — **Met**; all three `src/analytics/*.py` files are deleted, and no project file references them.
5. Local commit and tag `phase-2-complete` — **Met at phase close**; the commit contains all Phase 2 changes and is created immediately after this report.

#### Issues found

- **External commits appeared during the phase.** Commits `d212447` (“Remove deprecated files and modules from the project”) and `cd5f1bd` (“Refactor code structure for improved readability and maintainability”) were created by an external process under the environment user, not by the agent. They contain the Phase 2 deletions and foundation files. Per the agent rules, history was not rewritten or reset; the commits are preserved as-is. The working tree also reports `origin/Moaz` at the same commit, which the agent did not cause (no push command was run). The final `phase 2` commit adds only this report, and `phase-2-complete` tags the complete tree.
- `uv` resolved a managed CPython 3.12.13 instead of the system 3.14.4. This is compatible with `requires-python = ">=3.11"` and avoids wheel-availability risk; no action is required.
- Pre-commit hooks are local `uv run` hooks, so contributors need `uv` on `PATH`; this keeps hook versions aligned with `uv.lock`.
- Secret redaction is pattern-based (sensitive key names, bearer tokens, `sk-...` shapes). It covers the application’s known secret shapes but cannot guarantee redaction of arbitrary user text.
- The API package is intentionally empty; there is no ASGI `app` object or `uvicorn` entry point yet. That belongs to the API phase.
- `main.py` and `src/data/load_data.py` were deleted rather than left as placeholders because Phase 2 forbids API and ingestion logic. The reusable path convention now lives in `flame.config.PROJECT_ROOT` and the typed settings, with tests.

#### Deviations from the prompt

- The audit marked `main.py` as “Replace” and `src/data/load_data.py` as “Refactor”. Both were deleted because the replacement logic (FastAPI app, Parquet loader) belongs to later phases and this phase forbids that logic. The path/configuration portion of the loader was moved into `flame.config`.
- `uv_build` is used as the build backend. It ships with the `uv` toolchain and is not an additional project dependency.
- No other deviations; no dependency beyond the named runtime and development sets was added.

#### Remaining work

- Phase 3 ingestion: re-derive a validated Parquet snapshot from `data/raw` with documented provenance, or formally quarantine untraceable values.
- Add the ASGI application and `uvicorn` entry point in the API phase.
- Keep the legacy canonical CSV read-only and uncleared until the snapshot policy is approved and implemented.
