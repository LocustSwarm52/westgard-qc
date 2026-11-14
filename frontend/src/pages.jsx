import { useEffect, useState } from 'react';
import { api } from './api';
import LeveyJennings from './LeveyJennings';

const fmtTime = (t) => new Date(t).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

export function StatusBadge({ status }) {
  if (!status) return <span className="badge none">no data</span>;
  return <span className={`badge ${status}`}>{status}</span>;
}

function useLoad(fn, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const reload = () => {
    setState((s) => ({ ...s, loading: true }));
    fn().then((data) => setState({ data, error: null, loading: false }))
      .catch((e) => setState({ data: null, error: e.message, loading: false }));
  };
  useEffect(reload, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return { ...state, reload };
}

// ------------------------------------------------------------- login
export function Login({ onLogin }) {
  const [email, setEmail] = useState('supervisor@demo.lab');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const submit = async (e) => {
    e.preventDefault();
    setError('');
    try { await api.login(email, password); onLogin(); } catch (err) { setError(err.message); }
  };
  return (
    <div className="login">
      <form onSubmit={submit} className="card">
        <h1>Westgard QC Tracker</h1>
        <p className="muted">Log quality-control results and catch Westgard rule violations.</p>
        <label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></label>
        {error && <p className="error">{error}</p>}
        <button type="submit">Sign in</button>
        <p className="muted small">Demo accounts: supervisor@demo.lab or tech@demo.lab, password <code>demo1234</code></p>
      </form>
    </div>
  );
}

// ------------------------------------------------------------- dashboard
export function Dashboard({ onOpen }) {
  const { data, error, loading } = useLoad(api.controls, []);
  if (loading && !data) return <p className="muted">Loading…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!data.length) return <p className="muted">No controls yet. A supervisor can add one under Setup.</p>;
  const groups = {};
  data.forEach((c) => { (groups[`${c.instrument} · ${c.analyte}`] ||= []).push(c); });
  return (
    <>
      <h2>Controls</h2>
      <div className="grid">
        {Object.entries(groups).map(([name, controls]) => (
          <div className="card" key={name}>
            <h3>{name}</h3>
            {controls.map((c) => (
              <button className="row-button" key={c.id} onClick={() => onOpen(c.id)}>
                <span>{c.level} <span className="muted small">lot {c.lot}</span></span>
                <span>
                  {c.open_violations > 0 && <span className="pill">{c.open_violations} open</span>}
                  <StatusBadge status={c.latest_status} />
                </span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </>
  );
}

// ------------------------------------------------------------- control detail
export function ControlDetail({ id, onBack }) {
  const control = useLoad(() => api.control(id), [id]);
  const results = useLoad(() => api.results(id), [id]);
  const stats = useLoad(() => api.stats(id), [id]);
  const [value, setValue] = useState('');
  const [runId, setRunId] = useState('');
  const [message, setMessage] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setMessage(null);
    try {
      const [r] = await api.addRun({ run_id: runId || `R-${new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '')}`, values: { [id]: Number(value) } });
      const rules = r.violations.map((v) => v.rule).join(', ');
      setMessage({ kind: r.status, text: `${r.value} saved: ${r.status}${rules ? ` (${rules})` : ''}` });
      setValue('');
      results.reload(); stats.reload(); control.reload();
    } catch (err) { setMessage({ kind: 'reject', text: err.message }); }
  };

  if (!control.data || !results.data) return <p className="muted">Loading…</p>;
  const c = control.data;
  const s = stats.data;
  return (
    <>
      <button className="link" onClick={onBack}>← All controls</button>
      <h2>{c.analyte} · {c.level} <StatusBadge status={c.latest_status} /></h2>
      <p className="muted">{c.instrument} · lot {c.lot} · target {c.target_mean} ± {c.target_sd} {c.units}</p>

      <div className="card">
        <LeveyJennings results={results.data} control={c} />
        <p className="legend small">
          <span><i style={{ background: '#2f6f4f' }} />accept</span>
          <span><i style={{ background: '#c77d00' }} />warning (1-2s)</span>
          <span><i style={{ background: '#c92a2a' }} />reject</span>
          <span className="muted">Last {results.data.length} results. Hover a point for details.</span>
        </p>
      </div>

      <div className="two-col">
        <form className="card" onSubmit={submit}>
          <h3>Enter a result</h3>
          <label>Value ({c.units})<input type="number" step="any" required value={value} onChange={(e) => setValue(e.target.value)} /></label>
          <label>Run ID <span className="muted small">(optional; use the same ID for levels run together)</span>
            <input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="e.g. R041-GL" /></label>
          <button type="submit">Save and check rules</button>
          {message && <p className={`notice ${message.kind}`}>{message.text}</p>}
        </form>
        <div className="card">
          <h3>Statistics</h3>
          {s && s.n > 0 ? (
            <table className="stats"><tbody>
              <tr><td>Results</td><td>{s.n}</td></tr>
              <tr><td>Observed mean</td><td>{s.mean} {c.units}</td></tr>
              <tr><td>Observed SD</td><td>{s.sd}</td></tr>
              <tr><td>CV</td><td>{s.cv_percent}%</td></tr>
              <tr><td>Bias from target</td><td>{s.bias_percent > 0 ? '+' : ''}{s.bias_percent}%</td></tr>
            </tbody></table>
          ) : <p className="muted">No results yet.</p>}
        </div>
      </div>

      <div className="card">
        <h3>Recent results</h3>
        <table className="table">
          <thead><tr><th>Measured</th><th>Run</th><th>Value</th><th>z</th><th>Status</th><th>Rules</th></tr></thead>
          <tbody>
            {[...results.data].reverse().slice(0, 15).map((r) => (
              <tr key={r.id}>
                <td>{fmtTime(r.measured_at)}</td><td>{r.run_id}</td><td>{r.value}</td>
                <td>{r.z.toFixed(2)}</td><td><StatusBadge status={r.status} /></td>
                <td>{r.violations.map((v) => v.rule).join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ------------------------------------------------------------- violations
export function Violations({ user }) {
  const [showAll, setShowAll] = useState(false);
  const list = useLoad(() => api.violations(!showAll), [showAll]);
  const [drafts, setDrafts] = useState({});
  const [error, setError] = useState('');

  const save = async (v) => {
    setError('');
    try { await api.resolve(v.id, drafts[v.id] || ''); list.reload(); } catch (e) { setError(e.message); }
  };

  return (
    <>
      <h2>Violations</h2>
      <label className="inline"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> Show reviewed too</label>
      {error && <p className="error">{error}</p>}
      {list.data && !list.data.length && <p className="muted">No open violations.</p>}
      {list.data?.map((v) => (
        <div className="card violation" key={v.id}>
          <div className="violation-head">
            <strong>{v.rule}</strong>
            <span>{v.control_label}</span>
            <span className="muted">{fmtTime(v.measured_at)} · value {v.value} · {v.scope}</span>
          </div>
          {v.reviewed_at ? (
            <p className="small">Reviewed by {v.reviewed_by}: {v.corrective_action}</p>
          ) : (
            <div className="resolve">
              <input placeholder="Corrective action taken (e.g. recalibrated, reran controls)"
                value={drafts[v.id] || ''} onChange={(e) => setDrafts({ ...drafts, [v.id]: e.target.value })} />
              <button onClick={() => save(v)} disabled={(drafts[v.id] || '').length < 3}>Sign off</button>
            </div>
          )}
        </div>
      ))}
      {user.role !== 'supervisor' && <p className="muted small">Rejected runs need a supervisor's sign-off.</p>}
    </>
  );
}

// ------------------------------------------------------------- import
export function Import() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const submit = async (e) => {
    e.preventDefault();
    setError(''); setResult(null);
    try { setResult(await api.importCsv(file)); } catch (err) { setError(err.message); }
  };
  return (
    <>
      <h2>Import results from CSV</h2>
      <form className="card" onSubmit={submit}>
        <p>Columns: <code>control_id, value, run_id, measured_at</code>. The time is optional, in ISO format such as <code>2026-11-13T07:30:00</code>.</p>
        <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files[0])} required />
        <button type="submit" disabled={!file}>Import</button>
        {error && <p className="error">{error}</p>}
        {result && (
          <div className="notice accept">
            Imported {result.imported} results: {result.warnings} warnings, {result.rejects} rejects.
            {result.errors.length > 0 && <ul>{result.errors.map((e) => <li key={e}>{e}</li>)}</ul>}
          </div>
        )}
      </form>
    </>
  );
}

// ------------------------------------------------------------- setup (supervisor)
export function Setup() {
  const blank = { instrument: '', analyte: '', level: '', lot: '', target_mean: '', target_sd: '', units: '' };
  const [form, setForm] = useState(blank);
  const [msg, setMsg] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    try {
      const c = await api.createControl({ ...form, target_mean: Number(form.target_mean), target_sd: Number(form.target_sd) });
      setMsg({ kind: 'accept', text: `Added ${c.analyte} ${c.level} (id ${c.id}).` });
      setForm(blank);
    } catch (err) { setMsg({ kind: 'reject', text: err.message }); }
  };
  const field = (k, label, type = 'text') => (
    <label key={k}>{label}<input type={type} step="any" required={k !== 'units'} value={form[k]} onChange={set(k)} /></label>
  );
  return (
    <>
      <h2>Add a control</h2>
      <form className="card form-grid" onSubmit={submit}>
        {field('instrument', 'Instrument')}{field('analyte', 'Analyte')}{field('level', 'Level')}
        {field('lot', 'Lot number')}{field('target_mean', 'Target mean', 'number')}{field('target_sd', 'Target SD', 'number')}
        {field('units', 'Units')}
        <button type="submit">Add control</button>
        {msg && <p className={`notice ${msg.kind}`}>{msg.text}</p>}
      </form>
    </>
  );
}

// ------------------------------------------------------------- audit (supervisor)
export function Audit() {
  const { data } = useLoad(api.audit, []);
  return (
    <>
      <h2>Audit log</h2>
      <div className="card">
        <table className="table">
          <thead><tr><th>When</th><th>User</th><th>Action</th><th>Detail</th></tr></thead>
          <tbody>{data?.map((a, i) => (
            <tr key={i}><td>{fmtTime(a.at)}</td><td>{a.user}</td><td>{a.action}</td><td>{a.detail}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}
