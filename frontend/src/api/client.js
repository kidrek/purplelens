// Client HTTP unique vers le BFF (/api).
//
// PRINCIPE DE SÉCURITÉ (cahier §3, spec v2) : le client ne prend AUCUNE décision
// d'autorisation. Il envoie les cookies de session (HttpOnly, posés par /auth),
// affiche ce que le serveur renvoie, et réagit aux refus :
//   401 step_up_required  -> l'action exige une ré-authentification récente ;
//   403 forbidden         -> l'action est refusée (matrice / cloisonnement / TLP).
// Aucun jeton n'est lu ni stocké en JS (défense contre le vol de jeton via XSS).

const BASE = '/api'

export class ApiError extends Error {
  constructor(status, code, detail) {
    super(detail || code || `HTTP ${status}`)
    this.status = status
    this.code = code
    this.detail = detail
  }
}

async function request(method, path, body) {
  const opts = {
    method,
    credentials: 'include', // cookies de session HttpOnly
    headers: { 'Accept': 'application/json' },
  }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const resp = await fetch(BASE + path, opts)
  if (resp.status === 204) return null
  let data = null
  const ct = resp.headers.get('content-type') || ''
  if (ct.includes('application/json')) data = await resp.json()
  if (!resp.ok) {
    const code = data?.detail?.code || data?.detail || data?.code
    throw new ApiError(resp.status, code, data?.detail?.message || data?.detail)
  }
  return data
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b),
  put: (p, b) => request('PUT', p, b),
  del: (p) => request('DELETE', p),

  // Raccourcis métier
  whoami: () => request('GET', '/auth/whoami'),
  login: (email, password, otp) =>
    request('POST', '/auth/login', { email, password, totp: otp }),
  logout: () => request('POST', '/auth/logout'),
  stepUp: (otp) => request('POST', '/auth/step-up', { totp: otp }),
  oidcStart: () => request('GET', '/auth/oidc/start'),

  list: (entity, params = '') => request('GET', `/${entity}${params}`),
  create: (entity, payload) => request('POST', `/${entity}`, payload),
  update: (entity, id, payload) => request('PUT', `/${entity}/${id}`, payload),
  remove: (entity, id) => request('DELETE', `/${entity}/${id}`),

  journal: () => request('GET', '/journal'),
  journalVerify: () => request('GET', '/journal/verify'),
}
