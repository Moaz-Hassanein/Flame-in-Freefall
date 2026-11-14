import type { Plan } from '../types';
import { Val } from './Val';

interface Props {
  plan: Plan | null;
  /** Evidence rows returned with the answer (capped by the API). */
  evidenceCount: number;
  exclusions: Record<string, number>;
  aggregateCount: number;
}

function List({ items }: { items: string[] }) {
  if (items.length === 0) return <span className="k">None</span>;
  return (
    <ul className="plain">
      {items.map((x, i) => (
        <li key={i} className="mono">
          {x}
        </li>
      ))}
    </ul>
  );
}

export function PlanPanel({ plan, evidenceCount, exclusions, aggregateCount }: Props) {
  const exclEntries = Object.entries(exclusions);
  return (
    <section className="card plan" aria-labelledby="plan-h">
      <h2 id="plan-h">How this was answered</h2>
      {!plan ? (
        <p className="k">No interpretation plan was returned for this answer.</p>
      ) : (
        <dl className="facts">
          <div>
            <dt className="k">Interpreted as</dt>
            <dd className="mono">
              <Val v={plan.intent} />
            </dd>
          </div>
          <div>
            <dt className="k">Filters applied</dt>
            <dd>
              <List items={plan.filters} />
            </dd>
          </div>
          <div>
            <dt className="k">Grouped by</dt>
            <dd>
              <List items={plan.group_by} />
            </dd>
          </div>
          <div>
            <dt className="k">Aggregates</dt>
            <dd>
              <List items={plan.planned_aggregates} />
              <span className="k">
                {aggregateCount} aggregate result{aggregateCount === 1 ? '' : 's'} computed
              </span>
            </dd>
          </div>
          <div>
            <dt className="k">Modeled rows</dt>
            <dd>{plan.include_modeled ? '◈ Included' : 'Excluded'}</dd>
          </div>
          <div>
            <dt className="k">Evidence rows returned</dt>
            <dd className="mono">
              {evidenceCount}
              {plan.limit !== null && <span className="k"> (limit {plan.limit})</span>}
            </dd>
          </div>
          <div>
            <dt className="k">Rows excluded</dt>
            <dd className="mono">
              {exclEntries.length === 0 ? (
                <Val v={null} />
              ) : (
                <ul className="plain">
                  {exclEntries.map(([k, n]) => (
                    <li key={k}>
                      {k}: <span className="mono">{n}</span>
                    </li>
                  ))}
                </ul>
              )}
            </dd>
          </div>
        </dl>
      )}
    </section>
  );
}
