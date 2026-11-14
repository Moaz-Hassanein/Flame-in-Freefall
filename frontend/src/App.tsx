import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ask, getMeta } from './api/client';
import { AnswerPanel } from './components/AnswerPanel';
import { DatasetFooter } from './components/DatasetFooter';
import { DetailDrawer } from './components/DetailDrawer';
import { EvidenceTable } from './components/EvidenceTable';
import { LimitationsBanner } from './components/LimitationsBanner';
import { ModeledToggle } from './components/ModeledToggle';
import { PlanPanel } from './components/PlanPanel';
import { QuestionInput } from './components/QuestionInput';
import { EmptyState, ErrorState, Loading } from './components/States';
import { EXAMPLE_QUESTIONS } from './lib/examples';
import { ApiError, MAX_QUESTION_LENGTH, type AskResult, type EvidenceRow, type Meta } from './types';

type Phase = 'idle' | 'loading' | 'done' | 'error';
interface HistoryItem {
  question: string;
  result: AskResult;
}

const MAX_HISTORY = 5;

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState<ApiError | null>(null);
  const [question, setQuestion] = useState('');
  const [phase, setPhase] = useState<Phase>('idle');
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [highlight, setHighlight] = useState<{ id: string; n: number } | null>(null);
  const [open, setOpen] = useState<EvidenceRow | null>(null);
  const last = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const [metaTry, setMetaTry] = useState(0);
  const loadMeta = useCallback(() => setMetaTry((n) => n + 1), []);

  useEffect(() => {
    const ctl = new AbortController();
    getMeta(ctl.signal)
      .then((m) => {
        setMeta(m);
        setMetaError(null);
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === 'AbortError') return;
        setMetaError(e instanceof ApiError ? e : new ApiError(String(e)));
      });
    return () => ctl.abort();
  }, [metaTry]);

  useEffect(() => () => abort.current?.abort(), []);

  useEffect(() => {
    if (!highlight) return;
    const t = window.setTimeout(() => setHighlight(null), 4000);
    return () => window.clearTimeout(t);
  }, [highlight]);

  const run = useCallback(async (q: string) => {
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    last.current = q;
    setPhase('loading');
    setError(null);
    setHighlight(null);
    setOpen(null);
    try {
      const r = await ask(q, ctl.signal);
      setResult(r);
      setPhase('done');
      setHistory((h) => [{ question: q, result: r }, ...h].slice(0, MAX_HISTORY));
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      setError(e instanceof ApiError ? e : new ApiError(String(e)));
      setPhase('error');
    }
  }, []);

  const maxLen = meta?.max_question_length ?? MAX_QUESTION_LENGTH;
  const submit = () => {
    const q = question.trim();
    if (q && q.length <= maxLen) void run(q);
  };

  const evidenceIds = useMemo(() => new Set(result?.evidence.map((r) => r.experiment_id) ?? []), [result]);
  const onCite = useCallback((id: string) => setHighlight({ id, n: Date.now() }), []);

  const examples = meta && meta.examples.length > 0 ? meta.examples : EXAMPLE_QUESTIONS;
  const examplesLabel = meta && meta.examples.length > 0 ? 'Suggested' : 'Example';

  const restore = (h: HistoryItem) => {
    setQuestion(h.question);
    setResult(h.result);
    setPhase('done');
    setError(null);
    setHighlight(null);
  };

  return (
    <>
      <div className="space" aria-hidden="true">
        <div className="stars" />
        <div className="stars b" />
        <div className="dust" />
        <div className="moonbg" />
        <div className="horizon" />
      </div>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <main id="main" className="main">
        <QuestionInput
          value={question}
          onChange={setQuestion}
          onSubmit={submit}
          disabled={phase === 'loading'}
          maxLength={maxLen}
          examples={examples}
          examplesLabel={examplesLabel}
        />
        <ModeledToggle
          checked={phase === 'done' && result?.plan?.include_modeled === true}
          modeledRows={meta?.modeled_rows ?? null}
        />

        <div className="results" aria-live="polite" aria-busy={phase === 'loading'}>
          {phase === 'idle' && <EmptyState />}
          {phase === 'loading' && <Loading />}
          {phase === 'error' && error && (
            <ErrorState
              error={error}
              onRetry={() => last.current && void run(last.current)}
            />
          )}
          {phase === 'done' && result && (
            <>
              <LimitationsBanner
                status={result.status}
                limitations={result.limitations}
                modeledIncluded={result.modeled_included}
                warnings={result.warnings}
              />
              {(result.status === 'answered' || result.answer) && (
                <AnswerPanel answer={result.answer} evidenceIds={evidenceIds} onCite={onCite} />
              )}
              <PlanPanel
                plan={result.plan}
                evidenceCount={result.evidence.length}
                exclusions={result.exclusions}
                aggregateCount={result.aggregates.length}
              />
              <EvidenceTable rows={result.evidence} highlight={highlight} onOpen={setOpen} />
              {result.request_id && (
                <p className="k">
                  Request ID: <span className="mono">{result.request_id}</span>
                </p>
              )}
            </>
          )}
        </div>

        {history.length > 0 && (
          <nav className="card" aria-label="Session history">
            <h2>This session</h2>
            <ul className="plain hist">
              {history.map((h, i) => (
                <li key={`${i}-${h.question}`}>
                  <button type="button" className="sug" onClick={() => restore(h)}>
                    {h.question} <span className="tag mono">{h.result.status}</span>
                  </button>
                </li>
              ))}
            </ul>
            <p className="k">Kept in memory only. Cleared when you reload.</p>
          </nav>
        )}
      </main>
      <DatasetFooter meta={meta} error={metaError} onRetry={loadMeta} />
      {open && <DetailDrawer row={open} onClose={() => setOpen(null)} />}
    </>
  );
}
