import { describe, expect, it } from 'vitest';
import { normalizeAsk, normalizeMeta } from '../src/api/normalize';
import { ApiError } from '../src/types';
import { RAW_ASK, RAW_META } from './fixtures';

describe('normalizeAsk', () => {
  it('maps the real AskResponse shape', () => {
    const r = normalizeAsk(RAW_ASK, 'req-1');
    expect(r.request_id).toBe('req-1');
    expect(r.answer).toContain('ACME-BRE-003');
    expect(r.evidence.map((e) => e.experiment_id)).toEqual(['ACME-BRE-003', 'SLICE-005']);
    expect(r.evidence[0].flags).toEqual(['modeled', 'BURN_TIME_ZERO']);
    expect(r.plan?.filters).toEqual(['fuel_material = PMMA']);
    expect(r.exclusions).toEqual({ 'exclusions.modeled': 3 });
    expect(r.modeled_included).toBe(true); // a returned row is modeled
    expect(r.limitations).toEqual(['Only 2 rows matched.']);
  });
  it('keeps a reported 0 and a missing value distinct in the raw record', () => {
    const row = normalizeAsk(RAW_ASK).evidence[0];
    expect(row.raw.burn_time_s).toBe(0);
    expect(row.raw.extinction_diameter_mm).toBeNull();
  });
  it('accepts a null answer_markdown and every status', () => {
    for (const s of ['answered', 'insufficient_evidence', 'out_of_scope', 'clarification_needed', 'error']) {
      expect(normalizeAsk({ question: 'q', answer_markdown: null, status: s }).answer).toBe('');
    }
  });
  it('rejects an unknown status', () => {
    expect(() => normalizeAsk({ question: 'q', status: 'weird' })).toThrow(ApiError);
  });
});

describe('normalizeMeta', () => {
  it('maps version_info and modeled_rows_count', () => {
    const m = normalizeMeta(RAW_META);
    expect(m.dataset_version).toBe('4b3139dc');
    expect(m.row_count).toBe(892);
    expect(m.modeled_rows).toBe(52);
    expect(m.max_question_length).toBe(1000);
    expect(m.data_limitations).toHaveLength(1);
  });
});
