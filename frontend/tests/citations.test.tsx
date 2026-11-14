import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { parseCitations } from '../src/lib/citations';
import { AnswerPanel } from '../src/components/AnswerPanel';

const known = new Set(['EXP-001', 'EXP-002']);

describe('parseCitations', () => {
  it('resolves known ids and flags unknown ones', () => {
    const s = parseCitations('see [EXP-001] and [NOPE-1].', known);
    const cites = s.filter((x) => x.kind === 'cite');
    expect(cites).toEqual([
      { kind: 'cite', id: 'EXP-001', resolved: true },
      { kind: 'cite', id: 'NOPE-1', resolved: false },
    ]);
  });
  it('handles adjacent and comma-separated citations', () => {
    const adj = parseCitations('[EXP-001][EXP-002]', known).filter((x) => x.kind === 'cite');
    expect(adj).toHaveLength(2);
    const multi = parseCitations('[EXP-001, EXP-002]', known).filter((x) => x.kind === 'cite');
    expect(multi).toHaveLength(2);
  });
  it('leaves text without brackets untouched', () => {
    expect(parseCitations('plain text', known)).toEqual([{ kind: 'text', text: 'plain text' }]);
  });
});

describe('AnswerPanel', () => {
  it('renders resolved ids as chips that call onCite', () => {
    const onCite = vi.fn();
    render(<AnswerPanel answer="Result [EXP-001]." evidenceIds={known} onCite={onCite} />);
    const chip = screen.getByRole('button', { name: /Citation EXP-001/ });
    fireEvent.click(chip);
    expect(onCite).toHaveBeenCalledWith('EXP-001');
  });
  it('renders unresolved ids as plain text with a label, never a chip', () => {
    render(<AnswerPanel answer="Result [EXP-999]." evidenceIds={known} onCite={() => {}} />);
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByText('unresolved citation')).toBeTruthy();
  });
  it('does not parse citations inside code', () => {
    const md = 'Inline `[EXP-001]` and\n\n```\n[EXP-002]\n```\n';
    render(<AnswerPanel answer={md} evidenceIds={known} onCite={() => {}} />);
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByText('[EXP-001]')).toBeTruthy();
  });
  it('renders adjacent chips', () => {
    render(<AnswerPanel answer="[EXP-001][EXP-002]" evidenceIds={known} onCite={() => {}} />);
    expect(screen.getAllByRole('button')).toHaveLength(2);
  });
  it('does not render raw HTML', () => {
    const { container } = render(<AnswerPanel answer={'<script>x</script> hi'} evidenceIds={known} onCite={() => {}} />);
    expect(container.querySelector('script')).toBeNull();
  });
});
