import { useId } from 'react';

interface Props {
  checked: boolean;
  modeledRows: number | null;
}

/**
 * The API request (AskRequest) accepts only `question`, so the UI cannot send an
 * "include modeled rows" flag. The control is shown but disabled, and reflects what the
 * last answer's plan actually did.
 */
export function ModeledToggle({ checked, modeledRows }: Props) {
  const id = useId();
  return (
    <div className="card toggle">
      <input id={id} type="checkbox" checked={checked} disabled readOnly aria-describedby={`${id}-d`} />
      <div>
        <label htmlFor={id} className="lbl-strong">
          Include modeled rows
        </label>
        <p id={`${id}-d`} className="k">
          Modeled rows come from partial-gravity models, not measured experiments. They are excluded by default
          {modeledRows !== null ? ` (${modeledRows} rows in the dataset)` : ''}. This option is not available yet:
          the API does not accept an include-modeled setting, so it cannot be switched from here. If the interpreted
          plan includes modeled rows, the answer is labeled and the rows are marked in the evidence table.
        </p>
      </div>
    </div>
  );
}
