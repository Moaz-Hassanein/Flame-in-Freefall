# Data dictionary — `data/processed/experiments.parquet`

This dictionary describes the trusted experiment snapshot produced by
`scripts/build_dataset.py`. It covers the 28 canonical columns plus the 16
provenance, quality, and text-extraction columns added by the ingestion
pipeline.

The snapshot is built under an explicit source policy:

- **450 rows are rebuilt from the immutable Schema A/B files under `data/raw`.**
  Every physical measurement column was verified to match the legacy canonical
  CSV exactly on those rows.
- **442 rows are carried from `data/processed/canonical_experiments.csv`.**
  Their raw tables are free-text experiment logs. Rebuilding them faithfully
  would require inventing authored descriptions, per-family constants, and
  notes, so they remain sourced from the legacy artifact.

The policy is versioned in
`src/flame/ingestion/mappings/source_policy.yaml`. Value changes are controlled
by `src/flame/ingestion/mappings/vocabularies.yaml`, and modeled-row rules by
`src/flame/ingestion/mappings/modeled_rows.yaml`.

## Conventions

- **Null** means no value is asserted. Nulls are never imputed by this pipeline.
- **Structural null** means the family does not measure that field at all.
- **Flagged null** means a value existed but was withheld by a documented rule
  (campaign-range dates and quarantined airflow readings are the only two cases
  in this build).
- **`UNVERIFIED`** means the meaning, unit basis, or provenance cannot be
  established from the available sources. The value may still be present; it
  must not be treated as a validated measurement for the marked aspect.
- Units are recorded in the `Experiment` Pydantic field metadata in
  `src/flame/schemas/experiment.py` and repeated here.
- The Parquet file contains 892 rows and 44 columns. Identifiers are unique.

## Family source policy

| Family | Rows | Source | Notes |
|:--|--:|:--|:--|
| ACME (CIR) | 8 | canonical_legacy | Legacy raw log; authored fields retained. |
| ACME-BRE | 13 | raw_rebuild | Raw `ACME_Extended_Research_Data.csv`. |
| ACME-CFI | 13 | raw_rebuild | Raw `ACME_Extended_Research_Data.csv`. |
| ACME-CFI-G | 4 | raw_rebuild | Raw `NASA_PSI_Complete_Suite_CFIG_SPICE_DAFT.csv`. |
| ACME-CLD | 22 | raw_rebuild | Raw `ACME_Extended_Research_Data.csv`. |
| ACME-EFIELD | 12 | raw_rebuild | Raw `ACME_Extended_Research_Data.csv`. |
| BASS-I | 8 | raw_rebuild | Raw `BASS1_Initial_ISS_Data.csv`. |
| BASS-II | 129 | canonical_legacy | Raw table is a free-text log; legacy values retained. |
| DAFT / DAFT-2 | 2 | raw_rebuild | Raw PSI complete-suite file. |
| FLARE (JAXA/Kibo) | 30 | raw_rebuild | Raw `JAXA_FLARE_Kibo_Flight_Data.csv`. |
| FLEX | 274 | canonical_legacy | Raw log requires authored constants and descriptions. |
| FLEX-2 | 10 | canonical_legacy | Raw log requires authored constants and descriptions. |
| GRC Drop Tower | 95 | raw_rebuild | Raw `NASA_GRC_Drop_Tower_Quenching.csv`. |
| LUCI / FM2 (Future Partial-g) | 2 | raw_rebuild | Reference rows; both are modeled. |
| MGM (Smoldering) | 65 | raw_rebuild | Raw `NASA_MGM_Smoldering_Combustion.csv`. |
| NASA-STD-6001 | 59 | raw_rebuild | Two raw materials files. |
| NTRS-Combustion | 1 | canonical_legacy | No raw source file. |
| NTRS-FireSafety | 1 | canonical_legacy | No raw source file. |
| Partial-g Bounded (0g+1g / E-FIELD) | 50 | raw_rebuild | All 50 rows are modeled. |
| SAFFIRE-I | 4 | canonical_legacy | Includes 2 pre-test placeholder rows. |
| SAFFIRE-II | 5 | canonical_legacy | |
| SAFFIRE-III | 2 | canonical_legacy | |
| SAFFIRE-IV | 3 | canonical_legacy | |
| SAFFIRE-V | 3 | canonical_legacy | |
| SAFFIRE-VI | 2 | canonical_legacy | |
| SAME (Aerosol) | 50 | raw_rebuild | Raw `NASA_SAME_Aerosol_Detector_Data.csv`. |
| SAME-R | 2 | raw_rebuild | Raw PSI complete-suite file. |
| SLICE | 8 | raw_rebuild | Raw file omits the authored source/notes suffixes. |
| SOFIE | 12 | raw_rebuild | Raw `SOFIE_Flight_Data.csv`. |
| SPICE | 3 | raw_rebuild | Raw PSI complete-suite file. |

`investigation_id` has 35 distinct values across these 30 families.

## Canonical columns

### Identity and descriptive fields

| Column | Type | Nulls | Applies to | Meaning and caveats |
|:--|:--|--:|:--|:--|
| `experiment_id` | string | 0 | All rows | Stable, unique pipeline identifier. It is the join key to the legacy canonical CSV. |
| `dataset_family` | string | 0 | All rows | Experiment family or campaign. Thirty values; see the table above. |
| `investigation_id` | string | 0 | All rows | Owning investigation or programme identifier. Thirty-five distinct values. |
| `original_test_id` | string | 0 | All rows | Test identifier used by the source. For all 450 raw-rebuild rows it is set equal to `experiment_id` (verified in the legacy CSV). For carried legacy rows it retains the original legacy value, which differs from `experiment_id` on 434 rows. |
| `fuel_material` | string | 0 | All rows | Fuel or specimen label after the versioned vocabulary mapping. 112 distinct values. The pre-mapping value is in `fuel_material_raw`. No semantic merge was applied. |
| `material_category` | string | 0 | All rows | Material class descriptor. 62 distinct values. The mapping table is deliberately empty; values pass through unchanged. Pre-mapping value is in `material_category_raw`. |
| `sample_description` | string | 0 | All rows | Authored specimen description. It is not a Schema A/B raw column: for the 450 raw-rebuild rows it is carried from the legacy artifact; for legacy rows it is authored. Do not treat it as a source-measured field. |
| `gravity_condition` | string | 0 | All rows | Gravity descriptor. Seven values: `Microgravity (~0g)` (686), `Drop Tower Microgravity (10^-5 g)` (95), `Normal Gravity (1.0g — WSTF Upward Screening Bound)` (59), and four `Partial-g Bounded Model: ...` strings (52). The `~0g` and partial-gravity labels are descriptive, not measured accelerations; see `is_modeled`. |
| `source_name` | string | 0 | All rows | Human-readable source or programme name. For SLICE, the raw file's shorter wording differs from the carried legacy wording. |
| `source_url` | string | 0 | All rows | Source landing page or dataset URL. |
| `notes` | string | 0 | All rows | Source notes plus, for some legacy families, authored clarifications. For SLICE, authored facility suffixes are present in the carried legacy value but not in the raw file. |
| `facility_hardware` | string | 0 | All rows | Facility and hardware descriptor. Like `sample_description`, this is carried from the legacy artifact for raw-rebuild rows and is not a raw measurement column. |
| `test_date` | string (ISO 8601 date) | 23 | All rows | Test or campaign date. Accepted inputs: `YYYY-MM-DD`, `M/D/YYYY`, and `M/D/YY`. Two-digit years use the explicit pivot 00–68 → 2000–2068 and 69–99 → 1969–1999. The 23 campaign ranges such as `2017-2024` are nulled with `TEST_DATE_CAMPAIGN_RANGE`; they are not single dates. Original text is in `test_date_raw`. |

### Measurement fields

All numeric fields are nullable. A null is never filled. Soft plausibility
violations become flags; they never change the value.

| Column | Unit | Nulls | Families with values | Meaning and caveats |
|:--|:--|--:|:--|:--|
| `oxygen_pct` | percent | 2 | All families except two SAFFIRE-I rows | Oxygen fraction of the test atmosphere. Whether every source reports volume or mass percent is `UNVERIFIED`; volume percent is the conventional reading. The audit found an implicit midpoint value for SAFFIRE-I in the legacy data; treat SAFFIRE-I oxygen values as `UNVERIFIED` provenance. |
| `pressure_mmhg` | mmHg | 0 | All rows | Absolute pressure. For raw-rebuild rows it is derived as `round(pressure_kpa * 7.50061683, 1)` and was verified to reproduce the legacy value exactly on all 450 rows. For legacy rows it is carried. One value is zero `FLEX-114`, whose `pressure_kpa` is also null; both facts are flagged. |
| `pressure_kpa` | kPa | 1 | All rows except `FLEX-114` | Absolute pressure in kilopascals. Null for `FLEX-114`, flagged `PRESSURE_KPA_MISSING`. The soft consistency check allows the two pressure columns to differ by up to 1 mmHg; no row exceeds that tolerance. |
| `burn_time_s` | s | 8 | All families except some legacy FLEX rows | Burn or test duration. The cross-family definition is `UNVERIFIED`: some sources may report test duration, others burn duration. Seven zero values are retained and flagged `BURN_TIME_ZERO` (`SOFIE-006`, `STD6001-001/003/005/006/007/008`). `BASS-M5` at 10003.4 s is retained and flagged `BURN_TIME_IMPLAUSIBLE`. |
| `extinction_outcome` | categorical string | 0 | All rows | Normalised outcome label; 70 distinct values. One case-only mapping is applied: `Self-extinguished` → `Self-Extinguished` (1 row). The pre-mapping value is in `extinction_outcome_raw`. Labels are not merged across semantically similar wording. |
| `extinction_diameter_mm` | mm | 564 | ACME-CFI-G, DAFT, FLARE, FLEX, FLEX-2, GRC Drop Tower, LUCI/FM2, NTRS-Combustion, Partial-g, SAME-R, SPICE | Diameter associated with extinction or quenching. Eight zeros are retained and not imputed. Whether a family reports a final char diameter, a quench diameter, or another definition is `UNVERIFIED`. Structural nulls dominate because most families do not measure this field. |
| `initial_diameter_mm` | mm | 204 | Most raw-rebuild families; not ACME (CIR), BASS-II, SAFFIRE, NTRS-FireSafety | Initial specimen or characteristic diameter. The exact geometric definition is `UNVERIFIED` across families (droplet, rod, or sample width). Zero is not present. |
| `burning_rate_mms` | mm/s | 155 | Most families; not ACME (CIR), BASS-II, NTRS-Combustion | Burning, spread, or regression rate as reported. **Cross-family meaning is `UNVERIFIED`**; the column may combine flame-spread rate, regression rate, and mass-loss-derived rate. Some families have suspicious constants in the legacy data (for example FLEX-2 is a single value 0.45 for all 10 rows). Do not compare rates across families without checking the source definition. |
| `airflow_velocity_cms` | cm/s | 53 | All families except 11 rows that were already null | Forced-flow velocity. Eleven rows were null in the source (`BASS-O12`, `BASS-O6`, `BASS-O7`, `BASS-O8a`, `BASS-O8b`, `BASS-O9`, `BASS-P2`, `BASS-P3a`, `BASS-P3b`, `SAF1-F1C1/F1C2`, `SAF1-F2C1/F2C2`). Forty-two BASS-II values above the 1000 cm/s quarantine threshold are nulled and flagged `AIRFLOW_QUARANTINED`. Those values are concatenated free-text readings; no evidence-based repair exists. Every original value is retained in `airflow_velocity_cms_raw`. |
| `flame_temp_k` | K | 7 | All families; 6 nulls in NASA-STD-6001 and 1 in SOFIE | Reported flame or reaction temperature. The measurement method and whether the value is a peak, mean, or colour temperature are `UNVERIFIED`. Several families contain campaign-level constant or near-constant values in the legacy data, for example BASS-II has 2 distinct values for 129 rows and FLEX has 2 distinct values for 274 rows; SAFFIRE is constant within each subfamily. Treat these as reported, not independently validated, values. |
| `ignition_power_w` | W | 415 | ACME, BASS-I, DAFT, FLARE, FLEX-2, GRC Drop Tower, LUCI/FM2, MGM, NASA-STD-6001, NTRS, Partial-g, SAFFIRE, SAME, SLICE, SOFIE, SPICE | Igniter power, where reported. Structural nulls in FLEX and BASS-II. The definition (electrical input vs delivered power) is `UNVERIFIED`. |
| `ignition_time_s` | s | 415 | Same coverage as `ignition_power_w` | Igniter duration, where reported. Structural nulls in FLEX and BASS-II. |
| `co2_pct` | percent | 21 | All families except NTRS-Combustion, FLEX-2, and some BASS-II rows | CO2 fraction. **The column conflates ambient/diluent CO2 with combustion-produced CO2**, and the audit could not separate the two per family. Treat the physical meaning as `UNVERIFIED`; do not use it as a combustion-yield measurement without source review. |
| `he_pct` | percent | 0 | All rows | Helium fraction carried from the legacy canonical CSV. It is not present in the Schema A/B raw files. FLEX is the only family with non-zero values (5–45%); every other family is `0.0`. **The provenance of the non-FLEX zero values and the exact basis of the FLEX values are `UNVERIFIED`.** |
| `co_ppm` | ppm | 297 | Most families; not FLEX, FLEX-2, NTRS-Combustion | Carbon-monoxide concentration. Structural nulls in the largest legacy families. The measurement location (in-flame, exhaust, ambient) is `UNVERIFIED`. |

## Provenance, quality, and enrichment columns

| Column | Type | Nulls | Meaning and caveats |
|:--|:--|--:|:--|
| `is_modeled` | boolean | 0 | `true` for exactly 52 rows: 50 `Partial-g Bounded (0g+1g / E-FIELD)` rows and 2 `LUCI / FM2 (Future Partial-g)` reference rows. Rules match `dataset_family` plus the `gravity_condition` prefix `Partial-g Bounded Model`; no row identifiers are used. These rows are engineering bounding models or references, not direct partial-gravity measurements. |
| `data_quality_flags` | list of strings | 0 | Sorted flags for the row. An empty list means no flag fired. See the flag table below. |
| `test_date_raw` | string | 0 | Original date text before parsing: 466 ISO values, 403 US-format values, and 23 campaign ranges. Never altered. |
| `extinction_outcome_raw` | string | 0 | Outcome label before vocabulary normalisation. |
| `material_category_raw` | string | 0 | Material category before normalisation (no mapping is currently applied). |
| `fuel_material_raw` | string | 0 | Fuel label before normalisation. |
| `airflow_velocity_cms_raw` | float | 11 | Airflow value before quarantine. All 42 quarantined readings are retained here, including the maximum `5,105,204,962,494,442.0` cm/s. The 11 source nulls remain null. |
| `specimen_length_cm` | cm | 875 | First dimension extracted from `sample_description` for 17 SAFFIRE-II–VI rows. Range 30–100 cm. SAFFIRE-I pre-test rows contain literal `Nonecm` placeholders and remain null. |
| `specimen_width_cm` | cm | 875 | Second dimension for the same 17 rows. Range 5–94 cm. |
| `specimen_thickness_cm` | cm | 875 | Third dimension for the same 17 rows. Range 0.025–1.0 cm. |
| `flow_direction` | categorical string | 875 | `Concurrent` (13 rows) or `Opposed` (4 rows), extracted from the parenthesised `(Flow: ...)` text for SAFFIRE-II–VI. SAFFIRE-I pre-test rows have `(Flow: nan)` and stay null. |
| `microgravity_duration_s` | s | 797 | Microgravity duration extracted from the `Microgravity duration: ... s` note for all 95 GRC Drop Tower rows. Range 1.21–4.99 s. |
| `pi_name` | string | 763 | Principal-investigator surname extracted from the `PI: ...` note for all 129 BASS-II rows. Six surnames: `T'ien` (29), `Olson` (27), `Fernandez-Pello` (27), `Bhattacharjee` (22), `Miller` (20), `Ferkul` (4). Full names and affiliations are not recorded and are `UNVERIFIED`. |
| `source_file` | string | 0 | Input file that produced the row: one of 11 `data/raw/*.csv` files or `data/processed/canonical_experiments.csv`. |
| `source_row` | integer | 0 | 1-based data row in `source_file`, excluding the header. |
| `record_source` | categorical string | 0 | `raw_rebuild` (450 rows) or `canonical_legacy` (442 rows). |

## Quality flags

Flags are additive and sorted. A flag documents a decision; except for the two
withholding rules, it never changes a value.

| Flag | Rows in this build | Meaning |
|:--|--:|:--|
| `AIRFLOW_QUARANTINED` | 42 | `airflow_velocity_cms` exceeded the 1000 cm/s threshold and was nulled; the raw value is retained in `airflow_velocity_cms_raw`. |
| `BURN_TIME_IMPLAUSIBLE` | 1 | `burn_time_s` exceeds the 3600 s plausibility maximum; value retained. |
| `BURN_TIME_ZERO` | 7 | `burn_time_s` is zero; value retained. |
| `PRESSURE_KPA_MISSING` | 1 | `pressure_kpa` is null; row retained. |
| `PRESSURE_MMHG_ZERO` | 1 | `pressure_mmhg` is zero; value retained. |
| `TEST_DATE_CAMPAIGN_RANGE` | 23 | `test_date` was a campaign range such as `2017-2024`, not a single date; value nulled. |

The validator also defines `TEST_DATE_MISSING`, `TEST_DATE_UNPARSEABLE`,
`OXYGEN_OUT_OF_RANGE`, `PRESSURE_NEGATIVE`, `PRESSURE_UNIT_MISMATCH`,
`BURN_TIME_NEGATIVE`, `DIAMETER_NEGATIVE`, `BURNING_RATE_NEGATIVE`,
`AIRFLOW_NEGATIVE`, `FLAME_TEMP_OUT_OF_RANGE`, `GAS_FRACTION_OUT_OF_RANGE`,
`EMISSIONS_NEGATIVE`, and `IGNITION_NEGATIVE`. None fired in this snapshot. They
remain active for future builds.

Hard validation fails the build when identifiers are missing or duplicated,
required columns are absent, provenance fields are empty, or a declared type is
wrong. Soft range violations become flags only.

## Vocabulary changes applied

Only explicit, versioned entries change a value. All other values pass through
as identity.

| Column | Original | Normalised | Rows |
|:--|:--|:--|--:|
| `extinction_outcome` | `Self-extinguished` | `Self-Extinguished` | 1 |
| `fuel_material` | `1/4 blac rod` | `1/4" black rod` | 1 |
| `fuel_material` | `1/4 black rod` | `1/4" black rod` | 1 |
| `fuel_material` | `1/4"  black rod` | `1/4" black rod` | 1 |
| `fuel_material` | `1/4 clear rod` | `1/4" clear rod` | 1 |
| `fuel_material` | `3/8"clear rod` | `3/8" clear rod` | 1 |
| `fuel_material` | `PEEK (Polyetheretherketone)` | `PEEK (Polyether ether ketone)` | 1 |
| `fuel_material` | `Velcro Hook/Loop Fastener` | `Velcro Hook-and-Loop (Nylon)` | 11 |
| `gravity_condition` | `microgravity` | `Microgravity (~0g)` | 28 |

Semantic merges that were considered but deliberately not applied are listed in
`mappings/vocabularies.yaml` under `proposed_not_applied`. They include
`Blowoff` → `Convective Blowoff`, `Methanol` → `Methanol Droplet`,
`n-Heptane` → `n-Heptane Droplet`, `SIBAL Fabric` → `SIBAL (Cotton-Fiberglass Blend)`,
and `Nomex (Aramid)` → `Nomex Fabric (Aramid)`.

## `UNVERIFIED` items pending owner review

1. **Cross-family meaning of `burning_rate_mms`.** The snapshot combines rates
   whose source definitions may be flame spread, regression, or mass-loss
   based. Comparisons across families are `UNVERIFIED`.
2. **Provenance of `he_pct`.** The column exists only in the legacy artifact.
   All non-FLEX values are `0.0`; whether that means “no helium”, “not
   applicable”, or “not reported” is `UNVERIFIED`.
3. **`co2_pct` basis.** Ambient/diluent CO2 and combustion-produced CO2 are not
   separated. The physical interpretation per family is `UNVERIFIED`.
4. **`flame_temp_k` definition.** Measurement method (thermocouple, pyrometry,
   colour temperature) and whether values are peak or mean are `UNVERIFIED`;
   several families carry campaign-level constants.
5. **`burn_time_s` definition.** Test duration versus burn duration is
   `UNVERIFIED` across families.
6. **`oxygen_pct` basis and SAFFIRE-I provenance.** Volume versus mass percent is
   `UNVERIFIED`; the legacy SAFFIRE-I values include an implicit midpoint.
7. **`extinction_diameter_mm` definition.** Final char diameter versus quench
   diameter is `UNVERIFIED`.
8. **`initial_diameter_mm` geometry.** Droplet, rod, and sample-width meanings
   are mixed across families and are `UNVERIFIED`.
9. **PI identity.** `pi_name` contains surnames only; full names and
   affiliations are `UNVERIFIED`.
10. **Legacy-carried rows.** The 442 rows from
    `data/processed/canonical_experiments.csv` cannot be re-derived from their
    raw logs without inventing authored descriptions and constants. Their
    provenance is the legacy artifact, and the question of whether they should
    eventually be re-derived remains open.

## Reproduction

```bash
# Byte-identical artifacts for a fixed timestamp
SOURCE_DATE_EPOCH=1763070000 uv run python scripts/build_dataset.py
SOURCE_DATE_EPOCH=1763070000 uv run python scripts/build_dataset.py

# Verification
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

The build writes:

- `data/processed/experiments.parquet`
- `data/processed/provenance_manifest.json`
- `data/reports/quality_report.md`
- `data/reports/canonical_diff.csv`

Input checksums, row counts, thresholds, the pipeline version, and the git commit
are recorded in the provenance manifest. `data/raw` and the legacy canonical CSV
are read-only inputs and are never modified by the pipeline.
