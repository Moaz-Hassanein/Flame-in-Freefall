import {
  ApiError,
  MAX_QUESTION_LENGTH,
  STATUSES,
  type AskResult,
  type Citation,
  type EvidenceRow,
  type Meta,
  type Plan,
  type Status,
} from '../types';

/**
 * Converts raw API JSON into UI types. This is the single place that knows the
 * wire field names (see docs/openapi.json: AskResponse, MetaResponse).
 */
export type Json = Record<string, unknown>;
export const isObj = (v: unknown): v is Json =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

const str = (v: unknown): string | null =>
  typeof v === 'string' ? (v === '' ? null : v) : typeof v === 'number' || typeof v === 'boolean' ? String(v) : null;
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const strList = (v: unknown): string[] =>
  Array.isArray(v) ? v.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))) : [];

export function normalizeRow(v: unknown): EvidenceRow | null {
  if (!isObj(v)) return null;
  const id = str(v.experiment_id);
  if (!id) return null;
  const isModeled = v.is_modeled === true;
  const flags = strList(v.data_quality_flags);
  if (isModeled && !flags.includes('modeled')) flags.unshift('modeled');
  return {
    experiment_id: id,
    dataset_family: str(v.dataset_family),
    fuel_material: str(v.fuel_material),
    oxygen_pct: num(v.oxygen_pct),
    pressure_kpa: num(v.pressure_kpa),
    gravity_condition: str(v.gravity_condition),
    extinction_outcome: str(v.extinction_outcome),
    flags,
    is_modeled: isModeled,
    facility_hardware: str(v.facility_hardware),
    source_url: str(v.source_url),
    raw: v,
  };
}

function normalizeCitation(v: unknown): Citation | null {
  if (!isObj(v)) return null;
  const id = str(v.experiment_id);
  if (!id) return null;
  return {
    experiment_id: id,
    source_url: str(v.source_url),
    investigation_id: str(v.investigation_id),
    dataset_family: str(v.dataset_family),
  };
}

function normalizePlan(v: unknown): Plan | null {
  if (!isObj(v)) return null;
  return {
    intent: str(v.intent),
    filters: strList(v.filters),
    group_by: strList(v.group_by),
    planned_aggregates: strList(v.aggregates),
    include_modeled: v.include_modeled === true,
    limit: num(v.limit),
  };
}

/**
 * Sums exclusion counts reported inside aggregate results: numeric values under a key that
 * contains "exclu" (e.g. `excluded_modeled: 3`), or numeric entries of an object under such a key
 * (e.g. `exclusions: { modeled: 3 }` -> `exclusions.modeled`).
 */
function collectExclusions(aggregates: Json[]): Record<string, number> {
  const out: Record<string, number> = {};
  const add = (k: string, n: number) => {
    out[k] = (out[k] ?? 0) + n;
  };
  const visit = (o: unknown): void => {
    if (Array.isArray(o)) return o.forEach(visit);
    if (!isObj(o)) return;
    for (const [k, v] of Object.entries(o)) {
      if (/exclu/i.test(k)) {
        const n = num(v);
        if (n !== null) add(k, n);
        else if (isObj(v)) for (const [sk, sv] of Object.entries(v)) {
          const sn = num(sv);
          if (sn !== null) add(`${k}.${sk}`, sn);
        }
      } else visit(v);
    }
  };
  aggregates.forEach(visit);
  return out;
}

export function normalizeAsk(json: unknown, requestId: string | null = null): AskResult {
  if (!isObj(json)) throw new ApiError('The server returned an unexpected response.', requestId);
  const status = json.status as Status;
  if (!STATUSES.includes(status)) {
    throw new ApiError(`Unknown answer status "${String(json.status)}".`, requestId);
  }
  const evidence = (Array.isArray(json.evidence) ? json.evidence : [])
    .map(normalizeRow)
    .filter((r): r is EvidenceRow => r !== null);
  const citations = (Array.isArray(json.citations) ? json.citations : [])
    .map(normalizeCitation)
    .filter((c): c is Citation => c !== null);
  const aggregates = (Array.isArray(json.aggregates) ? json.aggregates : []).filter(isObj);
  const plan = normalizePlan(json.plan);
  return {
    request_id: requestId,
    status,
    answer: str(json.answer_markdown) ?? '',
    evidence,
    citations,
    aggregates,
    exclusions: collectExclusions(aggregates),
    plan,
    limitations: strList(json.limitations),
    warnings: strList(json.warnings),
    modeled_included: plan?.include_modeled === true || evidence.some((r) => r.is_modeled),
    dataset_version: str(json.dataset_version),
  };
}

export function normalizeMeta(json: unknown): Meta {
  if (!isObj(json)) throw new ApiError('The server returned unexpected dataset information.');
  const vi = isObj(json.version_info) ? json.version_info : {};
  const sha = str(vi.parquet_sha256);
  return {
    // Same 8-character form that /ask returns as dataset_version.
    dataset_version: sha ? sha.slice(0, 8) : null,
    row_count: num(vi.total_rows),
    modeled_rows: num(json.modeled_rows_count),
    data_limitations: strList(json.data_limitations),
    max_question_length: MAX_QUESTION_LENGTH,
    examples: [],
  };
}
