import { useEffect, useState } from 'react';
import App from './App';
import { getMeta } from './api/client';
import type { Meta } from './types';
import { Dashboard } from './pages/Dashboard';
import { Home } from './pages/Home';
import { SiteNav } from './pages/SiteNav';
import { Team } from './pages/Team';
import { ROUTES, type Route } from './pages/util';

export default function Root() {
  const [route, setRoute] = useState<Route>(() => ROUTES[window.location.hash] ?? 'home');
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    const onHash = () => {
      const r = ROUTES[window.location.hash];
      if (r) {
        setRoute(r);
        window.scrollTo(0, 0);
      }
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    const ctl = new AbortController();
    getMeta(ctl.signal)
      .then(setMeta)
      .catch(() => undefined);
    return () => ctl.abort();
  }, []);

  return (
    <>
      <SiteNav route={route} />
      {route === 'ask' ? (
        <App />
      ) : (
        <>
          <div className="nx-bg" aria-hidden="true" />
          {route === 'home' && <Home meta={meta} />}
          {route === 'dashboard' && <Dashboard meta={meta} />}
          {route === 'team' && <Team />}
        </>
      )}
    </>
  );
}