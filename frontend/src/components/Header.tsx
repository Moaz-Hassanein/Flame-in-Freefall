import { useRef, useState } from 'react';

const reduced = () =>
  typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false;

export function Header() {
  const [theme, setTheme] = useState(document.documentElement.dataset.theme ?? 'dark');
  const stage = useRef<HTMLDivElement>(null);

  const toggle = () => {
    const t = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = t;
    try {
      localStorage.setItem('ignis-theme', t);
    } catch {
      /* storage unavailable */
    }
    setTheme(t);
  };

  const onMove = (e: React.MouseEvent) => {
    if (reduced() || !stage.current) return;
    stage.current.style.setProperty('--px', (e.clientX / window.innerWidth - 0.5).toFixed(2));
    stage.current.style.setProperty('--py', (e.clientY / window.innerHeight - 0.5).toFixed(2));
  };

  return (
    <header className="hdr" onMouseMove={onMove}>
      <div className="lnav">
        <a className="brand" href="/" aria-label="IGNIS home">
          <div className="mark" aria-hidden="true" />
          <span>IGNIS</span>
        </a>
        <button type="button" className="ib" onClick={toggle} aria-label="Toggle light or dark theme">
          ◐ Theme
        </button>
      </div>
      <div className="hero">
        <div>
          <span className="status">Mission briefing · dataset online</span>
          <h1>
            FIRE SCIENCE.
            <br />
            BEYOND GRAVITY.
          </h1>
          <p>
            Ask questions about NASA microgravity combustion experiments. Every answer shows the evidence, how it was
            reached and what it cannot tell you.
          </p>
        </div>
        <div ref={stage} className="stage" role="img" aria-label="Conceptual illustration: spherical blue flame above a planet">
          <div className="planet" />
          <div className="ring" style={{ width: '96%', height: '96%', ['--rz' as string]: '-18deg' }} />
          <div className="ring" style={{ width: '70%', height: '70%', ['--rz' as string]: '24deg' }} />
          <div className="orb">
            <i />
          </div>
          <div className="trail" style={{ top: '22%' }} />
          <div className="trail" style={{ top: '63%', animationDelay: '-3s' }} />
          <div className="flame" />
          <div className="ap">
            <svg className="astro" viewBox="0 0 120 150" aria-hidden="true">
              <g fill="#dfe8ff" stroke="#9db4e6" strokeWidth="1.5">
                <rect x="38" y="52" width="44" height="52" rx="16" />
                <rect x="30" y="58" width="14" height="46" rx="7" transform="rotate(18 37 62)" />
                <rect x="76" y="58" width="14" height="46" rx="7" transform="rotate(-30 83 62)" />
                <rect x="42" y="98" width="15" height="40" rx="7" transform="rotate(8 49 100)" />
                <rect x="63" y="98" width="15" height="40" rx="7" transform="rotate(-14 70 100)" />
                <circle cx="60" cy="34" r="22" />
              </g>
              <ellipse cx="62" cy="35" rx="15" ry="12" fill="#0B1026" stroke="#36D9FF" />
              <ellipse cx="57" cy="31" rx="5" ry="3" fill="#36D9FF" opacity=".5" />
              <rect x="48" y="66" width="24" height="10" rx="3" fill="#287BFF" opacity=".7" />
            </svg>
          </div>
        </div>
      </div>
    </header>
  );
}
