import { useEffect, useMemo, useRef, useState } from 'react';
import { sortRows, type SortDir, type SortKey } from '../lib/sort';
import type { EvidenceRow } from '../types';
import { Val } from './Val';

interface Props {
  rows: EvidenceRow[];
  highlight: { id: string; n: number } | null;
  onOpen: (row: EvidenceRow) => void;
}

const COLS: { key: SortKey; label: string }[] = [
  { key: 'experiment_id', label: 'Experiment ID' },
  { key: 'dataset_family', label: 'Family' },
  { key: 'fuel_material', label: 'Fuel' },
  { key: 'conditions', label: 'Conditions' },
  { key: 'extinction_outcome', label: 'Outcome' },
  { key: 'flags', label: 'Flags' },
];

const prefersReduced = () =>
  typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false;

export function EvidenceTable({ rows, highlight, onOpen }: Props) {
  const [key, setKey] = useState<SortKey>('experiment_id');
  const [dir, setDir] = useState<SortDir>('asc');
  const refs = useRef(new Map<string, HTMLTableRowElement>());
  const sorted = useMemo(() => sortRows(rows, key, dir), [rows, key, dir]);

  useEffect(() => {
    if (!highlight) return;
    const el = refs.current.get(highlight.id);
    if (!el) return;
    el.scrollIntoView({ block: 'center', behavior: prefersReduced() ? 'auto' : 'smooth' });
    el.focus({ preventScroll: true });
  }, [highlight]);

  const toggle = (k: SortKey) => {
    if (k === key) setDir(dir === 'asc' ? 'desc' : 'asc');
    else {
      setKey(k);
      setDir('asc');
    }
  };

  return (
    <section className="card" aria-labelledby="ev-h">
      <div className="row between">
        <h2 id="ev-h">Evidence</h2>
        <span className="tag d">{rows.length} row{rows.length === 1 ? '' : 's'}</span>
      </div>
      {rows.length === 0 ? (
        <p className="state">No evidence rows were returned for this answer.</p>
      ) : (
        <div className="wrap" tabIndex={0} role="region" aria-label="Evidence table, scrollable">
          <table>
            <caption className="sr">Evidence rows behind the answer. Activate a column header to sort.</caption>
            <thead>
              <tr>
                {COLS.map((c) => (
                  <th
                    key={c.key}
                    scope="col"
                    aria-sort={c.key === key ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                  >
                    <button type="button" className="th-btn" onClick={() => toggle(c.key)}>
                      {c.label}
                      <span aria-hidden="true">{c.key === key ? (dir === 'asc' ? ' ▲' : ' ▼') : ' ↕'}</span>
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => {
                const hl = highlight?.id === r.experiment_id;
                return (
                  <tr
                    key={r.experiment_id}
                    ref={(el) => {
                      if (el) refs.current.set(r.experiment_id, el);
                      else refs.current.delete(r.experiment_id);
                    }}
                    tabIndex={-1}
                    data-eid={r.experiment_id}
                    className={hl ? 'hl' : undefined}
                    aria-current={hl ? 'true' : undefined}
                  >
                    <td>
                      <button type="button" className="link-btn mono" onClick={() => onOpen(r)} aria-label={`Open details for ${r.experiment_id}`}>
                        {r.experiment_id}
                      </button>
                    </td>
                    <td><Val v={r.dataset_family} /></td>
                    <td><Val v={r.fuel_material} /></td>
                    <td>
                      O₂ <Val v={r.oxygen_pct} />% · <Val v={r.pressure_kpa} /> kPa · <Val v={r.gravity_condition} />
                    </td>
                    <td><Val v={r.extinction_outcome} /></td>
                    <td>
                      {r.flags.length === 0 ? (
                        <span className="k">none</span>
                      ) : (
                        r.flags.map((f) => (
                          <span key={f} className="tag flag">
                            <span aria-hidden="true">⚑</span> {f}
                          </span>
                        ))
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
