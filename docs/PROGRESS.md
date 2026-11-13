# Progress

## Phase status

| Phase | Status | Notes |
|:--:|:--|:--|
| 1 | **Complete** | Repository audit and agent rules. Dispositions approved at the start of Phase 2. |
| 2 | **Complete** | Project foundation, configuration, logging, and tooling. |
| 3 | **Complete** | Reproducible ingestion snapshot, validation, quality report, and data dictionary. |
| 4 | **Complete** | DuckDB store, QueryPlan schema, parameterized SQL compiler, structured retrieval, and catalog. |
| 5 | **Complete** | Golden evaluation set (50 questions), independent pandas answer builder, deterministic scoring harness, and integration tests. |
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

### Phase 3 — Reproducible ingestion, validation, and data quality

#### What was done

- Verified the Phase 2 base: tag `phase-2-complete`, 25 passing tests, and a clean working tree before Phase 3 changes.
- Re-inspected the legacy canonical CSV and all raw files. Confirmed that all 450 Schema A/B rows join one-to-one to the canonical CSV and that every physical measurement column matches exactly. Confirmed that the remaining 442 canonical rows have no faithful raw source.
- Added an explicit, versioned source policy in `src/flame/ingestion/mappings/source_policy.yaml`:
  - 18 families / 450 rows rebuilt from 11 immutable Schema A/B files under `data/raw`.
  - 12 families / 442 rows carried from `data/processed/canonical_experiments.csv`.
  - Six legacy raw files are declared unused for rebuild because reconstructing their rows would require authored descriptions, constants, or notes that are not in the raw columns.
- Added the Pydantic v2 `Experiment` and `DatasetRecord` models in `src/flame/schemas/experiment.py`, covering all 28 canonical columns with units in field metadata and structural optionality.
- Implemented pure cleaning functions in `src/flame/ingestion/clean.py`:
  - ISO date parsing for `YYYY-MM-DD`, `M/D/YYYY`, and `M/D/YY`, with an explicit two-digit-year pivot; campaign ranges are nulled with `TEST_DATE_CAMPAIGN_RANGE`.
  - Explicit vocabulary normalisation for `extinction_outcome`, `material_category`, `fuel_material`, and `gravity_condition`, with originals preserved in `*_raw`.
  - Airflow quarantine above 1000 cm/s; raw values preserved in `airflow_velocity_cms_raw`.
  - Flags, without edits, for zero/implausible burn times and zero/missing pressure values.
- Implemented enrichment in `src/flame/ingestion/enrich.py`:
  - `is_modeled` selected only by family and gravity-descriptor rules; exactly 52 rows (50 partial-g bounded + 2 LUCI/FM2 references).
  - Text-only extraction for SAFFIRE specimen dimensions and flow direction, GRC Drop Tower microgravity duration, and BASS-II PI surnames. Every pattern is verified against all candidate rows; two SAFFIRE pre-test placeholder rows are documented exceptions.
  - `data_quality_flags` finalised as a sorted list per row.
- Implemented hard and soft validation in `src/flame/ingestion/validate.py`: Pandera hard contracts fail the build; soft range violations become flags only.
- Implemented the end-to-end orchestration in `src/flame/ingestion/pipeline.py` and the CLI in `scripts/build_dataset.py`.
- Added `docs/data_dictionary.md` covering all 44 output columns, units, family applicability, caveats, flags, mappings, and explicit `UNVERIFIED` items.
- Generated the artifacts:
  - `data/processed/experiments.parquet` (892 rows x 44 columns)
  - `data/processed/provenance_manifest.json`
  - `data/reports/quality_report.md`
  - `data/reports/canonical_diff.csv` (502 differing cells against the legacy canonical CSV)

#### Files changed

New files:

- `src/flame/ingestion/canonicalize.py`, `clean.py`, `enrich.py`, `errors.py`, `pipeline.py`, `validate.py`
- `src/flame/ingestion/mappings/__init__.py`, `source_policy.yaml`, `vocabularies.yaml`, `modeled_rows.yaml`
- `src/flame/schemas/experiment.py`
- `scripts/build_dataset.py`
- `tests/unit/test_clean_dates.py`, `test_clean_numeric.py`, `test_clean_vocab.py`, `test_enrich.py`, `test_schemas.py`, `test_validate.py`
- `tests/integration/test_build_dataset.py`
- `docs/data_dictionary.md`
- `data/processed/experiments.parquet`, `data/processed/provenance_manifest.json`
- `data/reports/quality_report.md`, `data/reports/canonical_diff.csv`

Modified files:

- `pyproject.toml` (added `pyyaml>=6.0` at runtime; `pandas-stubs` and `types-PyYAML` for strict typing)
- `uv.lock`
- `src/flame/config.py` (artifact paths and ingestion thresholds)
- `.env.example` (new paths and thresholds)
- `docs/PROGRESS.md` (this report)

No file under `data/raw` and no `data/processed/canonical_experiments.csv` was modified; `git diff phase-2-complete -- data/raw data/processed/canonical_experiments.csv` is empty.

#### Tests run and results

- `uv run pytest` — **PASS**: 71 passed, total coverage 91% (`config.py` 94%, `canonicalize.py` 88%, `clean.py` 94%, `enrich.py` 94%, `pipeline.py` 88%, `validate.py` 94%, `logging.py` 95%).
- `uv run ruff check .` — **PASS**.
- `uv run ruff format --check .` — **PASS** (38 files formatted).
- `uv run mypy` — **PASS**: no issues in 18 source files.
- `SOURCE_DATE_EPOCH=1763070000 uv run python scripts/build_dataset.py` twice — **PASS**: all four artifacts byte-identical between runs.
- Final artifact hashes:
  - `experiments.parquet`: `4b3139dc07546aa01ab89b3a0b02411a25c02be681275b9619bda57aba7b33cf`
  - `provenance_manifest.json`: `89904fb69c84bf2cb821a66ab375145dbd3b2cc759b52e62323a52ba4330ac0a`
  - `quality_report.md`: `67db68e2b48f33689f77c0b3685cc9c7fdd5f61dab16478751a8f115180f6e16`
  - `canonical_diff.csv`: `4acf80fe5537150ae77da7af4d7c2b7e31abfa7df48438ffc6a7e820c33aa3d4`
- Pipeline summary from each run: 892 rows, `is_modeled=52`, `quarantined_airflow=42`, 892 unique `experiment_id` values.
- Hard validation passed on the full dataset; no soft range violations fired.

#### Acceptance criteria checked

1. **CLI twice produces identical output** — **Met**. All artifacts are byte-identical with a fixed `SOURCE_DATE_EPOCH`. The Parquet content is deterministic regardless; only the manifest/report timestamp changes without a fixed epoch.
2. **892 rows or a justified documented count** — **Met**: exactly 892 rows (450 raw-rebuild + 442 legacy-carried), matching the legacy canonical shape. The split and family counts are in the manifest and quality report.
3. **`is_modeled` exactly 52** — **Met**: 50 partial-g bounded rows plus 2 LUCI/FM2 reference rows, selected by family and gravity-descriptor rules.
4. **All 42 corrupt airflow values quarantined with raw retained** — **Met**: 42 rows flagged `AIRFLOW_QUARANTINED`, clean values nulled, originals retained in `airflow_velocity_cms_raw` (max `5,105,204,962,494,442.0` cm/s).
5. **Quality report lists every mapping and flag** — **Met**: the report lists each applied mapping with counts, identity values, every flag, every quarantined row, modeled rows, null rates per family, and input checksums.
6. **Tests, ruff, and mypy pass** — **Met**: 71 tests pass; ruff and mypy are clean.
7. **Pydantic schema, data dictionary, deterministic pipeline** — **Met**. The schema covers all 28 canonical columns; the data dictionary covers all 44 output columns and marks `UNVERIFIED` items; artifacts are deterministic.
8. **Commit locally and tag `phase-3-complete`** — **Met at phase close**. The code and documentation are committed as `c03126a` (`phase 3: ingestion, validation and data quality`); the regenerated artifacts and this report are committed immediately after, and `phase-3-complete` tags the final tree.

#### Issues found

- **External commit during the phase.** Commit `b89048e` (“Implement dataset validation and schema for experiment records”) was created by an external process and captured the earlier Phase 3 implementation. Per the agent rules, history was not reset or rewritten. The remaining fixes and this report were committed on top as `c03126a` and the final artifact commit.
- **Determinism and timestamps.** The pipeline writes `generated_at` into the manifest and report. Byte-identical artifacts therefore require a fixed `SOURCE_DATE_EPOCH`; the Parquet itself is deterministic without it.
- **Null representation.** Pandas may expose missing string values as `NaN` rather than `None` in memory; Parquet stores them as nulls. Tests use `pd.isna` rather than identity checks.
- **Flag persistence under copy-on-write.** An intermediate implementation stored flags in a Series view, which copy-on-write discarded. Flags now update the parent DataFrame directly; the integration test catches regressions.
- **Legacy fidelity.** The 442 legacy-carried rows cannot be rebuilt faithfully from their raw logs without inventing authored descriptions, constants, and notes. They are explicitly sourced from the legacy canonical CSV and flagged in the report and dictionary.
- **Known data defects retained, not fixed.** Seven zero burn times, one 10003.4 s burn time, one zero/mmHg pressure row with missing kPa, eight zero extinction diameters, zero burning rates in NASA-STD-6001/SLICE/SOFIE, and campaign-level constants in several families are preserved and documented. No imputation or silent repair was performed.
- **SLICE metadata drift.** The raw SLICE file lacks the longer `source_name` and facility-suffixed `notes` present in the legacy canonical CSV. The pipeline uses the raw values; the difference is counted in the 502-cell final diff.
- **Dependency additions.** `pyyaml` is required to read the versioned mapping tables. `pandas-stubs` and `types-PyYAML` are dev-only typing dependencies needed for strict mypy. No other dependency was added.

#### Deviations from the prompt

- `gravity_condition` was added to the explicit vocabulary mapping alongside the three named columns. The only applied rule is the case/label normalisation `microgravity` → `Microgravity (~0g)` (28 rows); the original value is preserved in `gravity_condition_raw` in memory.
- `original_test_id` and `pressure_mmhg` are derived for raw-rebuild rows. Both were verified to reproduce the legacy canonical values exactly for all 450 rows; the derivations are documented in the source policy and data dictionary.
- The 442 non-rebuildable rows use `data/processed/canonical_experiments.csv` as their declared source, as permitted by the Phase 3 prompt. The six unused legacy raw files are recorded in the source policy.
- No database, retrieval, or LLM code was added.

#### Remaining work

- Owner approval is required for the vocabulary mappings, the 1000 cm/s airflow quarantine threshold, the 3600 s burn-time plausibility maximum, and the `UNVERIFIED` items in `docs/data_dictionary.md`.
- Later phases must not treat `is_modeled` rows as direct partial-gravity measurements, must not compare `burning_rate_mms` across families without source definitions, and must not treat legacy-carried fields as raw-verified measurements.
- Database loading, retrieval indices, and LLM/RAG components remain out of scope until their phases.


### Phase 4 — Storage and structured retrieval

#### What was done

- Verified Phase 3 acceptance state: tag `phase-3-complete`, 71 passing tests, clean tree, and confirmed `data/processed/experiments.parquet` exists and validates against the schema.
- Built `src/flame/retrieval/store.py`: `ExperimentStore` providing a DuckDB-backed read-only view over `experiments.parquet`. Utilizes one persistent DuckDB connection with a fresh cursor per request to ensure thread safety and concurrency. Exposes structured dataset version information from `provenance_manifest.json` (`git_commit`, `generated_at`, `total_rows`, `raw_rebuild_rows`, `canonical_legacy_rows`, `flags`, and `source_policy`).
- Built `src/flame/schemas/query_plan.py`: Pydantic v2 `QueryPlan` contract between any future planner and the retrieval core.
  - Intents: `lookup`, `aggregate`, `compare`, `explain_experiment`, `qualitative`, `out_of_scope`.
  - Filter operators: `eq`, `in`, `gte`, `lte`, `between`, `contains`, `is_null`, `not_null`.
  - Strict whitelist validation generated from the `DatasetRecord` schema (all 44 canonical and enrichment columns).
  - Validation: raises typed `UnknownFieldError` for unwhitelisted field names, `UnknownOperatorError` for invalid operators/functions, and `PlanValidationError` for invalid plan structures.
  - Server-side limit enforcement: default limit 100, hard maximum limit 1000.
  - Sorting specification and modeled-row inclusion flag (defaulting to false).
- Built `src/flame/retrieval/compiler.py`: Parameterized SQL compiler that maps a `QueryPlan` to parameterized DuckDB SQL.
  - Ensures no user or LLM strings are ever formatted or interpolated into SQL text; all values use positional DB-API placeholders (`?`).
  - Implements parameterized case-insensitive `contains` via `ILIKE '%' || ? || '%'`.
  - Automatically excludes modeled rows (`is_modeled = FALSE`) by default unless `include_modeled` is True.
  - Enforces cross-family semantic differences: aggregating columns documented as semantically different across families (`burning_rate_mms`, `co2_pct`, `burn_time_s`, `initial_diameter_mm`, `extinction_diameter_mm`, `flame_temp_k`, `he_pct`) defaults grouping to `dataset_family` and attaches explicit warnings.
- Built `src/flame/retrieval/structured.py`: Deterministic query executor returning `RetrievalResult`.
  - Rows always include citation/traceability columns: `experiment_id`, `source_url`, `investigation_id`, `data_quality_flags`, and `is_modeled`.
  - Aggregates explicitly calculate `n_used`, `n_null_excluded`, and `n_quarantined_excluded` (correctly isolating the 42 quarantined airflow readings).
  - Empty results return an explicit empty `RetrievalResult` (never an exception).
- Built `src/flame/retrieval/catalog.py`: Field catalog extracting names, logical types, physical units, caveats, null counts, allowed values for categorical fields, and min/max for numeric fields.
- Implemented comprehensive test suites:
  - SQL injection defense tests verifying parameterization across arbitrary injection strings.
  - Concurrency test running 20 parallel queries with fresh cursors.
  - 16 independent numeric comparison tests matching exact store results against pandas computations.
  - The acceptance test for methanol droplets at 21% O2 returning the exact matching rows (30 rows) and mean burning rate (0.4965 mm/s for FLEX) as pandas.

#### Files changed

New files:
- `src/flame/retrieval/catalog.py`
- `src/flame/retrieval/compiler.py`
- `src/flame/retrieval/errors.py`
- `src/flame/retrieval/store.py`
- `src/flame/retrieval/structured.py`
- `src/flame/schemas/query_plan.py`
- `tests/unit/test_retrieval_plan.py`
- `tests/unit/test_retrieval_compiler.py`
- `tests/unit/test_retrieval_executor.py`
- `tests/unit/test_retrieval_catalog.py`
- `tests/unit/test_retrieval_store_unit.py`
- `tests/integration/test_retrieval_store.py`
- `tests/integration/test_retrieval_numeric_validation.py`

Modified files:
- `src/flame/retrieval/__init__.py`
- `docs/PROGRESS.md`

#### Tests run and results

- `uv run pytest` — **PASS**: 148 passed in 4.58s.
- `uv run ruff check .` — **PASS**: all checks passed.
- `uv run ruff format --check .` — **PASS**: 52 files already formatted.
- `uv run mypy` — **PASS**: Success, no issues found in 24 source files (strict mode).
- Line coverage on `src/flame/retrieval`:
  - `src/flame/retrieval/catalog.py`: 95%
  - `src/flame/retrieval/compiler.py`: 97%
  - `src/flame/retrieval/store.py`: 98%
  - `src/flame/retrieval/structured.py`: 93%
  - `src/flame/schemas/query_plan.py`: 96%
  - Total project coverage: 93%.

#### Acceptance criteria checked

1. **All tests pass with at least 90% line coverage on `src/flame/retrieval`** — **Met**: 148 tests pass; coverage on retrieval modules is 93% to 98% (overall 93%).
2. **A query for methanol droplets at 21% O2 returns the same rows and mean burning rate as an independent computation** — **Met**: verified in `tests/integration/test_retrieval_store.py::test_methanol_droplets_at_21_pct_o2_acceptance_criterion` matching pandas results.
3. **Modeled rows never appear in default results** — **Met**: verified in `tests/unit/test_retrieval_executor.py::test_modeled_rows_never_appear_in_default_results` (all 840 default rows have `is_modeled=False`).
4. **Compiler tests proving injection strings cannot alter SQL structure** — **Met**: verified in `tests/unit/test_retrieval_compiler.py`.
5. **Numeric tests comparing store results with independent pandas computation for >= 15 queries** — **Met**: 16 numeric validation queries in `tests/integration/test_retrieval_numeric_validation.py`.
6. **Tests for null exclusion counts, modeled-row exclusion/inclusion, empty results, limit enforcement, unknown-field rejection** — **Met**: verified across unit tests.
7. **Concurrency test running parallel queries** — **Met**: verified in `test_store_concurrency_parallel_queries` running 20 parallel queries across 5 worker threads.

#### Issues found

- **DuckDB DDL Prepared Statement Restriction:** DuckDB does not permit prepared parameters (`?`) inside `CREATE VIEW ... AS SELECT * FROM read_parquet(?)`. Resolved by formatting the verified POSIX path into the DDL string while keeping all DML queries strictly parameterized.
- **Pydantic v2 Exception Wrapping:** Pydantic v2 wraps custom exceptions raised in field validators inside `ValidationError`. Resolved via `BasePlanModel` which unwraps and raises the exact typed domain exception (`UnknownFieldError`, `UnknownOperatorError`, `PlanValidationError`).
- **Provenance Manifest JSON Schema:** Manifest records counts under `row_counts` rather than `counts`, and output checksum under `outputs.parquet_sha256`. Store loader was aligned with this structure.

#### Deviations from the prompt

- None. All requested components, contracts, constraints, and test suites were implemented exactly as specified. No dependencies were added, and no LLM, vector DB, or external API code was introduced.

#### Remaining work

- Phase 6: LLM-based query planner (natural language to validated QueryPlan) and plan accuracy scoring against golden questions.


### Phase 5 — Golden evaluation set and deterministic harness

#### What was done

- Verified Phase 4 base: branch `Moaz`, clean tree, tag `phase-4-complete`, and full test suite passing (148 tests).
- Created `evaluation/golden_questions.yaml` inside the repository with exactly 50 curated questions across five balanced categories:
  - 15 filtered lookups (`q01`–`q15`): tests real experiments, single/multi-column filters (`fuel_material`, `dataset_family`, `extinction_outcome`, date ranges, null flags, quarantined airflow, modeled row exclusion/inclusion).
  - 15 aggregations and comparisons (`q16`–`q30`): mean, min, max, median, count; grouped aggregations; single-family isolating filters to respect cross-family semantic differences; verified exclusion of nulls and quarantined readings.
  - 8 single-experiment explanations (`q31`–`q38`): tests retrieval of exact experiment records and metadata across diverse families (`BASS-II`, `FLEX`, `GRC Drop Tower`, `MGM`, `SOFIE`, `FLARE`, `FM2-BOUND-002`).
  - 6 qualitative or conceptual questions (`q39`–`q44`): models domain rules (why modeled rows are excluded, airflow quarantine rationale, burning rate cross-family semantics, campaign date range nulling, helium percentage provenance, null/quarantine accounting).
  - 6 out-of-scope or unanswerable questions (`q45`–`q50`): partial-gravity extrapolation to Mars, raw unquarantined corrupt airflow, cross-family unverified grand mean, unrecorded discrete dates, missing pressure in kPa, hypothetical unmeasured fuels. All 6 are flagged `needs_expert: true`.
- Created `evaluation/build_expected.py`:
  - Pure pandas computation reading `data/processed/experiments.parquet` directly.
  - Does NOT import or execute any code from `src/flame/retrieval`.
  - Computes exact matching experiment IDs and numeric aggregates (mean, median, min, max, count) along with precise `n_used`, `n_null_excluded`, and `n_quarantined_excluded` counts.
  - Writes `evaluation/expected_answers.yaml` and updates `evaluation/golden_questions.yaml`.
- Created `evaluation/run_eval.py`:
  - Deterministic evaluation harness executing plans via `ExperimentStore`.
  - Scores exact list equality on experiment IDs for lookups and explanations.
  - Scores numeric aggregates within $10^{-4}$ relative tolerance and verifies `n_used` accounting.
  - Generates timestamped JSON logs and formatted markdown summaries under `evaluation/results/` (`latest.json` and `latest.md`).
  - Exposes pluggable `QuestionToPlanCallable` interface (`default_plan_from_question`) ready for Phase 6 planner integration.
- Created `tests/integration/test_golden_harness.py`:
  - `test_golden_harness_deterministic_100_pct`: verifies 100% pass rate across all 38 deterministic questions.
  - `test_golden_harness_expert_items_listed`: verifies all 6 `needs_expert` items (`q45`–`q50`) are identified and separated from automated execution.
  - `test_golden_harness_writes_results_artifacts`: verifies JSON and Markdown report artifact generation.
- Updated `pyproject.toml` with `pythonpath = ["."]` so `evaluation` is cleanly importable.

#### Files changed

New files:
- `evaluation/__init__.py`
- `evaluation/golden_questions.yaml`
- `evaluation/build_expected.py`
- `evaluation/expected_answers.yaml`
- `evaluation/run_eval.py`
- `tests/integration/test_golden_harness.py`

Modified files:
- `pyproject.toml` (added `pythonpath = ["."]`)
- `docs/PROGRESS.md` (this report)

#### Tests run and results

- `uv run python evaluation/build_expected.py` — **PASS**: computed independent expected answers for all 50 questions.
- `uv run python evaluation/run_eval.py` — **PASS**:
  - Total questions: 50
  - Deterministic evaluated: 38
  - Passed: 38 / 38 (**100.0% pass rate**)
  - Lookups: 15 / 15 passed (100%)
  - Aggregations: 15 / 15 passed (100%)
  - Explanations: 8 / 8 passed (100%)
  - Qualitative: 6 skipped (scored qualitatively in later phases)
  - Out of scope: 6 flagged `needs_expert`
- `uv run pytest` — **PASS**: 151 passed in 39.28s, 93% total line coverage (`src/flame/retrieval` at 93%–98%).
- `uv run ruff check .` — **PASS**: all checks clean.
- `uv run ruff format --check .` — **PASS**: 65 files formatted.
- `uv run mypy` — **PASS**: Success: no issues found in 24 source files (strict mode).

#### Acceptance criteria checked

1. **Harness runs from one command and reports per-category scores** — **Met**: `uv run python evaluation/run_eval.py` runs end-to-end and reports exact pass rates per category.
2. **All deterministic items pass (100%)** — **Met**: 38/38 deterministic items pass with exact ID matching and numeric tolerance.
3. **Items marked needs_expert are listed** — **Met**: all 6 expert items (`q45`–`q50`) are listed in console output, `latest.md`, and validated by tests.
4. **Independent expected values derived via pandas** — **Met**: `evaluation/build_expected.py` computes answers purely using pandas with zero retrieval imports.
5. **Tests, ruff, mypy pass** — **Met**: full green test suite (151 tests), ruff lint/format clean, strict mypy clean.
6. **Local commit and tag `phase-5-complete`** — **Met at phase close**.

#### Issues found

- `duckdb` does not support `ILIKE` on `VARCHAR[]` (array) columns (`data_quality_flags`). To ensure full deterministic compilation and execution, `q06` was refined to query the clean null state `airflow_velocity_cms IS NULL` combined with `airflow_velocity_cms_raw >= 1000.0`, matching the documented quarantine rule.
- Pandas `.groupby(..., dropna=False)` yields group names as tuples even for 1-column groupings. Fixed unpacking in `build_expected.py` to match the scalar dictionary representation in `RetrievalResult.aggregates`.

#### Deviations from the prompt

- None. No dependencies added, no LLM calls made, and all 50 questions use genuine data from `data/processed/experiments.parquet`.

#### Remaining work

- Phase 6: LLM-based query planner mapping natural language to typed `QueryPlan` instances and benchmarking against `evaluation/golden_questions.yaml`.
