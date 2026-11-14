import { useMemo } from 'react';
import ReactMarkdown, { type Components, type Options } from 'react-markdown';
import { remarkCitations } from '../lib/citations';

interface Props {
  answer: string;
  evidenceIds: ReadonlySet<string>;
  onCite: (id: string) => void;
}

interface ChipProps {
  cid?: string;
  ok?: string;
}

export function AnswerPanel({ answer, evidenceIds, onCite }: Props) {
  const plugins = useMemo<NonNullable<Options['remarkPlugins']>>(
    () => [remarkCitations(evidenceIds)] as unknown as NonNullable<Options['remarkPlugins']>,
    [evidenceIds],
  );
  const components = useMemo(
    () =>
      ({
        'cite-chip': ({ cid = '', ok }: ChipProps) =>
          ok === 'true' ? (
            <button
              type="button"
              className="chip cite"
              onClick={() => onCite(cid)}
              aria-label={`Citation ${cid}: go to evidence row`}
            >
              {cid}
            </button>
          ) : (
            <span className="unresolved" title="This citation does not match any evidence row">
              [{cid}] <span className="unres-label">unresolved citation</span>
            </span>
          ),
      }) as unknown as Components,
    [onCite],
  );

  return (
    <section className="card answer" aria-labelledby="answer-h">
      <h2 id="answer-h">Answer</h2>
      {answer ? (
        <div className="md">
          <ReactMarkdown skipHtml remarkPlugins={plugins} components={components}>
            {answer}
          </ReactMarkdown>
        </div>
      ) : (
        <p className="k">No answer text was returned.</p>
      )}
    </section>
  );
}
