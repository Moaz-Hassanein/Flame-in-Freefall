import type { Meta } from '../types';
import { CountUp } from './CountUp';
import { num, pick } from './util';

export function StatStrip({ meta, full }: { meta: Meta | null; full?: boolean }) {
  const rowsS = pick(meta, ['rows', 'total_rows', 'row_count', 'n_rows']);
  const modS = pick(meta, ['modeled_rows']);
  const rows = num(rowsS);
  const modeled = num(modS);
  const measured = rows !== null && modeled !== null ? rows - modeled : null;
  const version = pick(meta, ['dataset_version', 'version', 'snapshot']);
  const source = pick(meta, ['source', 'data_source']);
  return (
    <div className="nx-stats">
      <div className="nx-stat">
        <b><CountUp value={rows} /></b>
        <span>experiment records</span>
      </div>
      <div className="nx-stat">
        <b><CountUp value={measured} /></b>
        <span>measured experiments</span>
      </div>
      <div className="nx-stat red">
        <b><CountUp value={modeled} /></b>
        <span>modeled rows (excluded by default)</span>
      </div>
      {full && (
        <>
          <div className="nx-stat">
            <b className="small">{version}</b>
            <span>dataset version</span>
          </div>
          <div className="nx-stat wide">
            <b className="small">{source}</b>
            <span>data source</span>
          </div>
        </>
      )}
    </div>
  );
}