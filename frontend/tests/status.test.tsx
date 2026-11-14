import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LimitationsBanner } from '../src/components/LimitationsBanner';
import { STATUSES, type Status } from '../src/types';

const LABELS: Record<Exclude<Status, 'answered'>, string> = {
  insufficient_evidence: 'Insufficient evidence',
  out_of_scope: 'Out of scope',
  clarification_needed: 'Clarification needed',
  error: 'Error',
};

describe('LimitationsBanner', () => {
  for (const s of STATUSES.filter((x) => x !== 'answered')) {
    it(`renders a labeled banner for ${s}`, () => {
      render(<LimitationsBanner status={s} limitations={[]} modeledIncluded={false} />);
      expect(screen.getByText(LABELS[s as Exclude<Status, 'answered'>])).toBeTruthy();
      expect(document.querySelector(`[data-status="${s}"]`)).toBeTruthy();
    });
  }
  it('uses a distinct border class per status', () => {
    const classes = new Set<string>();
    for (const s of STATUSES.filter((x) => x !== 'answered')) {
      const { container, unmount } = render(<LimitationsBanner status={s} limitations={[]} modeledIncluded={false} />);
      classes.add(container.querySelector(`[data-status="${s}"]`)?.className ?? '');
      unmount();
    }
    expect(classes.size).toBe(4);
  });
  it('error uses role=alert', () => {
    render(<LimitationsBanner status="error" limitations={[]} modeledIncluded={false} />);
    expect(screen.getByRole('alert')).toBeTruthy();
  });
  it('always shows limitations when present', () => {
    render(<LimitationsBanner status="answered" limitations={['Small sample.', 'Mixed units.']} modeledIncluded={false} />);
    expect(screen.getByText('Small sample.')).toBeTruthy();
    expect(screen.getByText('Mixed units.')).toBeTruthy();
  });
  it('shows the modeled-data treatment when modeled rows are included', () => {
    render(<LimitationsBanner status="answered" limitations={[]} modeledIncluded />);
    expect(screen.getByTestId('modeled-banner')).toBeTruthy();
  });
  it('renders nothing for a clean answered result', () => {
    const { container } = render(<LimitationsBanner status="answered" limitations={[]} modeledIncluded={false} />);
    expect(container.firstChild).toBeNull();
  });
});
