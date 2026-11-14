import type { ApiError } from '../types';

export function Loading({ message = 'Searching the dataset…' }: { message?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <div className="spin" aria-hidden="true" />
      {message}
    </div>
  );
}

export function EmptyState() {
  return (
    <div className="card state">
      <p>
        <b>Ask a question to begin.</b>
      </p>
      <p className="k">
        Answers come from the experiment dataset and always show the evidence rows, the plan and the limitations behind
        them.
      </p>
    </div>
  );
}

export function ErrorState({ error, onRetry, title = 'Could not complete the request.' }: { error: ApiError; onRetry: () => void; title?: string }) {
  return (
    <div className="card state err b-error banner" role="alert">
      <p>
        <span aria-hidden="true" className="ico">
          ✕
        </span>{' '}
        <b>{title}</b>
      </p>
      <p>{error.message}</p>
      {error.requestId && (
        <p className="k">
          Request ID: <span className="mono">{error.requestId}</span>
        </p>
      )}
      <button type="button" className="btn alt" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
