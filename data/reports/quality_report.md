# Data quality report

- Generated at: `2025-11-13T21:40:00+00:00`
- Pipeline version: `0.3.0`
- Git commit: `c03126af689d3e769cc7b362705950d6f2dcef94`
- Rows: **892**

## Row counts

| Group | Rows |
|:--|--:|
| Total | 892 |
| Rebuilt from raw | 450 |
| Carried from legacy canonical | 442 |

| Family | Rows | Source |
|:--|--:|:--|
| ACME (CIR) | 8 | canonical_legacy |
| ACME-BRE | 13 | raw_rebuild |
| ACME-CFI | 13 | raw_rebuild |
| ACME-CFI-G | 4 | raw_rebuild |
| ACME-CLD | 22 | raw_rebuild |
| ACME-EFIELD | 12 | raw_rebuild |
| BASS-I | 8 | raw_rebuild |
| BASS-II | 129 | canonical_legacy |
| DAFT / DAFT-2 | 2 | raw_rebuild |
| FLARE (JAXA/Kibo) | 30 | raw_rebuild |
| FLEX | 274 | canonical_legacy |
| FLEX-2 | 10 | canonical_legacy |
| GRC Drop Tower | 95 | raw_rebuild |
| LUCI / FM2 (Future Partial-g) | 2 | raw_rebuild |
| MGM (Smoldering) | 65 | raw_rebuild |
| NASA-STD-6001 | 59 | raw_rebuild |
| NTRS-Combustion | 1 | canonical_legacy |
| NTRS-FireSafety | 1 | canonical_legacy |
| Partial-g Bounded (0g+1g / E-FIELD) | 50 | raw_rebuild |
| SAFFIRE-I | 4 | canonical_legacy |
| SAFFIRE-II | 5 | canonical_legacy |
| SAFFIRE-III | 2 | canonical_legacy |
| SAFFIRE-IV | 3 | canonical_legacy |
| SAFFIRE-V | 3 | canonical_legacy |
| SAFFIRE-VI | 2 | canonical_legacy |
| SAME (Aerosol) | 50 | raw_rebuild |
| SAME-R | 2 | raw_rebuild |
| SLICE | 8 | raw_rebuild |
| SOFIE | 12 | raw_rebuild |
| SPICE | 3 | raw_rebuild |

## Source policy

Raw-rebuild families were rebuilt from immutable Schema A/B files. Legacy families were carried from the existing canonical CSV because their raw tables are free-text logs with authored descriptions and constants that cannot be reconstructed without inventing transformations.

- Raw-rebuild rows: **450**
- Legacy-carried rows: **442**

## Rebuild fidelity (raw-rebuild rows, before cleaning)

Every measurement column is compared with the legacy canonical CSV on the 450 rows rebuilt from raw. A non-zero count is a known provenance difference, not a silent loss.

| Column | Mismatches | Example (experiment_id, pipeline, legacy) |
|:--|--:|:--|
| gravity_condition | 28 | `BASS1-001`: `'microgravity'` vs `'Microgravity (~0g)'` |
| source_name | 8 | `SLICE-001`: `'NASA PSI / MSG'` vs `'NASA PSI / ISS MSG SLICE (Microgravity Science Glovebox)'` |
| notes | 8 | `SLICE-001`: `'Suppressed by CO2 flood at 12.5% volume fraction.'` vs `'Suppressed by CO2 flood at 12.5% volume fraction. [Facility: ISS MSG + SPICE Fan-Driven Flow Duct]'` |

## Final output versus legacy canonical

Row-level mismatches written to `data/reports/canonical_diff.csv`: **502** cells.

| Column | Mismatches |
|:--|--:|
| fuel_material | 17 |
| extinction_outcome | 1 |
| airflow_velocity_cms | 42 |
| test_date | 426 |
| source_name | 8 |
| notes | 8 |

Expected final-output differences are: date normalisation (M/D/YYYY and M/D/YY converted to ISO), nulled campaign-range dates, quarantined BASS-II airflow values, the explicit vocabulary mappings, and the SLICE source/notes wording that the raw file does not contain. Raw values remain in the `*_raw` columns.

## Quality flags

| Flag | Count | Meaning |
|:--|--:|:--|
| `AIRFLOW_QUARANTINED` | 42 | airflow_velocity_cms above the quarantine threshold; nulled. |
| `BURN_TIME_IMPLAUSIBLE` | 1 | burn_time_s exceeds the plausibility maximum; value retained. |
| `BURN_TIME_ZERO` | 7 | burn_time_s is zero; value retained. |
| `PRESSURE_KPA_MISSING` | 1 | pressure_kpa is null; value retained. |
| `PRESSURE_MMHG_ZERO` | 1 | pressure_mmhg is zero; value retained. |
| `TEST_DATE_CAMPAIGN_RANGE` | 23 | test_date was a campaign range, not a date; nulled. |

## Per-family null rates

| Family | Rows | oxygen_pct | pressure_mmhg | pressure_kpa | burn_time_s | extinction_diameter_mm | initial_diameter_mm | burning_rate_mms | airflow_velocity_cms | flame_temp_k | ignition_power_w | ignition_time_s | co2_pct | he_pct | co_ppm |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| ACME (CIR) | 8 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| ACME-BRE | 13 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| ACME-CFI | 13 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| ACME-CFI-G | 4 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| ACME-CLD | 22 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| ACME-EFIELD | 12 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| BASS-I | 8 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| BASS-II | 129 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% | 100.0% | 39.5% | 0.0% | 100.0% | 100.0% | 4.7% | 0.0% | 6.2% |
| DAFT / DAFT-2 | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| FLARE (JAXA/Kibo) | 30 | 0.0% | 0.0% | 0.0% | 0.0% | 53.3% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| FLEX | 274 | 0.0% | 0.0% | 0.4% | 2.2% | 28.1% | 4.4% | 5.8% | 0.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| FLEX-2 | 10 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% |
| GRC Drop Tower | 95 | 0.0% | 0.0% | 0.0% | 0.0% | 36.8% | 36.8% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| LUCI / FM2 (Future Partial-g) | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| MGM (Smoldering) | 65 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| NASA-STD-6001 | 59 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 10.2% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| NTRS-Combustion | 1 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 100.0% |
| NTRS-FireSafety | 1 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| Partial-g Bounded (0g+1g / E-FIELD) | 50 | 0.0% | 0.0% | 0.0% | 0.0% | 34.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| SAFFIRE-I | 4 | 50.0% | 0.0% | 0.0% | 50.0% | 100.0% | 100.0% | 50.0% | 50.0% | 0.0% | 50.0% | 50.0% | 100.0% | 0.0% | 100.0% |
| SAFFIRE-II | 5 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| SAFFIRE-III | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| SAFFIRE-IV | 3 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| SAFFIRE-V | 3 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| SAFFIRE-VI | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| SAME (Aerosol) | 50 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| SAME-R | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| SLICE | 8 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| SOFIE | 12 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 8.3% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| SPICE | 3 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Rates are percentages of null values within the family. No value was imputed.

## Vocabulary mappings

Only the entries below change a value. All other values pass through as identity.

### `extinction_outcome` (mapping version 1)

| Original | Normalised | Rows |
|:--|:--|--:|
| `Self-extinguished` | `Self-Extinguished` | 1 |

- Non-null values: **892**; null values: **0**.
- Identity values (70): `Accelerated Upward Spread`, `Aerosol Discrimination Verified`, `Aerosol Quenched`, `Blowoff`, `Blowoff Extinction`, `Burnout`, `Char Formation Extinction`, `Chemical Radical Scavenging`, `Classical Radiative Extinction`, `Complete Burnout / Upward Spread`, `Complete Burnout in Cygnus`, `Complete Consumption`, `Completion`, `Conditional Pass`, `Convective Blowoff`, `Cool Flame Boundary Quenching`, `Cool Flame Persistence`, `Cool Flame Quenching`, `Cool Flame Steady State`, `Cool Flame Transition`, `Delayed Self-Extinction`, `Detector Alarm Triggered`, `Diffusive Quenching`, `Dilution Quenching Extinction`, `Disruption`, `Electric-Field Quenched`, `Extinction`, `Fail (Burned > 15cm)`, `Far-field Smoke Transport`, `Flame Spread & Extinction`, `Hypoxic Radiative Extinction`, `Incomplete Burn (Time Limit)`, `Ionic Wind Deflection`, `Low Flammability Extinction`, `Low Oxygen Quenching`, `No Ignition`, `Opposed Flame Spread`, `Pass (Self-Extinguishing < 15cm)`, `Prolonged Low-Temperature Combustion`, `Pyrolysis Aerosol Termination`, `Pyrolysis Extinction`, `Radiative Extinction`, `Radiative Quenching`, `Radiative Soot Quenching`, `Rapid Complete Burnout`, `Rapid Spread on Thin Section`, `Self-Extinction`, `Self-Extinguished`, `Self-Sustained Smolder`, `Self-extinguished Immediately`, `Slow Flame Spread with Charring`, `Smolder Quenched`, `Soot Smoke-Point Transition`, `Soot-Induced Radiative Extinction`, `Soot-free Blue Flame Radiative Extinction`, `Steady Diffusion Flame`, `Steady Radiative Balance`, `Sub-Micron Smoke Saturation`, `Suppression`, `Sustained Buoyant-Assisted Spread (Bounded)`, `Sustained Combustion`, `Sustained Flame`, `Sustained Non-Sooting Flame`, `Thermal Evaporation Suppression`, `Transition to Flaming`, `Two-Stage Cool Flame Extinction`, `Two-Stage Pyrolysis Extinction`, `Vigorous Flame Propagation`, `Vigorous Micro-explosion Extinction`, `Vigorous Pyrolysis & Burnout`

### `material_category` (mapping version 1)

No value is remapped in this build.

- Non-null values: **892**; null values: **0**.
- Identity values (62): `Acrylic Polymer`, `Aero Polyimide Wiring`, `Aerospace Fabric (Partial-g Reference)`, `Aerospace High-Temp Polymer`, `Aerospace Textile`, `Burning Rate Emulator`, `Cellulose Fiber`, `Cellulosic Solid`, `Coflow Laminar Gas Flame`, `Composite Circuit Board`, `Elastomer`, `Electrical Cable Insulation`, `Electrical Insulation Material`, `Electrical Wire Jacketing`, `Electrostatic Flame Interaction`, `Engineering Thermoplastic`, `Fabric / Textile`, `Fabric Blend`, `Fastener Material`, `Flame-Resistant Aramid`, `Flame-Retarded Polymer Foam`, `Flexible Wire Coating`, `Fluoropolymer Wire Wrap`, `Gaseous Alkane (Spherical Burner)`, `Gaseous Alkene`, `Gaseous Flame & Suppressant`, `Gaseous Hydrocarbon`, `Gaseous Hydrocarbon Jet`, `High-Strength Aramid`, `High-Strength Polyimide`, `Hydrocarbon Gas Flame`, `Hydrocarbon Wax`, `Impact Shielding Fiber`, `Insulation`, `Laminar Gas Jet`, `Large-Scale Spacecraft Hull & Membrane`, `Large-Scale Spacecraft Material`, `Liquid Alcohol Droplet`, `Liquid Alkane Droplet`, `Liquid Droplet`, `Liquid Droplet (Cool Flame)`, `Liquid Droplet Array`, `Liquid Hydrocarbon`, `Open-Pore Filter Foam`, `Optical Window / Shield`, `Planetary Dust / Smoke Discrimination`, `Polyester Fastener System`, `Porous Polymer Foam`, `Rigid Polymer`, `Sealant / O-Ring`, `Solid Polymer`, `Solid Polymer (Partial-g Reference)`, `Solid Polymer / Film`, `Soot-Free Diffusion Jet`, `Space Suit Outer Layer`, `Spacecraft Potting Silicone`, `Spacecraft Sealant/Cable Aerosol`, `Spacecraft Wire Insulation Aerosol`, `Structural Thermoplastic`, `Thermal Insulation Blanket`, `Thermal Protection Multilayer`, `Thermoplastic`

### `fuel_material` (mapping version 1)

| Original | Normalised | Rows |
|:--|:--|--:|
| `1/4 blac rod` | `1/4" black rod` | 1 |
| `1/4 black rod` | `1/4" black rod` | 2 |
| `1/4 clear rod` | `1/4" clear rod` | 1 |
| `1/4"  black rod` | `1/4" black rod` | 1 |
| `3/8"clear rod` | `3/8" clear rod` | 2 |
| `PEEK (Polyetheretherketone)` | `PEEK (Polyether ether ketone)` | 2 |
| `Velcro Hook/Loop Fastener` | `Velcro Hook-and-Loop (Nylon)` | 8 |

- Non-null values: **892**; null values: **0**.
- Identity values (112): `0.5" black rod`, `1-Propanol`, `1/2" clear rod`, `1/4" black rod`, `1/4" clear rod`, `100 micron film   2 cm wide`, `2 cm   0.4 mm thick film`, `200 micron  2 cm wide`, `3/8" black rod`, `3/8" clear rod`, `300 micron film   2 cm wide`, `4 cm spherical section`, `400 micron film   2 cm wide`, `Beta Cloth (PTFE / Woven Glass)`, `Black PMMA Rod (6.35mm)`, `Cellulose Filter Paper Stack`, `Clear Diluted Laminar Jet Flame`, `Clear PMMA Rod (6.35mm)`, `Clear PMMA Rod (9.5mm)`, `Cotton Textile Blend`, `Cotton-Fiberglass Fabric (SIBAL)`, `Delrin (Polyoxymethylene)`, `Dimethyl Ether (Counterflow Burner)`, `Ethanol (Pure)`, `Ethanol Droplet`, `Ethylene (C2H4 Laminar Co-flow Jet)`, `Ethylene (Coflow Tube Burner)`, `Ethylene Laminar Flame`, `Ethylene/Air Coflow Laminar Flame`, `Ethylene/Air Micro-Burner`, `Flexible Polyurethane Foam (Open-Cell)`, `Heptane`, `Heptane Pool Burner`, `Hexane`, `Ionized Methane Diffusion Flame (+5kV)`, `Iso-octane`, `Japan Wax candle`, `Kapton Film Overheated Wire Pyrolysis`, `Kapton Polyimide Film`, `Kevlar 29 Aramid Fabric`, `Kevlar 29 Fabric`, `Lunar Highlands Dust Simulant + Pyrolysis Smoke Mix`, `Lunar Regolith Simulant (JSC-1A) vs Lampwick Smoke`, `Methane (Electrode Burner)`, `Methane (Flat Porous Burner)`, `Methane / n-Butane Blend (Spherical Burner)`, `Methane Gaseous Jet`, `Methane/Air Coflow Jet`, `Methanol`, `Methanol (Pure)`, `Methanol Droplet`, `Methanol Droplet Array`, `Nomex (Aramid)`, `Nomex / Cotton-Fiberglass SIBAL (FM2 Reference)`, `Nomex Aramid Fabric`, `Nomex Fabric`, `Nomex Fabric (Aramid)`, `Nomex HT90-40 Fabric`, `Nomex III-A (Aramid)`, `Overheated Kapton-Insulated Wire`, `Overheated PTFE-Insulated Wire (AWG 20)`, `Overheated Silicone Rubber Cable`, `PEEK (Polyether ether ketone)`, `PMMA (Acrylic Sheet)`, `PMMA (Acrylic Slab)`, `PMMA (Acrylic)`, `PMMA (Polymethyl Methacrylate)`, `PMMA (Step-profile 4-10mm)`, `PMMA (Thick Slab 10mm)`, `PMMA Cylinder (Cast Acrylic)`, `PMMA Cylinder / Solid Polymer (LUCI Reference)`, `PMMA Flat Slab (20mm wide)`, `PMMA Solid Strip`, `Polycarbonate (Lexan Sheet)`, `Polyethylene (LDPE)`, `Polyethylene-coated Wire`, `Polyurethane Foam with TCPP Retardant`, `Porous Flat Burner (Methane/Heptane Simulated)`, `Pre-test flow visulation data for sample 1`, `Pre-test flow visulation data for sample 2`, `Propane (C3H8 Laminar Co-flow Jet)`, `Propylene (C3H6 Laminar Co-flow Jet)`, `Pyrex Borosilicate Glass-Epoxy`, `Pyrolyzing Cotton Wick Precursor`, `RTV 560 Silicone Elastomer`, `Reticulated Polyurethane Foam`, `SIBAL (Cotton-Fiberglass Blend)`, `SIBAL Fabric`, `SIBAL Fabric (Cotton/Fiberglass)`, `Silicone Elastomer & Teflon Co-Pyrolysis`, `Silicone Electrical Cable Insulation`, `Silicone Membrane (Medium)`, `Silicone Membrane (Thick)`, `Silicone Membrane (Thin)`, `Silicone Rubber Cable Insulation`, `Silicone Rubber Gasket`, `Silicone Rubber Sheet`, `Solid Wax Cylinder (Paraffin)`, `Teflon (PTFE Fluoropolymer)`, `Tefzel ETFE Film`, `Torlon 4203 (Polyamide-imide)`, `Velcro Hook-and-Loop (Nylon)`, `n-Butane (Normal Spherical Diffusion Flame)`, `n-Butane / Nitrogen (Inverse Inside-Out Flame)`, `n-Butane /CO2 Diluent (Inverse Inside-Out Flame)`, `n-Decane`, `n-Heptane`, `n-Heptane / Decane (Surrogate)`, `n-Heptane / Iso-octane (50/50)`, `n-Heptane Droplet`, `n-Octane`, `n-Octane Droplet`

### `gravity_condition` (mapping version 1)

| Original | Normalised | Rows |
|:--|:--|--:|
| `microgravity` | `Microgravity (~0g)` | 28 |

- Non-null values: **892**; null values: **0**.
- Identity values (7): `Drop Tower Microgravity (10^-5 g)`, `Microgravity (~0g)`, `Normal Gravity (1.0g — WSTF Upward Screening Bound)`, `Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001)`, `Partial-g Bounded Model: Lunar (0.16g — Pre-FM2 Flight Reference)`, `Partial-g Bounded Model: Lunar (0.16g — Pre-LUCI Flight Reference)`, `Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001)`

## Quarantined airflow readings

Threshold: **1000 cm/s**. Quarantined rows: **42**. Null before quarantine: **11**; null after quarantine: **53**.

| experiment_id | Family | Source file | Row | Raw airflow (cm/s) |
|:--|:--|:--|--:|--:|
| `BASS-B10` | BASS-II | `data/processed/canonical_experiments.csv` | 295 | 54,321 |
| `BASS-B11` | BASS-II | `data/processed/canonical_experiments.csv` | 296 | 5,311 |
| `BASS-B13` | BASS-II | `data/processed/canonical_experiments.csv` | 298 | 1,054,321 |
| `BASS-B6` | BASS-II | `data/processed/canonical_experiments.csv` | 291 | 3,510 |
| `BASS-M10` | BASS-II | `data/processed/canonical_experiments.csv` | 321 | 101,714,108 |
| `BASS-M11` | BASS-II | `data/processed/canonical_experiments.csv` | 322 | 10,201,512 |
| `BASS-M15` | BASS-II | `data/processed/canonical_experiments.csv` | 326 | 108,781,020,181,615 |
| `BASS-M16` | BASS-II | `data/processed/canonical_experiments.csv` | 327 | 10,632,110 |
| `BASS-M17` | BASS-II | `data/processed/canonical_experiments.csv` | 328 | 10,530 |
| `BASS-M18` | BASS-II | `data/processed/canonical_experiments.csv` | 329 | 1,015,108 |
| `BASS-M19` | BASS-II | `data/processed/canonical_experiments.csv` | 330 | 1,017,141,075 |
| `BASS-M2` | BASS-II | `data/processed/canonical_experiments.csv` | 313 | 20,151,314 |
| `BASS-M3` | BASS-II | `data/processed/canonical_experiments.csv` | 314 | 102,018 |
| `BASS-M5` | BASS-II | `data/processed/canonical_experiments.csv` | 316 | 20,131,085 |
| `BASS-M6` | BASS-II | `data/processed/canonical_experiments.csv` | 317 | 10,530 |
| `BASS-M7` | BASS-II | `data/processed/canonical_experiments.csv` | 318 | 10,654.54 |
| `BASS-M8` | BASS-II | `data/processed/canonical_experiments.csv` | 319 | 10,575 |
| `BASS-M9` | BASS-II | `data/processed/canonical_experiments.csv` | 320 | 1,014 |
| `BASS-O1` | BASS-II | `data/processed/canonical_experiments.csv` | 332 | 2,010,521 |
| `BASS-O13a` | BASS-II | `data/processed/canonical_experiments.csv` | 347 | 494,442,414,140.55 |
| `BASS-O13b` | BASS-II | `data/processed/canonical_experiments.csv` | 348 | 7,449 |
| `BASS-O17` | BASS-II | `data/processed/canonical_experiments.csv` | 353 | 3,011 |
| `BASS-O18` | BASS-II | `data/processed/canonical_experiments.csv` | 354 | 5,201,121,120 |
| `BASS-O20` | BASS-II | `data/processed/canonical_experiments.csv` | 356 | 5,838.50 |
| `BASS-O3b` | BASS-II | `data/processed/canonical_experiments.csv` | 335 | 5,321 |
| `BASS-O5a` | BASS-II | `data/processed/canonical_experiments.csv` | 337 | 5,105,204,962,494,442 |
| `BASS-P10` | BASS-II | `data/processed/canonical_experiments.csv` | 368 | 4,841 |
| `BASS-P12` | BASS-II | `data/processed/canonical_experiments.csv` | 369 | 53,210.50 |
| `BASS-P14` | BASS-II | `data/processed/canonical_experiments.csv` | 372 | 4,641 |
| `BASS-P17` | BASS-II | `data/processed/canonical_experiments.csv` | 375 | 532,222 |
| `BASS-P18` | BASS-II | `data/processed/canonical_experiments.csv` | 376 | 2,020 |
| `BASS-P19` | BASS-II | `data/processed/canonical_experiments.csv` | 377 | 5,820 |
| `BASS-P20` | BASS-II | `data/processed/canonical_experiments.csv` | 378 | 2,020 |
| `BASS-P23` | BASS-II | `data/processed/canonical_experiments.csv` | 383 | 2,020 |
| `BASS-P24` | BASS-II | `data/processed/canonical_experiments.csv` | 384 | 2,020 |
| `BASS-P4` | BASS-II | `data/processed/canonical_experiments.csv` | 363 | 4,841 |
| `BASS-P6` | BASS-II | `data/processed/canonical_experiments.csv` | 365 | 4,841 |
| `BASS-P8` | BASS-II | `data/processed/canonical_experiments.csv` | 366 | 51,015 |
| `BASS-T21` | BASS-II | `data/processed/canonical_experiments.csv` | 405 | 1,147 |
| `BASS-T5` | BASS-II | `data/processed/canonical_experiments.csv` | 390 | 1,021 |
| `BASS-T6` | BASS-II | `data/processed/canonical_experiments.csv` | 391 | 5,211 |
| `BASS-T7` | BASS-II | `data/processed/canonical_experiments.csv` | 392 | 10,531 |

No repair is applied. The audit found these values originate from concatenated free-text `Fan display` / `Air display` fields and no documented rule separates them.

## Modeled rows

`is_modeled` is true for **52** rows. Rules use family and gravity descriptors, never row identifiers.

| Rule | Rows |
|:--|--:|
| `partial_g_bounded` | 50 |
| `pre_luci_fm2_reference` | 2 |

| experiment_id | Family | Gravity condition |
|:--|:--|:--|
| `FLARE-KIBO-031` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-032` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-033` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-034` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-035` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-036` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-037` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-038` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-039` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-040` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-041` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-042` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-043` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-044` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-045` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-046` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-047` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-048` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-049` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-050` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-051` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-052` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-053` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-054` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-055` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-056` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-057` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-058` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-059` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-060` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Lunar (0.16g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-061` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-062` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-063` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-064` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-065` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-066` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-067` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-068` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-069` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-070` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-071` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-072` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-073` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-074` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-075` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-076` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-077` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-078` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-079` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FLARE-KIBO-080` | Partial-g Bounded (0g+1g / E-FIELD) | Partial-g Bounded Model: Martian (0.38g — 0g PSI + 1g STD-6001) |
| `FM2-BOUND-002` | LUCI / FM2 (Future Partial-g) | Partial-g Bounded Model: Lunar (0.16g — Pre-FM2 Flight Reference) |
| `LUCI-BOUND-001` | LUCI / FM2 (Future Partial-g) | Partial-g Bounded Model: Lunar (0.16g — Pre-LUCI Flight Reference) |

## Text extraction verification

| Fact | Candidate rows | Matched rows | Verified | Unmatched values |
|:--|--:|--:|:--:|:--|
| specimen_dimensions | 19 | 17 | yes | documented exceptions: `Dimensions: Nonecm x Nonecm x Nonecm (Flow: nan)` x 2 |
| flow_direction | 19 | 17 | yes | documented exceptions: `Dimensions: Nonecm x Nonecm x Nonecm (Flow: nan)` x 2 |
| microgravity_duration | 95 | 95 | yes | — |
| pi_name | 129 | 129 | yes | — |

Patterns that did not verify cause the build to fail. Two SAFFIRE pre-test placeholder rows contain literal `Nonecm` dimensions and no numeric flow direction; they stay null and are counted as documented exceptions.

## Soft validation violations

Soft violations are flagged, never fixed. Hard structural violations fail the build.

| Flag | Rows |
|:--|--:|
| (none) | 0 |

## Input checksums

| Path | Kind | Rows | SHA-256 |
|:--|:--|--:|:--|
| `data/processed/canonical_experiments.csv` | canonical_legacy | 892 | `3e72eaf1ab70ed37511aa3f2013fe0538b54fe586b010a48a554a9b568982a51` |
| `data/raw/ACME_Extended_Research_Data.csv` | raw | 60 | `4ca4c2dd981316f0fd1c6988591568999d38578060d872df81e4704724ffb3f6` |
| `data/raw/BASS1_Initial_ISS_Data.csv` | raw | 8 | `5f032fc6a54a5c85acf940d69388662062d7a52311d1fb1713fb5b06f2709a77` |
| `data/raw/JAXA_FLARE_Kibo_Flight_Data.csv` | raw | 80 | `dbe262faef08a5e63c87c846d7919e0c5d7cd9361101a312c792b9c0ea06972c` |
| `data/raw/NASA_GRC_Drop_Tower_Quenching.csv` | raw | 95 | `ac2f0724899715ca0032f86d090c1a1f5a8f16da53b857dc2cccd6a04794d360` |
| `data/raw/NASA_MGM_Smoldering_Combustion.csv` | raw | 65 | `4983408b1e427563f30d8bdad86ec8700553163b9f462da6cb14c63f43a82049` |
| `data/raw/NASA_PSI_Complete_Suite_CFIG_SPICE_DAFT.csv` | raw | 13 | `cbdb46e1260077481ca9ca74ed311690c6b49b65c71203534c2bccbd6c5314da` |
| `data/raw/NASA_SAME_Aerosol_Detector_Data.csv` | raw | 50 | `52834ffbb686214e5e6cbcaf69ca673d15c546c562f00a992c0900ffff8792ee` |
| `data/raw/NASA_STD_6001_Extended_Materials.csv` | raw | 45 | `b2d64be130d7ae66db67ce2d8557bede088c577356bd98b2b96d56fb90786f85` |
| `data/raw/NASA_STD_6001_Materials.csv` | raw | 14 | `0819910b39814a2f511c74af94488739875128dea8299f5af7bc9fecf5bc4fba` |
| `data/raw/SLICE_Extinguishment_Data.csv` | raw | 8 | `5a5eabe21fd51a27ff71d9837bd0ab98857395f2bc532d568e90a4ac4280a4db` |
| `data/raw/SOFIE_Flight_Data.csv` | raw | 12 | `9dc02c4e3053b08e2da5066113fbe6fde82884cf2ac0e9cc974aad1117a1659d` |
| `src/flame/ingestion/mappings/modeled_rows.yaml` | mapping | 0 | `1bb791623726b2198d513ac798c75726deac6a5585814f4f0b466a9768c98cad` |
| `src/flame/ingestion/mappings/source_policy.yaml` | mapping | 0 | `c7d72a48aa4f524dce6ca85f55e5727281c5cabc2d0f314851ab8d23764c1c8f` |
| `src/flame/ingestion/mappings/vocabularies.yaml` | mapping | 0 | `c28c2ea1833277b41a3bebb974e24860a990ef3979390aad309d0a8b7cc47c4b` |

## Pending review

The following decisions need owner approval before the dataset is treated as final:

- The vocabulary mapping tables (see above). Semantic merges deliberately not applied are listed in `mappings/vocabularies.yaml` under `proposed_not_applied`.
- The airflow quarantine threshold (default 1000 cm/s).
- The burn-time plausibility maximum (default 3600 s).
- The `UNVERIFIED` items in `docs/data_dictionary.md`, especially the cross-family meaning of `burning_rate_mms` and the provenance of `he_pct` for non-FLEX families.
- Whether the 442 legacy-carried rows should ever be re-derived from their raw tables.

