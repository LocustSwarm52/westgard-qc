// Small wrapper around fetch that adds the login token and turns
// error responses into readable messages.

const TOKEN_KEY = 'qc_token';

export const getToken = () => {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
};
const setToken = (t) => {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
};

async function request(path, { method = 'GET', body, form, file } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = new URLSearchParams(form);
  } else if (file) {
    payload = new FormData();
    payload.append('file', file);
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const res = await fetch(`/api${path}`, { method, headers, body: payload });
  if (res.status === 401 && path !== '/auth/login') {
    setToken(null);
    window.location.reload();
  }
  const data = res.headers.get('content-type')?.includes('json') ? await res.json() : null;
  if (!res.ok) {
    const detail = data?.detail;
    const msg = Array.isArray(detail) ? detail.map((d) => `${d.loc?.at(-1)}: ${d.msg}`).join('; ') : detail;
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  async login(email, password) {
    const { access_token } = await request('/auth/login', { method: 'POST', form: { username: email, password } });
    setToken(access_token);
  },
  logout: () => setToken(null),
  me: () => request('/me'),
  controls: () => request('/controls'),
  control: (id) => request(`/controls/${id}`),
  createControl: (body) => request('/controls', { method: 'POST', body }),
  results: (id, limit = 60) => request(`/controls/${id}/results?limit=${limit}`),
  stats: (id) => request(`/controls/${id}/stats`),
  addRun: (body) => request('/runs', { method: 'POST', body }),
  importCsv: (file) => request('/import', { method: 'POST', file }),
  violations: (openOnly = true) => request(`/violations?open_only=${openOnly}`),
  resolve: (id, corrective_action) => request(`/violations/${id}`, { method: 'PATCH', body: { corrective_action } }),
  audit: () => request('/audit'),
};
