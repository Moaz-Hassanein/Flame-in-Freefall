import type { Meta } from '../types';
import { StatStrip } from './StatStrip';

const INVESTIGATIONS = [
  { n: 'ACME', k: 'Gaseous flames', d: 'Six experiments on modular hardware in the Combustion Integrated Rack. CFI-G reached up to 85% oxygen.' },
  { n: 'FLEX · FLEX-2 · CFI', k: 'Burning droplets', d: 'Liquid fuel droplets in the Multi-user Droplet Combustion Apparatus. FLEX tested suppression with CO2 and helium.' },
  { n: 'BASS · BASS-II', k: 'Solid materials', d: 'Flammability of fabrics and plastics in the Microgravity Science Glovebox flow duct.' },
  { n: 'SPICE · SLICE', k: 'Smoke and structure', d: 'Smoke point and flame liftoff of gaseous fuels, run in the same glovebox flow duct.' },
  { n: 'Saffire', k: 'Spacecraft-scale fires', d: 'Spacecraft Fire Safety Demonstrations (I, II, III) on larger solid samples.' },
  { n: 'SAME · DAFT', k: 'Smoke and dust detection', d: 'Smoke and Aerosol Measurement Experiments and the dust feasibility tests that reuse the same instrument.' },
];

const ATMOS = [
  { n: 'Earth air', o2: 21, psi: '14.7 psi' },
  { n: 'Moon habitat (expected)', o2: 30, psi: '10.2 psi or less', hot: true },
  { n: 'Spacesuit', o2: 100, psi: '4.3 psi' },
];

const LIMITS = [
  'Modeled rows (is_modeled=True) come from computational extrapolations and are not measured experiments.',
  '42 BASS-II experiments had anomalous airflow readings (above 1000 cm/s) and were quarantined to NULL.',
  'burning_rate_mms is not comparable across dataset families (droplet regression, solid slab spread, foam smolder).',
  'Only NASA and JAXA microgravity combustion datasets indexed in Flame in Freefall are queried.',
];

export function Dashboard({ meta }: { meta: Meta | null }) {
  return (
    <main className="nx-page" id="main">
      <header className="nx-head nx-rise">
        <p className="nx-eyebrow">Mission data</p>
        <h1 className="sm">Dashboard</h1>
        <p className="nx-lead">What is in the dataset, and what you need to know before you trust a number.</p>
      </header>

      <StatStrip meta={meta} full />

      <section className="nx-section">
        <h2>Oxygen and pressure in context</h2>
        <div className="nx-card">
          {ATMOS.map((a) => (
            <div className="nx-bar" key={a.n}>
              <div className="nx-bar-top">
                <span>{a.n}</span>
                <span className="mute">{a.o2}% O₂ · {a.psi}</span>
              </div>
              <div className="nx-track">
                <div className={'nx-fill' + (a.hot ? ' hot' : '')} style={{ width: `${a.o2}%` }} />
              </div>
            </div>
          ))}
          <p className="mute small">
            The 30% mark is why IGNIS highlights tests at 30% oxygen or higher. Figures from the challenge brief.
          </p>
        </div>
      </section>

      <section className="nx-section">
        <h2>Investigation map</h2>
        <div className="nx-grid three">
          {INVESTIGATIONS.map((i) => (
            <article className="nx-card" key={i.n}>
              <span className="nx-tag">{i.k}</span>
              <h3>{i.n}</h3>
              <p>{i.d}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="nx-section">
        <h2>What the data cannot tell you</h2>
        <ul className="nx-list">
          {LIMITS.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </section>

      <section className="nx-cta">
        <h2>Have a specific question?</h2>
        <a className="nx-btn" href="#/ask">Ask IGNIS</a>
      </section>
    </main>
  );
}