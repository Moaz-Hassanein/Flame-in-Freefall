import type { Status } from '../types';

interface Props {
  status: Status;
  limitations: string[];
  modeledIncluded: boolean;
  warnings?: string[];
}

/** Each state has an icon, a text label and its own border style, so meaning never depends on colour. */
const STATUS_UI: Record<Exclude<Status, 'answered'>, { icon: string; label: string; cls: string; hint: string }> = {
  insufficient_evidence: {
    icon: '◌',
    label: 'Insufficient evidence',
    cls: 'b-insufficient',
    hint: 'The dataset does not contain enough matching rows to answer reliably.',
  },
  out_of_scope: {
    icon: '⊘',
    label: 'Out of scope',
    cls: 'b-scope',
    hint: 'This question is outside what the experiment dataset covers.',
  },
  clarification_needed: {
    icon: '?',
    label: 'Clarification needed',
    cls: 'b-clarify',
    hint: 'Please rephrase or add detail (fuel, oxygen level, pressure, family).',
  },
  error: {
    icon: '✕',
    label: 'Error',
    cls: 'b-error',
    hint: 'The pipeline could not produce an answer.',
  },
};

export function LimitationsBanner({ status, limitations, modeledIncluded, warnings = [] }: Props) {
  const refusal = status !== 'answered' ? STATUS_UI[status] : null;
  if (!refusal && !modeledIncluded && limitations.length === 0 && warnings.length === 0) return null;
  return (
    <div className="banners">
      {refusal && (
        <section
          className={`banner ${refusal.cls}`}
          role={status === 'error' ? 'alert' : 'status'}
          aria-label={`Status: ${refusal.label}`}
          data-status={status}
        >
          <h3>
            <span aria-hidden="true" className="ico">
              {refusal.icon}
            </span>{' '}
            <span className="stamp">{refusal.label}</span>
          </h3>
          <p>{refusal.hint}</p>
        </section>
      )}
      {modeledIncluded && (
        <section className="banner b-modeled" role="note" aria-label="Modeled data included" data-testid="modeled-banner">
          <h3>
            <span aria-hidden="true" className="ico">
              ◈
            </span>{' '}
            Modeled data included
          </h3>
          <p>Some rows behind this answer come from models or estimates, not from measured experiments.</p>
        </section>
      )}
      {limitations.length > 0 && (
        <section className="banner b-limits" aria-label="Limitations and data quality" data-testid="limitations">
          <h3>
            <span aria-hidden="true" className="ico">
              ⚠
            </span>{' '}
            Limitations and data quality
          </h3>
          <ul>
            {limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </section>
      )}
      {warnings.length > 0 && (
        <section className="banner b-limits" aria-label="Warnings" data-testid="warnings">
          <h3>
            <span aria-hidden="true" className="ico">
              ⚠
            </span>{' '}
            Warnings
          </h3>
          <ul>
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
