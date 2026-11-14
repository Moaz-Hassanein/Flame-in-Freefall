import { useId } from 'react';

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled: boolean;
  maxLength: number;
  examples: readonly string[];
  examplesLabel: string;
}

export function QuestionInput({ value, onChange, onSubmit, disabled, maxLength, examples, examplesLabel }: Props) {
  const id = useId();
  const nearLimit = value.length >= maxLength * 0.9;
  const empty = value.trim().length === 0;
  return (
    <form
      className="card ask dossier"
      aria-label="Ask a question"
      onSubmit={(e) => {
        e.preventDefault();
        if (!disabled && !empty) onSubmit();
      }}
    >
      <label htmlFor={`${id}-q`} className="lbl-strong">
        Your question
      </label>
      <textarea
        id={`${id}-q`}
        rows={3}
        value={value}
        maxLength={maxLength}
        placeholder="Ask about a fuel, a dataset family, an experiment ID or test conditions"
        aria-describedby={`${id}-hint ${id}-count`}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            if (!disabled && !empty) onSubmit();
          }
        }}
      />
      <div className="row between">
        <span id={`${id}-hint`} className="k">
          Enter to send · Shift+Enter for a new line
        </span>
        <span id={`${id}-count`} className={`k mono ${nearLimit ? 'warn-ink' : ''}`} aria-label={`${value.length} of ${maxLength} characters`}>
          {value.length} / {maxLength}
        </span>
      </div>
      <div className="row" style={{ marginTop: 'var(--s3)' }}>
        <button type="submit" className="btn" disabled={disabled || empty}>
          {disabled ? 'Asking…' : 'Ask'}
        </button>
      </div>
      {examples.length > 0 && (
        <div className="examples" role="group" aria-label={examplesLabel}>
          <span className="tag i">{examplesLabel}</span>
          {examples.map((q) => (
            <button key={q} type="button" className="sug" onClick={() => onChange(q)} disabled={disabled}>
              {q}
            </button>
          ))}
        </div>
      )}
    </form>
  );
}
