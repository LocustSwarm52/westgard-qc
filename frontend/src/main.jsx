import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, getToken } from './api';
import { Audit, ControlDetail, Dashboard, Import, Login, Setup, Violations } from './pages';
import './style.css';

function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(!!getToken());
  const [page, setPage] = useState('dashboard');
  const [controlId, setControlId] = useState(null);

  const loadMe = () => api.me().then(setUser).catch(() => setUser(null)).finally(() => setChecking(false));
  useEffect(() => { if (getToken()) loadMe(); }, []);

  if (checking) return null;
  if (!user) return <Login onLogin={loadMe} />;

  const tabs = [['dashboard', 'Controls'], ['violations', 'Violations'], ['import', 'Import CSV']];
  if (user.role === 'supervisor') tabs.push(['setup', 'Setup'], ['audit', 'Audit log']);
  const go = (p) => { setPage(p); setControlId(null); };

  return (
    <>
      <header>
        <strong>Westgard QC Tracker</strong>
        <nav>{tabs.map(([key, label]) => (
          <button key={key} className={page === key ? 'active' : ''} onClick={() => go(key)}>{label}</button>
        ))}</nav>
        <span className="who">{user.name} · {user.role}
          <button className="link" onClick={() => { api.logout(); setUser(null); }}>Sign out</button></span>
      </header>
      <main>
        {page === 'dashboard' && !controlId && <Dashboard onOpen={setControlId} />}
        {page === 'dashboard' && controlId && <ControlDetail id={controlId} onBack={() => setControlId(null)} />}
        {page === 'violations' && <Violations user={user} />}
        {page === 'import' && <Import />}
        {page === 'setup' && <Setup />}
        {page === 'audit' && <Audit />}
      </main>
      <footer className="muted small">Portfolio project with made-up demo data. Not for clinical use.</footer>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
