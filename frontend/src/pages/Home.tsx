import type { Meta } from '../types';
import { StatStrip } from './StatStrip';

const PROBLEMS = [
  {
    t: 'Fire without buoyancy',
    d: 'In microgravity hot gases do not rise. A flickering teardrop flame becomes a ghostly blue sphere that depends on diffusion for its oxygen.',
  },
  {
    t: 'More oxygen, more risk',
    d: 'Moon habitats and rovers are expected to run at 30% oxygen or more at 10.2 psi or less. That is over 40% more oxygen than Earth air, so materials burn far more easily.',
  },
  {
    t: 'Too much data to compare',
    d: 'Results from BASS, FLEX, ACME, Saffire and more are public in NASA PSI, but they are hard to find, harder to compare and harder still to interpret.',
  },
];

const STEPS = [
  { t: 'Ask', d: 'Type a question in plain English about fuels, oxygen, pressure or extinction.' },
  { t: 'Plan', d: 'An LLM turns it into a strictly validated query plan. Only whitelisted fields and operators are allowed.' },
  { t: 'Retrieve', d: 'Deterministic SQL on DuckDB returns the evidence rows. The model never invents data.' },
  { t: 'Answer and check', d: 'The answer cites its evidence. Guardrails verify citations and numbers and show what the data cannot tell you.' },
];

const TRUST = [
  { t: 'Modeled rows stay out', d: 'Partial-gravity model rows are excluded by default and labeled whenever they appear.' },
  { t: 'Bad readings quarantined', d: '42 BASS-II airflow readings above 1000 cm/s were quarantined instead of being trusted.' },
  { t: 'Every claim is cited', d: 'Citations are checked against the evidence rows before you ever see them.' },
  { t: 'Limits are shown', d: 'Each answer lists its limitations, filters and exclusions next to the evidence table.' },
];

export function Home({ meta }: { meta: Meta | null }) {
  return (
    <main className="nx-page" id="main">
      <section className="nx-hero">
        <div className="nx-rise">
          <p className="nx-eyebrow">NASA Space Apps Challenge 2026 · Flame in Freefall</p>
          <h1>
            FIRE SCIENCE.
            <br />
            <span>BEYOND GRAVITY.</span>
          </h1>
          <p className="nx-lead">
            IGNIS turns decades of NASA microgravity combustion experiments into answers you can check. Every claim
            comes with its evidence, how it was reached and what the data cannot tell you.
          </p>
          <div className="nx-actions">
            <a className="nx-btn" href="#/ask">Ask IGNIS</a>
            <a className="nx-btn ghost" href="#/dashboard">Explore the data</a>
          </div>
        </div>
        <div className="nx-orb" aria-hidden="true" />
      </section>

      <StatStrip meta={meta} />

      <section className="nx-section">
        <h2>Why fire safety in space is different</h2>
        <div className="nx-grid three">
          {PROBLEMS.map((p, i) => (
            <article className="nx-card" key={p.t} style={{ animationDelay: `${i * 90}ms` }}>
              <h3>{p.t}</h3>
              <p>{p.d}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="nx-section">
        <h2>How IGNIS works</h2>
        <div className="nx-grid four">
          {STEPS.map((s, i) => (
            <article className="nx-card step" key={s.t}>
              <span className="nx-num">{i + 1}</span>
              <h3>{s.t}</h3>
              <p>{s.d}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="nx-section">
        <h2>Why you can trust the answers</h2>
        <div className="nx-grid four">
          {TRUST.map((s) => (
            <article className="nx-card" key={s.t}>
              <h3>{s.t}</h3>
              <p>{s.d}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="nx-cta">
        <h2>Ready to interrogate the data?</h2>
        <a className="nx-btn" href="#/ask">Open the chat</a>
      </section>

      <footer className="nx-foot">
        Built for NASA Space Apps Challenge 2026 · Giza, Egypt · Data: NASA Physical Sciences Informatics
      </footer>
    </main>
  );
}