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

// Rafraîchissement silencieux « single-flight » et sûr multi-onglets.
//
// L'access token (cookie pc_access) expire en 10 min ; le backend sait le
// renouveler jusqu'à 14 j via POST /auth/refresh, mais ce refresh doit être
// SÉRIALISÉ : la rotation brûle toute la famille de tokens en cas de rejeu
// (deux appels concurrents présentant le même cookie). navigator.locks garantit
// qu'un seul refresh court à la fois à l'échelle du navigateur (les cookies
// Set-Cookie sont partagés entre onglets), avec repli sur une promesse partagée
// en module si l'API Web Locks est absente. Ne throw jamais : renvoie true/false.
let refreshInflight = null

async function rawRefresh() {
  try {
    const resp = await fetch(BASE + '/auth/refresh', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Accept': 'application/json' },
    })
    return resp.ok
  } catch {
    return false
  }
}

async function ensureFreshToken() {
  if (typeof navigator !== 'undefined' && navigator.locks?.request) {
    return navigator.locks.request('pc-token-refresh', rawRefresh)
  }
  // Repli : coalescer les appels concurrents dans le même onglet.
  if (!refreshInflight) {
    refreshInflight = rawRefresh().finally(() => { refreshInflight = null })
  }
  return refreshInflight
}

// Codes de refus qui ne doivent PAS déclencher de refresh silencieux :
//  - step_up_required : flux MFA inline (le composant appelant gère le TOTP) ;
//  - account_inactive : compte désactivé, la session ne doit pas repartir.
// Chemins exclus pour éviter toute boucle de rejeu.
const _noRetryPaths = ['/auth/refresh', '/auth/login', '/auth/logout']

async function request(method, path, body, _retry = true) {
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
    // Access token expiré/absent (401 unauthenticated) : rafraîchir en silence
    // puis rejouer UNE seule fois. Transparent pour l'utilisateur actif ; si le
    // refresh échoue (session réellement morte), le 401 d'origine remonte et le
    // routeur redirige vers /login (comportement inchangé).
    if (
      resp.status === 401 &&
      code === 'unauthenticated' &&
      _retry &&
      !_noRetryPaths.includes(path)
    ) {
      const refreshed = await ensureFreshToken()
      if (refreshed) return request(method, path, body, false)
    }
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
  // Rotation du refresh token → nouvel access token portant le client_scope à jour
  // (relu en base). Sert à refléter un scope élargi sans imposer une reconnexion.
  refresh: () => request('POST', '/auth/refresh'),
  stepUp: (otp) => request('POST', '/auth/step-up', { totp: otp }),
  oidcStart: () => request('GET', '/auth/oidc/start'),

  list: (entity, params = '') => request('GET', `/${entity}${params}`),
  create: (entity, payload) => request('POST', `/${entity}`, payload),
  update: (entity, id, payload) => request('PUT', `/${entity}/${id}`, payload),
  remove: (entity, id) => request('DELETE', `/${entity}/${id}`),

  journal: () => request('GET', '/journal'),
  journalVerify: () => request('GET', '/journal/verify'),

  // Profil self-service « Ma fiche » : fiche ressource (type humaine) liée au compte,
  // qui rend l'utilisateur sélectionnable comme auditeur d'un audit de son périmètre.
  myResources: () => request('GET', '/profile/resources'),
  saveMyResource: (body) => request('PUT', '/profile/resource', body),

  // Initialisation d'une preuve → renvoie une URL présignée d'upload (PresignedUpload).
  // Le binaire ne transite pas par l'API : le caller fait un PUT direct vers MinIO,
  // puis appelle /evidence/{id}/ingest pour déclencher le sas (cahier §6quater).
  initEvidence: (payload) => request('POST', '/evidence', payload),
}
