// Test-only fixtures. Nothing in src/ imports this file.
// Shapes follow docs/openapi.json (AskResponse, MetaResponse).
import type { EvidenceRow, Plan } from '../src/types';

export const RAW_ROW_A = {
  experiment_id: 'ACME-BRE-003',
  dataset_family: 'ACME-BRE',
  fuel_material: 'PMMA (Acrylic)',
  oxygen_pct: 30,
  pressure_kpa: 70.3,
  gravity_condition: 'Microgravity (~0g)',
  extinction_outcome: 'Self-Extinction',
  burn_time_s: 0,
  extinction_diameter_mm: null,
  data_quality_flags: ['BURN_TIME_ZERO'],
  is_modeled: true,
  facility_hardware: 'Rig-1',
  source_url: 'https://example.org/psi/acme-bre-003',
};
export const RAW_ROW_B = {
  experiment_id: 'SLICE-005',
  dataset_family: 'SLICE',
  fuel_material: 'Heptane',
  oxygen_pct: 21,
  data_quality_flags: [],
  is_modeled: false,
};

export const ROW_A: EvidenceRow = {
  experiment_id: 'ACME-BRE-003',
  dataset_family: 'ACME-BRE',
  fuel_material: 'PMMA (Acrylic)',
  oxygen_pct: 30,
  pressure_kpa: 70.3,
  gravity_condition: 'Microgravity (~0g)',
  extinction_outcome: 'Self-Extinction',
  flags: ['modeled', 'BURN_TIME_ZERO'],
  is_modeled: true,
  facility_hardware: 'Rig-1',
  source_url: 'https://example.org/psi/acme-bre-003',
  raw: RAW_ROW_A,
};

export const PLAN: Plan = {
  intent: 'lookup',
  filters: ['fuel_material = PMMA'],
  group_by: ['extinction_outcome'],
  planned_aggregates: ['count(experiment_id)'],
  include_modeled: false,
  limit: 100,
};

export const RAW_PLAN = {
  intent: 'lookup',
  filters: ['fuel_material = PMMA'],
  group_by: ['extinction_outcome'],
  aggregates: ['count(experiment_id)'],
  select_fields: [],
  sort: [],
  limit: 100,
  include_modeled: false,
  experiment_ids: null,
  allow_cross_family_aggregate: false,
};

export const RAW_META = {
  version_info: { parquet_sha256: '4b3139dc07546aa01ab89b3a0b02411a25c02be681275b9619bda57aba7b33cf', total_rows: 892 },
  field_catalog: { fields: {} },
  dataset_families: ['ACME-BRE', 'SLICE'],
  modeled_rows_count: 52,
  data_limitations: ['Modeled rows are not measured experiments.'],
};

export const RAW_ASK = {
  question: 'What about PMMA?',
  answer_markdown: 'PMMA self-extinguished [ACME-BRE-003] but [NOPE-999] is missing.',
  citations: [{ experiment_id: 'ACME-BRE-003', source_url: null, investigation_id: null, dataset_family: 'ACME-BRE' }],
  evidence: [RAW_ROW_A, RAW_ROW_B],
  aggregates: [{ name: 'count', value: 2, exclusions: { modeled: 3 } }],
  plan: RAW_PLAN,
  limitations: ['Only 2 rows matched.'],
  warnings: [],
  status: 'answered',
  dataset_version: '4b3139dc',
  timings: { plan_s: 0.1, total_s: 0.2 },
};
