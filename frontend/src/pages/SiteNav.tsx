import type { Route } from './util';

const LINKS: { to: string; label: string; route: Route; cta?: boolean }[] = [
  { to: '#/', label: 'Home', route: 'home' },
  { to: '#/dashboard', label: 'Dashboard', route: 'dashboard' },
  { to: '#/team', label: 'Team', route: 'team' },
  { to: '#/ask', label: 'Ask IGNIS', route: 'ask', cta: true },
];

export function SiteNav({ route }: { route: Route }) {
  const toggleTheme = () => {
    const cur = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
    const next = cur === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem('ignis-theme', next);
    } catch {
      /* storage unavailable */
    }
  };
  return (
    <nav className="nx-nav" aria-label="Main">
      <a className="nx-brand" href="#/">
        <i aria-hidden="true" />
        IGNIS
      </a>
      <div className="nx-links">
        {LINKS.map((l) => (
          <a
            key={l.to}
            href={l.to}
            className={(route === l.route ? 'on ' : '') + (l.cta ? 'cta' : '')}
            aria-current={route === l.route ? 'page' : undefined}
          >
            {l.label}
          </a>
        ))}
        <button type="button" className="nx-theme" onClick={toggleTheme} aria-label="Toggle theme">
          ◐
        </button>
      </div>
    </nav>
  );
}