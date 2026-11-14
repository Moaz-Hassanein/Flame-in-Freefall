import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PlanPanel } from '../src/components/PlanPanel';
import { PLAN } from './fixtures';

const base = { plan: PLAN, evidenceCount: 10, exclusions: { 'exclusions.modeled': 2 }, aggregateCount: 1 };

describe('PlanPanel', () => {
  it('shows filters, aggregates, modeled flag, row counts and exclusions', () => {
    render(<PlanPanel {...base} />);
    expect(screen.getByText('How this was answered')).toBeTruthy();
    expect(screen.getByText('fuel_material = PMMA')).toBeTruthy();
    expect(screen.getByText('count(experiment_id)')).toBeTruthy();
    expect(screen.getByText('Excluded')).toBeTruthy();
    expect(screen.getByText(/limit 100/)).toBeTruthy();
    expect(screen.getByText(/exclusions\.modeled:/)).toBeTruthy();
  });
  it('shows when modeled rows were included', () => {
    render(<PlanPanel {...base} plan={{ ...PLAN, include_modeled: true }} />);
    expect(screen.getByText(/Included/)).toBeTruthy();
  });
  it('keeps a reported 0 and marks missing exclusion counts n/r', () => {
    render(<PlanPanel {...base} evidenceCount={0} exclusions={{}} />);
    expect(screen.getByText(/^0/)).toBeTruthy();
    expect(screen.getAllByText('n/r').length).toBeGreaterThan(0);
  });
  it('handles a missing plan', () => {
    render(<PlanPanel {...base} plan={null} />);
    expect(screen.getByText(/No interpretation plan/)).toBeTruthy();
  });
});
