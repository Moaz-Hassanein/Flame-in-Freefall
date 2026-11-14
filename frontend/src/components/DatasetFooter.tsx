import type { ApiError, Meta } from '../types';
import { Val } from './Val';

interface Props {
  meta: Meta | null;
  error: ApiError | null;
  onRetry: () => void;
}

export function DatasetFooter({ meta, error, onRetry }: Props) {
  return (
    <footer className="foot" aria-label="Dataset information">
      {error ? (
        <div role="alert" className="b-error banner">
          <span aria-hidden="true">✕</span> Dataset information unavailable: {error.message}
          {error.requestId && (
            <>
              {' '}
              (Request ID: <span className="mono">{error.requestId}</span>)
            </>
          )}{' '}
          <button type="button" className="btn alt" onClick={onRetry}>
            Retry
          </button>
        </div>
      ) : !meta ? (
        <span className="k">Loading dataset information…</span>
      ) : (
        <dl className="foot-list">
          <div>
            <dt className="k">Dataset version</dt>
            <dd className="mono">
              <Val v={meta.dataset_version} />
            </dd>
          </div>
          <div>
            <dt className="k">Rows</dt>
            <dd className="mono">
              <Val v={meta.row_count} />
            </dd>
          </div>
          <div>
            <dt className="k">Modeled rows (excluded by default)</dt>
            <dd className="mono">
              <Val v={meta.modeled_rows} />
            </dd>
          </div>
          <div>
            <dt className="k">Source</dt>
            <dd>NASA Physical Sciences Informatics</dd>
          </div>
          {meta.data_limitations.length > 0 && (
            <div className="foot-lim">
              <dt className="k">Dataset limitations</dt>
              <dd>
                <ul className="plain k">
                  {meta.data_limitations.map((l, i) => (
                    <li key={i}>{l}</li>
                  ))}
                </ul>
              </dd>
            </div>
          )}
        </dl>
      )}
    </footer>
  );
}
