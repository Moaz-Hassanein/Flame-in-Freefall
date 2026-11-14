/** Shows a value as reported. Missing -> "n/r" (not reported). A real 0 stays 0. */
export function Val({ v }: { v: unknown }) {
  if (v === null || v === undefined || v === '') {
    return (
      <span className="na" title="Not reported in the dataset">
        n/r
      </span>
    );
  }
  if (typeof v === 'object') return <>{JSON.stringify(v)}</>;
  return <>{String(v)}</>;
}
