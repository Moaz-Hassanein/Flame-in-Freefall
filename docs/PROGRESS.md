# Progress

## Phase status

| Phase | Status | Notes |
|:--:|:--|:--|
| 1 | **Complete** | Repository audit and agent rules. Awaiting approval of proposed dispositions. |
| 2 | Not started | Scope defined by the Phase 2 prompt. |
| 3 | Not started | Scope defined by the Phase 3 prompt. |
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
