import { useEffect, useId, useRef } from 'react';
import type { EvidenceRow } from '../types';
import { Val } from './Val';

const FOCUSABLE = 'a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])';

export function DetailDrawer({ row, onClose }: { row: EvidenceRow; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>('button')?.focus();
    return () => opener?.focus?.();
  }, []);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      onClose();
      return;
    }
    if (e.key !== 'Tab') return;
    const items = Array.from(ref.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    if (items.length === 0) return;
    const firstEl = items[0];
    const lastEl = items[items.length - 1];
    if (e.shiftKey && document.activeElement === firstEl) {
      e.preventDefault();
      lastEl.focus();
    } else if (!e.shiftKey && document.activeElement === lastEl) {
      e.preventDefault();
      firstEl.focus();
    }
  };

  const safeUrl = row.source_url && /^https?:\/\//i.test(row.source_url) ? row.source_url : null;

  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={ref}
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={onKeyDown}
      >
        <div className="row between">
          <h2 id={titleId} className="mono">
            {row.experiment_id}
          </h2>
          <button type="button" className="ib" onClick={onClose} aria-label="Close details">
            ✕ Close
          </button>
        </div>

        <div className="facts">
          <div>
            <span className="k">Facility</span>
            <Val v={row.facility_hardware} />
          </div>
          <div>
            <span className="k">Family</span>
            <Val v={row.dataset_family} />
          </div>
          <div>
            <span className="k">Source</span>
            {safeUrl ? (
              <a href={safeUrl} target="_blank" rel="noopener noreferrer">
                Original source
              </a>
            ) : (
              <Val v={null} />
            )}
          </div>
        </div>

        <h3>Flags</h3>
        {row.flags.length === 0 ? (
          <p className="k">No flags on this record.</p>
        ) : (
          <p>
            {row.flags.map((f) => (
              <span key={f} className="tag flag">
                <span aria-hidden="true">⚑</span> {f}
              </span>
            ))}
          </p>
        )}

        <h3>Full record</h3>
        <dl className="record">
          {Object.entries(row.raw).map(([k, v]) => (
            <div key={k}>
              <dt className="k mono">{k}</dt>
              <dd className="mono">
                <Val v={v} />
              </dd>
            </div>
          ))}
        </dl>
        <p className="k">
          <span className="na">n/r</span> = not reported. A reported 0 stays 0.
        </p>
      </div>
    </div>
  );
}
