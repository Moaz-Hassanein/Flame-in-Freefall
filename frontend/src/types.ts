/**
 * Domain types used by the UI. The API response is converted into these in
 * src/api/normalize.ts (the ONLY place that knows raw field names).
 */
export const STATUSES = [
  'answered',
  'insufficient_evidence',
  'out_of_scope',
  'clarification_needed',
  'error',
] as const;
export type Status = (typeof STATUSES)[number];

/** AskRequest.question has maxLength 1000 in the OpenAPI schema. */
export const MAX_QUESTION_LENGTH = 1000;

export interface EvidenceRow {
  experiment_id: string;
  dataset_family: string | null;
  fuel_material: string | null;
  oxygen_pct: number | null;
  pressure_kpa: number | null;
  gravity_condition: string | null;
  extinction_outcome: string | null;
  flags: string[];
  is_modeled: boolean;
  facility_hardware: string | null;
  source_url: string | null;
  /** The full record exactly as returned (shown in the detail drawer). */
  raw: Record<string, unknown>;
}

export interface Plan {
  intent: string | null;
  filters: string[];
  group_by: string[];
  planned_aggregates: string[];
  include_modeled: boolean;
  limit: number | null;
}

export interface Citation {
  experiment_id: string;
  source_url: string | null;
  investigation_id: string | null;
  dataset_family: string | null;
}

export interface AskResult {
  /** Not part of the success body; read from the x-request-id header when present. */
  request_id: string | null;
  status: Status;
  answer: string;
  evidence: EvidenceRow[];
  citations: Citation[];
  /** Aggregate results exactly as returned. */
  aggregates: Record<string, unknown>[];
  /** Numeric exclusion counts found in aggregate results (key -> total). */
  exclusions: Record<string, number>;
  plan: Plan | null;
  limitations: string[];
  warnings: string[];
  modeled_included: boolean;
  dataset_version: string | null;
}

export interface Meta {
  dataset_version: string | null;
  row_count: number | null;
  /** Rows with is_modeled=true; the API excludes them unless the plan includes them. */
  modeled_rows: number | null;
  data_limitations: string[];
  max_question_length: number;
  /** /meta supplies no example questions; kept so the UI can use them if it ever does. */
  examples: string[];
}

export class ApiError extends Error {
  readonly requestId: string | null;
  readonly httpStatus: number;
  constructor(message: string, requestId: string | null = null, httpStatus = 0) {
    super(message);
    this.name = 'ApiError';
    this.requestId = requestId;
    this.httpStatus = httpStatus;
  }
}
