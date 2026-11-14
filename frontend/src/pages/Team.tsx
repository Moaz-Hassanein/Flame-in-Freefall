const MEMBERS = [
  { name: 'Moaz Hassanein', handle: '@moazhassanein', owner: true },
  { name: 'Gehad Abdulaziz Ibrahim Abdulaziz', handle: '@gehad_abdulaziz' },
  { name: 'Mohab Kamal', handle: '@mohab_kamal' },
  { name: 'Nour Hatem Mohamed ElMahdy AbouSarea', handle: '@nourhatem' },
  { name: 'Omar Ayman', handle: '@omaraymanzaid' },
  { name: 'Moataz Mohamed Abdelrahman', handle: '@moataz2675' },
];

function initials(n: string): string {
  const p = n.split(' ').filter(Boolean);
  return ((p[0]?.[0] ?? '') + (p[1]?.[0] ?? '')).toUpperCase();
}

export function Team() {
  return (
    <main className="nx-page" id="main">
      <header className="nx-head nx-rise">
        <p className="nx-eyebrow">Local event · Giza, Egypt</p>
        <h1 className="sm">Beauty and the Beasts</h1>
        <p className="nx-lead">
          Six builders taking on the Flame in Freefall challenge: SI-powered fire safety insights from microgravity
          combustion data.
        </p>
      </header>

      <section className="nx-members">
        {MEMBERS.map((m, i) => (
          <article className="nx-card member" key={m.handle} style={{ animationDelay: `${i * 70}ms` }}>
            <div className="nx-avatar" aria-hidden="true">{initials(m.name)}</div>
            <div>
              <h3>{m.name}</h3>
              <p className="mute small">{m.handle}</p>
              {m.owner && <span className="nx-tag">Team owner</span>}
            </div>
          </article>
        ))}
      </section>

      <section className="nx-cta">
        <h2>See what we built</h2>
        <a className="nx-btn" href="#/ask">Try IGNIS</a>
      </section>
    </main>
  );
}