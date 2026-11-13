# Repository Audit — Phase 1

- Date: 2026-11-13
- Branch: `Moaz` (tracking `origin/Moaz`, clean tree at audit start)
- Latest commit: `9fa9cf8`
- Scope: read-only audit of the existing repository plus creation of `docs/AGENT_RULES.md`, `docs/PROGRESS.md`, and this report. No code, data, dependency, or structure changes were made.
- Method: direct file reads; `git status` / `git branch` / `git log --all`; deterministic Python profiling scripts executed from `/tmp/opencode` and deliberately not committed; CSV inspection with the standard library and `pandas` 3.0.3.

---

## 1. Repository state and environment (Task 5)

### 1.1 Git state

```
$ git status
On branch Moaz
Your branch is up to date with 'origin/Moaz'.
nothing to commit, working tree clean

$ git branch
* Moaz
  remotes/origin/Moaz
```

- The tree is clean and the branch is `Moaz`. No branch switch was performed.
- There are no tags in the repository.
- All raw data and the canonical CSV were added in a single commit, `45a2d1e` ("Add new experimental datasets for SAFFIRE, SLICE, and SOFIE projects", 18 files, 1800 insertions). No generator or pipeline script was included.

### 1.2 Runtime environment (report only; nothing installed)

| Item | Finding | Status |
|:--|:--|:--|
| OS | Ubuntu 26.04 LTS (Resolute Raccoon), kernel `7.0.0-43-generic`, x86_64 | Reported |
| Python | 3.14.4 (`/usr/bin/python3`) | Reported |
| `uv` | 0.11.28 at `/home/nour/.local/bin/uv` | Installed |
| Node.js | v22.22.3 at `~/.nvm/versions/node/v22.22.3/bin/node` | Installed, ≥ 20 |
| npm | 10.9.8 | Installed |
| pandas | 3.0.3 importable from the system interpreter | Present but **not declared** in `requirements.txt` |
| Project venv / lockfile | None (`.venv` absent, no lockfile, no `pyproject.toml`) | Missing |
| Test/lint tooling | No `pytest`, `mypy`, or `ruff` configuration | Missing |

---

## 2. Repository tree

```
.
├── .env.example
├── .gitignore
├── LICENSE                      (Apache-2.0)
├── README.md
├── main.py                      (0 bytes)
├── exp.py
├── inventory_psi159.py
├── requirements.txt
├── assets/
│   └── README.md                (dataset catalog)
├── data/
│   ├── processed/
│   │   └── canonical_experiments.csv
│   └── raw/                     (17 CSVs)
├── docs/
│   ├── AGENT_RULES.md           (created this phase)
│   ├── PROGRESS.md              (created this phase)
│   └── audit/
│       └── repo_audit.md        (this file)
└── src/
    ├── analytics/
    │   ├── advanced_analytics.py
    │   ├── analytics.py
    │   └── query_engine.py
    └── data/
        └── load_data.py
```

There is no backend package, no `src/flame`, no frontend, no tests, no `pyproject.toml`, no package `__init__.py` files, no Parquet snapshot, no DuckDB, no LLM client, and no Qdrant integration. `src` works only as an implicit namespace package.

---

## 3. Non-data file analysis (Task 1)

### 3.1 Summary table

| File | Purpose | Inputs → Outputs | Dependencies | Quality | RAG disposition | One-line justification |
|:--|:--|:--|:--|:--|:--|:--|
| `main.py` | Intended application entry point | none → none | none | Empty file (0 bytes) | **Replace** | Cannot be reused; the FastAPI app must be created here or in a real package entry point. |
| `exp.py` | Scratch probing of the NASA PSI download API | HTTP → stdout | `requests`; `pandas`/`os`/`json` only in commented code | Scratch: mostly commented-out code, unguarded network call at import, hardcoded filenames | **Remove** | Exploratory PSI-159 download snippet with no role in retrieval or answering. |
| `inventory_psi159.py` | Builds a PSI-159 file inventory from the NASA PSI API | HTTP JSON → three CSVs written to CWD | `requests`, `pandas` | Scratch utility: no typing, no tests, network-dependent, hardcoded `PSI-159` | **Remove** | One-off metadata inventory for a study absent from the curated dataset; not part of the product. |
| `requirements.txt` | Python dependency pins | n/a → n/a | `fastapi`, `uvicorn[standard]`, `python-multipart` | Incomplete: missing `pandas`, `duckdb`, `pyarrow`, Pydantic config, LLM/Qdrant clients, dev tools | **Replace** | The dependency set does not match the decided FastAPI + DuckDB + Parquet (+ optional Qdrant) architecture. |
| `.env.example` | Environment template | n/a → n/a | none | Minimal: `APP_NAME`, `APP_VERSION` only; uses spaces around `=`; no secrets or config keys | **Refactor** | Keep the file but expand it as phases introduce configuration; values must be loaded by a config module. |
| `README.md` | Project blurb | n/a → n/a | none | Three lines, challenge description only; no setup, architecture, or run instructions | **Replace** | Needs a real project README once phases define the system. |
| `src/data/load_data.py` | Loads the canonical CSV | `data/processed/canonical_experiments.csv` → `pandas.DataFrame` | `pandas` | Minimal: no schema validation, no typing, no Parquet, no provenance checks | **Refactor** | Keep the project-root/path convention, but replace CSV loading with a typed, validated Parquet snapshot loader. |
| `src/analytics/analytics.py` | Prints aggregate dataset statistics | CSV → stdout | `pandas`, `load_data` | Print-only CLI, no return values, no typing, hardcoded columns | **Remove** | The product needs machine-readable, deterministic queries, not a print report; statistical definitions may inform evaluation only. |
| `src/analytics/advanced_analytics.py` | Prints oxygen/gravity/fuel crosstabs | CSV → stdout | `pandas`, `load_data` | Print-only CLI, duplicate logic, no typing | **Remove** | Superseded by the query-plan → DuckDB path; no reusable contract. |
| `src/analytics/query_engine.py` | Interactive keyword-based query router | CSV + stdin → stdout | `pandas`, `load_data` | 401 lines of `if/elif` keyword matching, prints results, no typing, no tests | **Remove** | A hardcoded keyword router is exactly what the typed LLM query plan replaces; only its question vocabulary is useful as reference. |
| `assets/README.md` | Curated dataset catalog with facilities and scope notes | n/a → n/a | none | Useful domain metadata but contains factual errors: references nonexistent `scripts/pipeline.py`, says 29 investigations while the canonical file has 35 | **Refactor** | Salvage the catalog into accurate documentation; remove false provenance and reconcile counts. |
| `LICENSE` | Apache-2.0 license | n/a → n/a | none | Standard, no issues | **Keep** | Legally required and unrelated to the RAG implementation. |
| `.gitignore` | Git exclusions | n/a → n/a | none | Standard Python template; covers `.env` and caches; lacks `node_modules/`, frontend build output, and generated Parquet snapshots | **Refactor (minimal)** | Add only the ignore rules later phases need; do not rewrite it wholesale. |

### 3.2 File-by-file notes

**`main.py`** — 0 bytes. It is tracked but empty. There is no importable application, so `uvicorn main:app` cannot work today. Disposition: replace with the FastAPI application (or a thin entry point importing `src/flame`).

**`exp.py`** — 151 lines. Lines 1–121 are commented-out PSI-159 inventory code. Lines 123–151 execute at import time: an unguarded `requests.get` against `https://psi.nasa.gov/geode-py/ws/studies/PSI-159/download` for two hardcoded filenames, printing the first 4000 characters. There is no `main()` guard, no error policy beyond `raise_for_status()`, and no typing. It is scratch code from dataset exploration. Disposition: remove.

**`inventory_psi159.py`** — 163 lines. Fetches `PSI-159` metadata, classifies files by extension, and writes `psi159_full_inventory.csv`, `psi159_relevant_files.csv`, and `psi159_archives.csv` into the current working directory. It is a reasonable one-off exploration script but has no typing, tests, retry logic, or CLI arguments, and PSI-159 is not one of the 17 curated datasets. Disposition: remove (its classification idea is trivial to re-implement if ever needed).

**`requirements.txt`** — three pinned packages only. `pandas` is imported by existing code but undeclared. The decided backend also needs `duckdb`, `pyarrow`, Pydantic v2, an LLM client, and dev tooling (`pytest`, `mypy`, `ruff`), plus an optional Qdrant client if semantic retrieval survives evaluation. Disposition: replace, with dependencies added only when the owning phase names them.

**`.env.example`** — contains `APP_NAME = "Flame-in-Freefall"` and `APP_VERSION = "0.1.0"`. The spaces around `=` are tolerated by some dotenv parsers but are unnecessary. There is no config module yet. Disposition: refactor/expand in the configuration phase; no secrets are present.

**`README.md`** — three lines describing the NASA Space Apps challenge. No install, architecture, data caveats, or run instructions. Disposition: replace.

**`src/data/load_data.py`** — 33 lines. Resolves the project root with `Path(__file__).resolve().parents[2]`, builds the canonical CSV path, raises `FileNotFoundError` if missing, and returns `pandas.read_csv` output. There is no schema validation, dtype coercion, null policy, or provenance check. Disposition: refactor; the root/path convention is reusable, the loader contract is not.

**`src/analytics/analytics.py`** — prints counts of experiments, fuels, investigations, gravity conditions, extinction outcomes, and grouped means. It is a console report, not a query API. Disposition: remove; keep the metric definitions as evaluation reference.

**`src/analytics/advanced_analytics.py`** — prints oxygen-band vs outcome percentages, burning rate by gravity, and fuel vs outcome crosstabs. Same limitations. Disposition: remove.

**`src/analytics/query_engine.py`** — an interactive CLI with 13 functions and a keyword router. It parses natural-language-ish strings with substring matching (`"search fuel"`, `"compare fuels X vs Y"`, etc.) and prints pandas output. This is the component the typed LLM query plan and DuckDB compiler are meant to replace. Disposition: remove, but retain the list of supported question shapes as a seed for query-plan intent categories.

**`assets/README.md`** — the most useful document in the repository for domain context: it catalogs facilities, campaigns, test counts, and the official partial-gravity scope note. However, it contains two verifiable errors: it says the raw tables are unified by `scripts/pipeline.py`, which has never existed in the working tree or in any git commit, and it says the canonical dataset spans 29 investigations, while the CSV actually contains 35 distinct `investigation_id` values. Disposition: refactor into accurate documentation; preserve the catalog and scope note, remove the false provenance claim, reconcile counts.

**`LICENSE`** — Apache License 2.0. Keep.

**`.gitignore`** — standard GitHub Python template. It ignores `.env`, `.venv`, `__pycache__`, `.mypy_cache`, `.ruff_cache`, and `dist/`, but it has no `node_modules/` or frontend build entries and does not treat generated Parquet/DuckDB artifacts specially. Disposition: minimal additions later.

**`src` packaging** — there are no `__init__.py` files. Imports such as `from src.data.load_data import load_experiments` work under the implicit namespace-package rules, but a typed application should introduce an explicit package. This is a Phase 2 structural decision, not a Phase 1 change.

---

## 4. Raw dataset inventory (Task 2)

### 4.1 Summary

| # | File | Rows | Cols | Schema | Encoding |
|--:|:--|--:|--:|:--|:--|
| 1 | `ACME_CIR_Extinction_Data.csv` | 8 | 13 | C (ACME legacy) | UTF-8 |
| 2 | `ACME_Extended_Research_Data.csv` | 60 | 23 | A (canonical-like) | UTF-8 |
| 3 | `BASS1_Initial_ISS_Data.csv` | 8 | 23 | A | UTF-8 |
| 4 | `FLEX2_Cool_Flame_Droplet_Data.csv` | 10 | 13 | D (FLEX-2 legacy) | UTF-8 |
| 5 | `JAXA_FLARE_Kibo_Flight_Data.csv` | 80 | 23 | A | UTF-8 |
| 6 | `NASA_GRC_Drop_Tower_Quenching.csv` | 95 | 23 | A | UTF-8 |
| 7 | `NASA_MGM_Smoldering_Combustion.csv` | 65 | 23 | A | UTF-8 |
| 8 | `NASA_PSI_Complete_Suite_CFIG_SPICE_DAFT.csv` | 13 | 24 | B (A + `sample_description`) | UTF-8 |
| 9 | `NASA_SAME_Aerosol_Detector_Data.csv` | 50 | 23 | A | UTF-8 |
| 10 | `NASA_STD_6001_Extended_Materials.csv` | 45 | 23 | A | UTF-8 |
| 11 | `NASA_STD_6001_Materials.csv` | 14 | 23 | A | UTF-8 |
| 12 | `PSI-25_Experimental table_BASS-II.csv` | 129 | 17 | E (BASS-II PI table) | UTF-8 with BOM |
| 13 | `PSI-69_Experimental table_FLEX.csv` | 274 | 15 | F (FLEX PI table) | **cp1252** (byte `0x96`, en dash) |
| 14 | `PSI-98_Experimental table_SAFFIRE-1.csv` | 4 | 13 | G (SAFFIRE-I PI table) | UTF-8 |
| 15 | `SAFFIRE_II_to_VI_Flight_Data.csv` | 15 | 17 | H (SAFFIRE II–VI) | UTF-8 |
| 16 | `SLICE_Extinguishment_Data.csv` | 8 | 23 | A | UTF-8 |
| 17 | `SOFIE_Flight_Data.csv` | 12 | 23 | A | UTF-8 |

Total raw rows: **890**. Ten of the 17 files already use the canonical 23-column schema (Schema A), one adds `sample_description` (Schema B), and six use older PI-specific layouts. `PSI-69` cannot be read as UTF-8 without a fallback; the other files can.

### 4.2 Schemas and apparent units

**Schema A — 23 columns** (used by files 2, 3, 5, 6, 7, 9, 10, 11, 16, 17):

| Column | Apparent unit / meaning |
|:--|:--|
| `experiment_id` | text identifier |
| `investigation_id` | text identifier |
| `dataset_family` | text label |
| `fuel_material` | text |
| `material_category` | text |
| `oxygen_pct` | % by volume |
| `pressure_kpa` | kPa |
| `burn_time_s` | s |
| `extinction_outcome` | text label |
| `extinction_diameter_mm` | mm |
| `initial_diameter_mm` | mm |
| `burning_rate_mms` | mm/s |
| `airflow_velocity_cms` | cm/s |
| `flame_temp_k` | K |
| `gravity_condition` | text label |
| `ignition_power_w` | W |
| `ignition_time_s` | s |
| `co2_pct` | % by volume |
| `co_ppm` | ppm |
| `test_date` | date string |
| `source_name` | text |
| `source_url` | URL |
| `notes` | free text |

**Schema B — 24 columns** (file 8): Schema A plus `sample_description` (text) inserted after `material_category`.

**Schema C — ACME CIR legacy, 13 columns** (file 1):
`Test_ID`, `Project_Name`, `Fuel`, `Burner_Type`, `Suppressant_Type`, `Suppressant_Pct` (%), `Airflow_cms` (cm/s), `Oxygen_Pct` (%), `Pressure_mmHg` (mmHg), `Burn_Time_s` (s), `Extinction_Type`, `Notes`, `Source_URL`.

**Schema D — FLEX-2 legacy, 13 columns** (file 4):
`Test_ID`, `Investigation`, `Fuel_Name`, `Initial_Diameter_mm` (mm), `Visible_Extinction_Diam_mm` (mm), `Cool_Flame_Extinction_Diam_mm` (mm), `Ambient_Pressure_mmHg` (mmHg), `Oxygen_Percent` (%), `Hot_Flame_Burn_Time_s` (s), `Cool_Flame_Burn_Time_s` (s), `Total_Burn_Time_s` (s), `Observed_Extinction_Phenomenon`, `Source_URL`.

**Schema E — BASS-II PI table, 17 columns** (file 12):
`PI`, `Test #`, `Date`, `GMT`, `Sample #`, `Fuel Sample Material`, `Flow restrictor` (unitless setting), `Fan display` (raw text; mixed numeric tokens and notes), `Air display` (raw text; mixed numeric tokens and notes), `Radiometer gain (1000 250 50 10)` (instrument gain setting), `Total Frames Shot` (frames; mixed numeric/text), `Calibrated initial O2 % by vol` (%), `Calibrated final O2 % by vol` (%), `Initial CO2 % by vol` (%), `Final CO2 % by vol` (%), `Initial CO (ppm)`, `Final CO (ppm)`.
There is **no airflow-velocity column** in this file; the canonical `airflow_velocity_cms` therefore cannot be a direct mapping.

**Schema F — FLEX PI table, 15 columns** (file 13):
`FLEX Test #`, `FLEX Identifier`, `Test Date`, `Test GMT`, `Fuel`, `Ambient pressure; mmHg` (mmHg), `O initial ambient composition; mole fraction` (mole fraction), `N ...` (mole fraction), `CO ...` (mole fraction), `He ...` (mole fraction), `Droplet initial diameter; mm` (mm), `Visible flame extinction diameter; mm` (mm), `Burning rate; mm` (label says mm; observed values 0.05–1.06 are physically **mm/s**), `Burn time; s` (s), `Test end` (text outcome).

**Schema G — SAFFIRE-I PI table, 13 columns** (file 14):
`Sample Number`, `Material`, `Sample Thickness (cm)` (cm), `Sample Length (cm)` (cm), `Sample Width (cm)` (cm), `Air Flow (cm/s)` (cm/s), `Percent O2` (%; entries are range strings such as `21.5 - 21.7` and `~ 21.5`), `Ignition Power (W)` (W), `Ignition Time (s)` (s), `Burn Time (s)` (s), `Flow Direction` (text), `Camera 1`, `Camera 2` (camera IDs).

**Schema H — SAFFIRE II–VI, 17 columns** (file 15):
`Mission`, `Sample_Number`, `Material`, `Sample_Thickness_cm` (cm), `Sample_Length_cm` (cm), `Sample_Width_cm` (cm), `Air_Flow_cms` (cm/s), `Percent_O2` (%), `Pressure_psia` (psia), `Pressure_mmHg` (mmHg), `Ignition_Power_W` (W), `Ignition_Time_s` (s), `Burn_Time_s` (s), `Flow_Direction` (text), `Extinction_Outcome` (text), `Notes`, `Source_URL`.
There is **no burning-rate column** in Schemas G and H.

### 4.3 Schema observations

- The ten Schema A files are not raw instrument exports in any ordinary sense: they already carry `experiment_id`, `dataset_family`, normalized SI units, and canonical outcome labels. Their own provenance is therefore second-hand. Only files 1, 4, 12, 13, 14, and 15 (plus the mixed file 8) look like PI-level tables.
- `PSI-25` stores airflow as free text in `Fan display` / `Air display` (e.g. `1.7 (52) 1.25 0.9 0.6 0.4 0.35`, `10 max`, `approaching 10`), with values sometimes written as sequences. This is the root of the canonical airflow corruption described below.
- `PSI-69` uses a non-UTF-8 en dash, so any reader must handle `cp1252` or decode with replacement. Its `Burning rate; mm` column name is wrong by a factor of time.
- `PSI-98` encodes oxygen as text ranges, and has no burning-rate or pressure columns.
- `SAFFIRE_II_to_VI` has no per-test date and no burning rate; dates in the canonical file (`2017-2024`) are campaign windows, not test dates.

---

## 5. Canonical dataset validation (Task 4)

File: `data/processed/canonical_experiments.csv`, **892 rows × 28 columns**, 437,422 bytes.

Columns: `experiment_id`, `dataset_family`, `investigation_id`, `original_test_id`, `fuel_material`, `material_category`, `sample_description`, `oxygen_pct`, `pressure_mmhg`, `pressure_kpa`, `burn_time_s`, `extinction_outcome`, `extinction_diameter_mm`, `initial_diameter_mm`, `burning_rate_mms`, `airflow_velocity_cms`, `flame_temp_k`, `gravity_condition`, `ignition_power_w`, `ignition_time_s`, `co2_pct`, `he_pct`, `co_ppm`, `test_date`, `source_name`, `source_url`, `notes`, `facility_hardware`.

Cardinality: 892 unique `experiment_id`, 892 unique `original_test_id`, 30 dataset families, 35 investigations, 7 gravity-condition labels. No duplicate `experiment_id`; no duplicate rows when IDs are excluded.

### 5.1 Claimed issues — confirmed or contradicted

| # | Claim | Verdict | Evidence |
|--:|:--|:--|:--|
| 1 | 892 rows, 28 columns | **Confirmed** | Shape is exactly `(892, 28)`; IDs unique. |
| 2 | 52 modeled partial-gravity rows, identifiable by `gravity_condition` prefix or `dataset_family` membership | **Confirmed exactly** | `gravity_condition.str.startswith("Partial-g Bounded")` = 52; `dataset_family in {"Partial-g Bounded (0g+1g / E-FIELD)", "LUCI / FM2 (Future Partial-g)"}` = 52; intersection = 52; symmetric difference = 0. Breakdown: 30 lunar bounded, 20 Martian bounded, 1 pre-LUCI, 1 pre-FM2. The same 52 rows are already modeled inside the raw files (`JAXA_FLARE` 50; `NASA_PSI_Complete_Suite` 2), not only in the canonical output. |
| 3 | `airflow_velocity_cms` has 42 values above 1000 with max near 5e15 | **Confirmed** | Exactly 42 values > 1000 (61 > 100); max = `5,105,204,962,494,442.0` (5.105×10^15 cm/s ≈ 1.7×10^14 m/s). All 42 belong to `BASS-II`. Nine BASS-II rows are null. The values are non-physical and correlate with free-text `Fan display` / `Air display` strings; e.g. `BASS-M15` carries `1.087810e14` and notes `Fan display: 102015.0`, evidently digit-concatenated from `10`, `20`, `15`. Most extreme rows have `Fan display: None.`. |
| 4 | Mixed date formats | **Confirmed** | `YYYY-MM-DD`: 466; `M/D/YYYY`: 353; `M/D/YY`: 50; non-date campaign ranges: 23 (`2017-2024` ×15, `2019-2022` ×8). 23 strings are unparseable by pandas. Parsed range: 2009-03-05 to 2025-02-10. |
| 5 | Fragmented vocabularies | **Confirmed** | `extinction_outcome`: 71 distinct; `material_category`: 62; `fuel_material`: 119. Examples: `Self-Extinguished`, `Self-extinguished`, `Self-Extinction`, `Self-extinguished Immediately`; `Extinction` vs `Radiative Extinction` vs `Radiative Quenching` vs `Soot-Induced Radiative Extinction`; `PMMA (Acrylic)` vs `PMMA (Polymethyl Methacrylate)` vs `Clear PMMA Rod (6.35mm)`; typo `1/4 blac rod`. |
| 6 | Structured null patterns per family | **Confirmed** | See the table in §5.2. Examples: `FLEX` has 100% null `ignition_power_w`, `ignition_time_s`, `co_ppm`; `BASS-II` has 100% null `ignition_*` and 100% null `extinction_diameter_mm`; `FLEX-2` has 100% null `co2_pct`, `co_ppm`, `ignition_*`; `NASA-STD-6001`, `MGM`, `SAME (Aerosol)`, `SAFFIRE-*` have 100% null `extinction_diameter_mm`. |

### 5.2 Null fractions per family (selected columns)

Fraction of rows that are null; `0.00` means fully populated.

| Family | n | O2 | pressure_kPa | burn_time | ext. diam | init. diam | burn rate | airflow | flame temp | ignition power | CO2 | CO |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| FLEX | 274 | 0.00 | 0.00 | 0.02 | 0.28 | 0.04 | 0.06 | 0.00 | 0.00 | **1.00** | 0.00 | **1.00** |
| BASS-II | 129 | 0.00 | 0.00 | 0.00 | **1.00** | **1.00** | **1.00** | 0.07 | 0.00 | **1.00** | 0.05 | 0.06 |
| GRC Drop Tower | 95 | 0.00 | 0.00 | 0.00 | 0.37 | 0.37 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| MGM | 65 | 0.00 | 0.00 | 0.00 | **1.00** | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| NASA-STD-6001 | 59 | 0.00 | 0.00 | 0.00 | **1.00** | 0.00 | 0.00 | 0.00 | 0.10 | 0.00 | 0.00 | 0.00 |
| SAME (Aerosol) | 50 | 0.00 | 0.00 | 0.00 | **1.00** | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| FLARE (JAXA/Kibo) | 30 | 0.00 | 0.00 | 0.00 | 0.53 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| FLEX-2 | 10 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | **1.00** | **1.00** | **1.00** |
| SLICE | 8 | 0.00 | 0.00 | 0.00 | **1.00** | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| SAFFIRE-I | 4 | **0.50** | 0.00 | **0.50** | **1.00** | **1.00** | **0.50** | **0.50** | 0.00 | **0.50** | **1.00** | **1.00** |
| ACME (CIR) | 8 | 0.00 | 0.00 | 0.00 | **1.00** | **1.00** | **1.00** | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

### 5.3 Additional findings

1. **The canonical row count is not derivable from the raw row count.** Raw files total 890 rows. The canonical file has 892: all 890 raw rows map 1:1 to canonical rows, plus two rows (`NTRS-2012-01`, `NTRS-2024-02`) that exist in no raw file. Their `source_url` values are NTRS citations, but no raw CSV or extraction artifact supports their numeric values.
2. **Template/constant infill is widespread.** Several numeric columns take only one or two values per campaign, which is not credible for measured telemetry:
   - `BASS-II` (129 rows): `flame_temp_k` only `{950, 1380}`; `pressure_kpa` only `101.32`; no ignition data.
   - `FLEX` (274 rows): `flame_temp_k` only `{1250, 1400}`; `airflow_velocity_cms` only `0.0`.
   - `FLEX-2` (10 rows): `burning_rate_mms` is `0.45` for every row; `flame_temp_k` only `{720, 1450}`.
   - `SAFFIRE-II`/`III`: `flame_temp_k=1410`, `co2_pct=0.35`, `co_ppm=45`, airflow `20` for all rows; `SAFFIRE-IV`–`VI`: `1520`, `0.85`, `45`.
   - `ACME (CIR)`: `ignition_power_w=50`, `ignition_time_s=2.0`, `co2_pct=0.5`, `co_ppm=12` for all 8 rows.
   These look like campaign-level placeholder constants, not measurements. They must not be presented as measured values without a provenance label.
3. **Burning rates exist where the source has no burning-rate column.** `SAFFIRE-I` has 2 non-null burning rates (`0.97`, `5.80`) and `SAFFIRE-II`–`VI` have 15 non-null burning rates, yet Schemas G and H contain no burning-rate field. `FLEX-2` has 10 non-null burning rates although Schema D has only diameters and burn times. These values have no traceable formula in the repository.
4. **Implicit imputation in SAFFIRE-I oxygen.** Raw `Percent O2` is the text range `21.5 - 21.7`; canonical `SAF1-S1` stores `21.6`, a midpoint that is not stated in the source. `SAF1-S2` maps `~ 21.5` to `21.5`.
5. **`co2_pct` mixes two different physical quantities.** For FLEX, values up to 70% are ambient CO2 diluent from the raw mole-fraction columns (`CO initial ambient composition; mole fraction`). For other families, `co2_pct` is a combustion/product measurement. Aggregating or comparing this column across families is scientifically invalid. `he_pct` is similarly ambient composition, and is zero-filled rather than null where not applicable.
6. **`pressure_mmhg` and `pressure_kpa` are redundant.** The ratio is 7.50062 for all 891 rows with both values. `FLEX-114` has `pressure_mmhg = 0.0` and `pressure_kpa = NaN`, an inconsistent placeholder. No phase should treat both as independent measurements.
7. **Two rows are not experiments.** `SAF1-F1C1/F1C2` and `SAF1-F2C1/F2C2` are labeled `Pre-test flow visulation data for sample 1/2` (typo included). They have no oxygen, burn time, diameter, or airflow, yet carry an extinction outcome and a `test_date`.
8. **Zero burning rate conflates “no propagation” with “not measured”.** Twelve rows have `burning_rate_mms = 0.0` (`SOFIE-006`, six `NASA-STD-6001` rows, five `SLICE` rows), while other measurement columns are missing. Zero should not be treated as a measurement without a separate status flag.
9. **Dates are partly placeholders.** 23 rows use campaign windows (`2017-2024`, `2019-2022`) instead of test dates. `SAFFIRE` and `ACME (CIR)` therefore cannot support date-based filtering at test resolution.
10. **Documentation contradicts the data.** `assets/README.md` claims 29 investigations; the canonical file has 35. It also names `scripts/pipeline.py`, which has never existed in git history.
11. **Ten raw files are already canonicalized.** Their presence in `data/raw` means the repository cannot distinguish original observations from a previous normalization pass. This weakens the meaning of “raw”.
12. **`FLEX-2` loses a measured field.** The raw table has both visible-flame and cool-flame extinction diameters; canonical keeps only one `extinction_diameter_mm` (the cool-flame value), with no column distinguishing the two phenomena.
13. **`PSI-69` is the only file that is not UTF-8.** It requires `cp1252`; naive UTF-8 ingestion fails. The `Burning rate; mm` header is dimensionally wrong (values are mm/s).
14. **Source metadata is thin.** Only 25 distinct `source_url` values for 892 rows; 9 rows point at the bare `https://psi.nasa.gov`. Citations can identify a campaign but often not the specific test.
15. **Gravity labels are normalized in canonical but not fully in raw.** Canonical has 7 labels; raw files use variants such as `microgravity` and `Microgravity (~0g)`. Canonical normalization is good, but it hides the measured-vs-modeled distinction except through the `Partial-g Bounded` string convention.

---

## 6. Is canonicalization reproducible? (Task 3)

**No. The provenance of `data/processed/canonical_experiments.csv` does not exist in this repository.**

Evidence:

1. **No code reads the raw CSVs.** The only data loader, `src/data/load_data.py`, reads the canonical CSV itself. A repository-wide search found no script that opens anything under `data/raw/`.
2. **No generator was ever committed.** `git log --all --name-only` lists exactly 31 paths across all history; `scripts/pipeline.py` is not among them. The file referenced by `assets/README.md` never existed.
3. **The canonical file arrived with the data.** Commit `45a2d1e` added the canonical CSV and all 17 raw CSVs together, in one commit, with no pipeline, notebook, config, or mapping tables.
4. **The canonical file contains values that normalization cannot produce.** Burning rates for `SAFFIRE` and `FLEX-2` have no source column; two `NTRS` rows have no source file; SAFFIRE-I oxygen is an unstated midpoint; many fields are campaign-level constants. Conversely, several derivable fields are missing or wrong (BASS-II airflow, FLEX-114 pressure).
5. **A 1:1 row mapping exists for 890 of 892 rows**, which is consistent with a previous one-off transformation, but that transformation is not present and its rules (especially for the 42 corrupted airflow values) cannot be recovered from the repository.

**Conclusion:** the canonical CSV is a legacy artifact of unknown provenance. It may be used only as a reference/comparison input until a documented, deterministic pipeline re-derives a validated snapshot from `data/raw` (or until each untraceable value is explicitly quarantined). It must not be treated as ground truth for citations or numeric answers.

---

## 7. Disposition table (every non-data file)

| File | Disposition | Justification summary |
|:--|:--|:--|
| `main.py` | **Replace** | Empty placeholder; becomes the FastAPI entry point. |
| `exp.py` | **Remove** | Scratch PSI downloader with import-time network I/O; no product role. |
| `inventory_psi159.py` | **Remove** | One-off PSI-159 inventory for a study not in the dataset. |
| `requirements.txt` | **Replace** | Incomplete and mismatched with the decided architecture; add deps per phase. |
| `.env.example` | **Refactor** | Keep; expand with documented non-secret configuration as phases require. |
| `README.md` | **Replace** | Three-line blurb; needs real setup/architecture/caveats. |
| `src/data/load_data.py` | **Refactor** | Keep path convention; replace CSV loader with typed Parquet snapshot loader. |
| `src/analytics/analytics.py` | **Remove** | Print-only report; no reusable contract. |
| `src/analytics/advanced_analytics.py` | **Remove** | Print-only crosstabs; duplicate logic. |
| `src/analytics/query_engine.py` | **Remove** | Keyword router replaced by typed query plan + DuckDB compiler. |
| `assets/README.md` | **Refactor** | Valuable catalog, but fix false pipeline reference and investigation count. |
| `LICENSE` | **Keep** | Apache-2.0; correct and required. |
| `.gitignore` | **Refactor (minimal)** | Standard Python template; add only frontend/generated-artifact rules later. |
| `src/__init__.py`, `src/*/__init__.py` | **Add later** | Explicit packaging for `src/flame` and typed imports; Phase 2 decision. |
| `data/raw/*.csv` (17 files) | **Keep immutable** | Original datasets; never modify. |
| `data/processed/canonical_experiments.csv` | **Replace by re-derived snapshot** | Legacy artifact of unknown provenance; keep as read-only reference until superseded. |

---

## 8. Implications for the RAG architecture (for Phase 2 planning, not implemented here)

1. **Provenance must be a first-class field.** Every snapshot row needs a trust tier: `measured` / `modeled` / `derived` / `imputed` / `unknown`, plus source file and source row. The current CSV already contains all five categories but labels only one (`Partial-g Bounded`).
2. **Default numeric answers should use measured rows only.** Modeled and imputed values must be excluded from aggregates unless the user explicitly asks about modeled partial-gravity data, and any displayed number must carry its trust tier.
3. **The structured schema must be repaired before it is frozen.** Required fixes: airflow parse, date normalization, ambient-vs-product CO2/He separation, pressure unit policy, extinction-outcome enum mapping, fuel/material normalization, and removal or quarantine of non-experiment rows.
4. **A Parquet snapshot needs a typed contract.** Pydantic v2 row/schema models, deterministic dtype policies, explicit nullable fields, and validation tests against the raw files.
5. **Query plans need provenance filters built in.** The typed plan should carry `gravity_regime`, `measured_only`, `dataset_family`, and trust-tier constraints, not just numeric predicates.
6. **Citations must resolve to row-level lineage.** With 25 distinct URLs for 892 rows, campaign-level links are insufficient for “verified citations”; the snapshot must retain `source_file`, `source_row`, and `original_test_id`.
7. **Evaluation must include adversarial data-quality questions.** Examples: “compare measured burning rates only”, “is the lunar row measured?”, “what is the airflow for BASS-O5a?”. The last one should refuse or flag corruption rather than return 5.1×10^15.
8. **The 52 modeled rows are analytically useful but must never be mixed silently.** They support “what would lunar/Martian partial-gravity behavior look like under the bounded model?” questions, not “what was measured?” questions.

---

## 9. Items requiring approval before Phase 2

1. Approve or amend the dispositions in §7.
2. Decide whether Phase 2 re-derives the canonical snapshot from `data/raw` (recommended) or preserves the legacy CSV with per-value provenance flags.
3. Decide the policy for untraceable values: drop them, keep them as `unknown`/`imputed`, or keep them with `modeled` labels.
4. Confirm that modeled partial-gravity rows remain in scope for retrieval but excluded from measured-only aggregates by default.
5. Confirm that `assets/README.md` should be rewritten/moved rather than deleted, preserving its facility catalog and scope note.
