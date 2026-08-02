<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import DetailDrawer from './DetailDrawer.vue'
import EntityForm from './EntityForm.vue'
import ExoStepsDrawer from './ExoStepsDrawer.vue'
import { api } from '../api/client'
import { ENTITY_FIELDS } from '../fields'
import { STATUT_EXO_TONE, TLP_TONE, VERDICT_TONE } from '../tones'

// Tiroir de lecture d'un exercice Purple. En-tête = KPI + périmètre (client,
// applications auditées via l'audit, audit rattaché, identité auto-générée). Corps =
// tableau de bord groupé de TOUS les RUNs de l'audit (posture, timeline d'étapes avec
// verdicts/observations, remédiation, couverture par tactique MITRE) — porté depuis
// l'ancienne page Exercices, en lecture seule. L'édition reste sur /exercices/:id.
// `readonly` : rendu en panneau compagnon (cf. composables/useDrawerPair.js) — surface de
// consultation seule. Les commandes d'édition disparaissent et les liens sortants
// remplacent le compagnon en place via `open-entity` au lieu de naviguer.
const props = defineProps({
  record: { type: Object, required: true },
  readonly: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'open-entity'])
const { locale } = useI18n()

const DICT = {
  fr: {
    subtitle: 'Exercice Purple · lecture seule', perimetre: 'Périmètre', runsOf: 'RUNs de cet audit',
    runCourant: 'RUN courant', statut: 'Statut', date: 'Date', client: 'Client',
    apps: 'Applications auditées', audit: 'Audit rattaché', nom: 'Nom métier',
    period: 'Période', seq: 'Séquence', equipe: 'Équipe', creation: 'Création', notes: 'Notes',
    run: 'Run', runs: 'run(s)', legDet: 'Détectée', legPart: 'Partielle', legGap: 'Angle mort',
    cov: 'Couv.', exec: 'joué', detN: 'détectés', prev: 'prévenu', logged: 'journalisé',
    gapsSg: 'angle mort', gapsPl: 'angles morts', mttrResp: 'MTTR réponse', mttrRem: 'MTTR remédiation',
    posture: 'Décomposition de la posture', testedN: 'étapes testées',
    pPrev: 'Prévention', pAlert: 'Alerting', pLog: 'Journalisé', pBlind: 'Angle mort',
    tacKpi: 'Couverture par tactique MITRE', killchain: 'ordre kill-chain',
    covered: 'couverte', gap: 'angle mort', partial: 'partielle', noTac: 'Non mappée',
    remLabel: 'Purple — Remédiation', noSteps: 'Aucune étape testée sur ce RUN.',
    verdicts: { prevented: 'Prévenu', alerted: 'Alerté', logged: 'Journalisé (non alerté)', no_telemetry: 'Aucune télémétrie', not_tested: 'Non testé' },
    deltaUnit: 'pts', loading: 'Chargement…', edit: 'Modifier',
    cockpitEyebrow: 'Posture de détection · RUN courant', coverage: 'Couverture', detectedFoot: 'détectées',
    vsRun: 'vs RUN', blind: 'Angles morts', played: 'Étapes jouées', trendNote: 'couverture par RUN',
    runMetrics: 'Métriques défensives', noRun: 'Aucun RUN mesurable sur cet audit.', show: 'Voir', hide: 'Masquer',
    editRun: 'Éditer le RUN', editSteps: 'Éditer les étapes', editRunT: 'Modifier les méta de ce RUN', editStepsT: 'Modifier les étapes de ce RUN',
  },
  en: {
    subtitle: 'Purple exercise · read-only', perimetre: 'Perimeter', runsOf: 'RUNs of this audit',
    runCourant: 'Current RUN', statut: 'Status', date: 'Date', client: 'Client',
    apps: 'Audited applications', audit: 'Linked audit', nom: 'Business name',
    period: 'Period', seq: 'Sequence', equipe: 'Team', creation: 'Created', notes: 'Notes',
    run: 'Run', runs: 'run(s)', legDet: 'Detected', legPart: 'Partial', legGap: 'Blind spot',
    cov: 'Cov.', exec: 'played', detN: 'detected', prev: 'prevented', logged: 'logged',
    gapsSg: 'blind spot', gapsPl: 'blind spots', mttrResp: 'MTTR response', mttrRem: 'MTTR remediation',
    posture: 'Posture breakdown', testedN: 'tested steps',
    pPrev: 'Prevention', pAlert: 'Alerting', pLog: 'Logged', pBlind: 'Blind spot',
    tacKpi: 'Coverage by MITRE tactic', killchain: 'kill-chain order',
    covered: 'covered', gap: 'blind spot', partial: 'partial', noTac: 'Unmapped',
    remLabel: 'Purple — Remediation', noSteps: 'No tested step on this RUN.',
    verdicts: { prevented: 'Prevented', alerted: 'Alerted', logged: 'Logged (not alerted)', no_telemetry: 'No telemetry', not_tested: 'Not tested' },
    deltaUnit: 'pts', loading: 'Loading…', edit: 'Edit',
    cockpitEyebrow: 'Detection posture · current RUN', coverage: 'Coverage', detectedFoot: 'detected',
    vsRun: 'vs RUN', blind: 'Blind spots', played: 'Steps played', trendNote: 'coverage per RUN',
    runMetrics: 'Defensive metrics', noRun: 'No measurable RUN on this audit.', show: 'Show', hide: 'Hide',
    editRun: 'Edit the RUN', editSteps: 'Edit the steps', editRunT: 'Edit this RUN’s metadata', editStepsT: 'Edit this RUN’s steps',
  },
}
const L = computed(() => DICT[locale.value === 'en' ? 'en' : 'fr'])
const tr = (k) => L.value[k] ?? k

// ── Verdicts / états (miroir de la spec §2) ──────────────────────────────────
// VERDICT_TONE vient de tones.js (source unique partagée avec /exercices/:id).
function verdictLabel(v) { return L.value.verdicts[v] || v }
const TICKET_DONE = 'clos'
function stepState(step, ticket) {
  const v = step.verdict
  if (v === 'not_tested') return 'untested'
  if (v === 'prevented') return 'prevented'
  if (v === 'alerted') return 'alerted'
  if (v === 'logged') return (ticket && ticket.statut === TICKET_DONE) ? 'covered' : 'logged'
  return (ticket && ticket.statut === TICKET_DONE) ? 'covered' : 'gap'
}
function stvClass(state) {
  return { prevented: 'stv-prev', alerted: 'stv-det', detected: 'stv-det', logged: 'stv-part', covered: 'stv-cov', gap: 'stv-gap', untested: 'stv-untested' }[state] || 'stv-gap'
}
function ticketStatutTone(s) { return { ouvert: 'red', en_cours: 'amber', traite: 'blue', clos: 'green' }[s] || 'gray' }
function prioTone(p) { return { P1: 'red', P2: 'amber', P3: 'blue', P4: 'gray', critique: 'red', haute: 'amber', moyenne: 'blue', basse: 'gray' }[p] || 'gray' }

// ── Format temps ─────────────────────────────────────────────────────────────
function parseTs(v) { if (!v) return null; const x = new Date(v).getTime(); return Number.isNaN(x) ? null : x }
function tsDeltaMin(a, b) { const x = parseTs(a), y = parseTs(b); return (x != null && y != null && y >= x) ? Math.round((y - x) / 60000) : null }
function fmtDur(min) {
  if (min == null) return '—'
  if (min < 60) return min + ' min'
  const h = Math.floor(min / 60), m = min % 60
  if (h < 24) return m ? `${h} h ${m} min` : `${h} h`
  const d = Math.floor(h / 24), hh = h % 24
  return hh ? `${d} j ${hh} h` : `${d} j`
}
function fmtTs(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString(locale.value === 'en' ? 'en-GB' : 'fr-FR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }) }
  catch { return String(ts) }
}
function fmtCreated(v) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  const loc = locale.value === 'en' ? 'en-GB' : 'fr-FR'
  const date = d.toLocaleDateString(loc, { day: '2-digit', month: '2-digit', year: 'numeric' })
  const time = d.toLocaleTimeString(loc, { hour: '2-digit', minute: '2-digit' })
  const off = -d.getTimezoneOffset() / 60
  return `${date} ${time} (UTC${off >= 0 ? '+' : ''}${off})`
}
function fmtDate(v) {
  if (!v) return '—'
  const s = String(v).slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  return m ? `${m[3]}/${m[2]}/${m[1]}` : s
}
const d3Arr = (v) => (Array.isArray(v) ? v : (v ? [v] : []))
const normTech = (s) => String(s || '').split('.')[0]

// ── État & chargement (scopé à l'audit de l'exercice) ────────────────────────
const loading = ref(true)
const audit = ref(null)
const clientName = ref('')
const appLabels = ref([])
const tickets = ref([])
const stepsByExo = reactive({})
const obsByStep = reactive({})
const tacMap = reactive({})
const tacOrder = reactive({})
const cyclesRaw = ref([])
const cycleOpen = reactive({})

const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))
// Enregistrement courant du tiroir : ref (et non computed) pour pouvoir le rafraîchir en
// place après une édition (la prop `record` du parent reste figée jusqu'à réouverture).
const s = ref(props.record)
const statutTone = (v) => STATUT_EXO_TONE[v] || 'gray'
const equipeText = computed(() => {
  const e = s.value.equipe
  if (Array.isArray(e)) return e.length ? e.join(', ') : '—'
  return e || '—'
})

// Chargement (ré-exécutable) : appelé au montage et après chaque édition en place pour que
// cockpit / KPIs / RUNs se recalculent sans détruire le tiroir.
async function load() {
  const auditId = props.record.audit_id
  try {
    const [exs, auds, orgs, apps, tks, mx] = await Promise.all([
      auditId ? api.list('exercices', `?audit_id=${auditId}`).then(unwrap).catch(() => []) : Promise.resolve([]),
      api.list('audits').then(unwrap).catch(() => []),
      api.list('organisations').then(unwrap).catch(() => []),
      api.list('applications').then(unwrap).catch(() => []),
      api.list('tickets').then(unwrap).catch(() => []),
      api.get('/analytics/attack-matrix').catch(() => null),
    ])
    tickets.value = tks
    buildTacMap(mx)
    audit.value = auds.find((a) => a.id === auditId) || null
    clientName.value = orgs.find((o) => o.id === props.record.client_id)?.nom || ''
    const appIds = audit.value?.applications || []
    appLabels.value = appIds
      .map((id) => { const a = apps.find((x) => x.id === id); return a ? (a.nom || a.code) : null })
      .filter(Boolean)
    // Fallback : au moins l'exercice courant si l'audit n'a rien renvoyé (RLS/héritage).
    const exList = exs.length ? exs : [props.record]
    // Rafraîchit l'enregistrement courant (identité + id-card) avec sa version rechargée.
    s.value = exList.find((e) => e.id === props.record.id) || props.record
    // Purge les maps réactives pour ne pas conserver d'étapes/observations d'un état antérieur.
    Object.keys(stepsByExo).forEach((k) => delete stepsByExo[k])
    Object.keys(obsByStep).forEach((k) => delete obsByStep[k])
    const stepLists = await Promise.all(
      exList.map((e) => api.list('attack_steps', `?exercise_id=${e.id}`).then(unwrap).catch(() => []))
    )
    exList.forEach((e, i) => { stepsByExo[e.id] = stepLists[i].slice().sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0)) })
    const allSteps = stepLists.flat()
    const obsLists = await Promise.all(
      allSteps.map((st) => api.list('observations', `?attack_step_id=${st.id}`).then(unwrap).catch(() => []))
    )
    allSteps.forEach((st, i) => { obsByStep[st.id] = obsLists[i] })
    cyclesRaw.value = exList
  } finally {
    loading.value = false
  }
}
onMounted(load)

// ── Édition en place (formulaires / tiroirs empilés, pattern AuditDrawer) ─────
const editingExo = ref(null)   // exercice dont on édite les méta (EntityForm empilé)
const stepsExo = ref(null)     // exercice dont on édite les étapes (ExoStepsDrawer empilé)
async function onExoSaved() { editingExo.value = null; await load() }

function buildTacMap(matrix) {
  const cols = matrix?.tactics || []
  cols.forEach((col, i) => {
    const tac = col.tactic
    if (tac == null) return
    tacOrder[tac] = i
    for (const tt of col.techniques || []) {
      tacMap[tt.ext_id] = tac
      for (const st of tt.subtechniques || []) tacMap[st.ext_id] = tac
    }
  })
}
function techTac(technique) { return tacMap[technique] ?? tacMap[normTech(technique)] ?? null }

// ── Agrégation par RUN (KPI mesurés) ─────────────────────────────────────────
function buildCycle(exo) {
  const raw = stepsByExo[exo.id] || []
  const steps = raw.map((st) => {
    const ticket = tickets.value.find((tk) => tk.source_attack_step_id === st.id) || null
    const obs = obsByStep[st.id] || []
    const state = stepState(st, ticket)
    return { ...st, obs, ticket, state, tac: techTac(st.technique) }
  })
  const tested = steps.filter((x) => x.state !== 'untested')
  const prevented = steps.filter((x) => x.verdict === 'prevented').length
  const alerted = steps.filter((x) => x.verdict === 'alerted').length
  const logged = tested.filter((x) => x.verdict === 'logged').length
  const blind = tested.filter((x) => x.verdict === 'no_telemetry').length
  const detected = prevented + alerted
  const gaps = steps.filter((x) => x.state === 'gap').length
  const nTested = tested.length
  const detPct = nTested ? Math.round(detected / nTested * 100) : 0

  const dDet = [], dResp = [], dRem = []
  steps.forEach((x) => {
    if (x.verdict === 'alerted') {
      const a = tsDeltaMin(x.horodatage, x.horodatage_detection); if (a != null) dDet.push(a)
      const b = tsDeltaMin(x.horodatage_detection, x.horodatage_reponse); if (b != null) dResp.push(b)
    }
  })
  steps.forEach((x) => {
    const tk = x.ticket
    if (tk && tk.statut === TICKET_DONE && tk.valide_le) {
      const anchor = tk.gap_decouvert_le || x.horodatage || exo.date
      const d = tsDeltaMin(anchor, tk.valide_le); if (d != null) dRem.push(d)
    }
  })
  const mean = (a) => (a.length ? Math.round(a.reduce((acc, x) => acc + x, 0) / a.length) : null)

  const tm = {}
  tested.forEach((x) => {
    const id = x.tac || '—'
    const e = tm[id] || (tm[id] = { id, det: 0, tot: 0 })
    e.tot++
    if (x.state === 'prevented' || x.state === 'alerted' || x.state === 'covered') e.det++
  })
  const tactics = Object.values(tm)
    .sort((a, b) => (tacOrder[a.id] ?? 99) - (tacOrder[b.id] ?? 99))
    .map((e) => ({ id: e.id, det: e.det, tot: e.tot, label: e.id === '—' ? tr('noTac') : e.id, state: e.det === e.tot ? 'detected' : (e.det === 0 ? 'gap' : 'covered') }))

  return {
    exo, steps, detected, tested: nTested, logged, gaps, prevented, detPct,
    execTested: nTested, execTotal: steps.length, execRate: steps.length ? Math.round(nTested / steps.length * 100) : 0,
    prevention: nTested ? Math.round(prevented / nTested * 100) : 0,
    pPrev: prevented, pAlert: alerted, pLog: logged, pBlind: blind, pTested: nTested,
    mttd: mean(dDet), mttdN: dDet.length,
    mttrResp: mean(dResp), mttrRespN: dResp.length,
    mttrRem: mean(dRem), mttrRemN: dRem.length,
    tactics,
  }
}

// RUNs de l'audit, triés par date (kill-chain temporelle) puis id, numérotés.
const runs = computed(() => {
  const cycles = cyclesRaw.value.map(buildCycle)
  const sorted = cycles.slice().sort((a, b) =>
    String(a.exo.date || '').localeCompare(String(b.exo.date || '')) || String(a.exo.id).localeCompare(String(b.exo.id)))
  sorted.forEach((r, i) => { r.runNo = i + 1; r.isLast = i === sorted.length - 1; r.delta = i > 0 ? (r.detPct - sorted[i - 1].detPct) : null })
  return sorted
})
function runOpen(id, dflt) { return id in cycleOpen ? cycleOpen[id] : !!dflt }
function toggleRun(id, dflt) { cycleOpen[id] = !runOpen(id, dflt) }

// RUN courant = dernier de la série (kill-chain temporelle) — alimente le cockpit d'en-tête.
const current = computed(() => { const r = runs.value; return r.length ? r[r.length - 1] : null })

// Périmètre — carte d'identité du client (reprise du pattern d'AppDrawer.vue).
// Initiales pour le glyphe : 2 premières lettres significatives du nom client.
const initials = computed(() => {
  const src = String(clientName.value || '?').trim()
  const words = src.split(/\s+/).filter(Boolean)
  const raw = words.length >= 2 ? words[0][0] + words[1][0] : src.slice(0, 2)
  return raw.toUpperCase()
})
// Période brute AAAAMM -> AAAA-MM (repli sur la valeur telle quelle si non conforme).
function fmtPeriod(v) {
  if (!v) return '—'
  const m = /^(\d{4})(\d{2})$/.exec(String(v))
  return m ? `${m[1]}-${m[2]}` : String(v)
}
// Icônes de la carte (style DA : viewBox 24, currentColor, stroke 1.7), rendues via v-html.
const PERIM_ICONS = {
  client: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16"/><path d="M15 9h4a1 1 0 0 1 1 1v11"/><path d="M3 21h18M8 8h2M8 12h2M8 16h2"/></svg>',
  nom: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 7V5a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v2"/><path d="M9 20h6M12 4v16"/></svg>',
  apps: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
  audit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/></svg>',
  period: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/></svg>',
  seq: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/></svg>',
  equipe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="M16 5.5a3 3 0 0 1 0 5.8M21 20a6 6 0 0 0-4-5.6"/></svg>',
  creation: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></svg>',
  note: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M5 3h9l5 5v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5M8 13h8M8 17h6"/></svg>',
}

// Icônes des indicateurs de RUN (viewBox 16, chemins internes rendus via v-html dans un <svg
// class="ki">). Les 4 états de posture/verdict sont repris VERBATIM de SEG_ICONS d'AppDrawer
// (bouclier = prévention, cloche = alerting, document = journalisé, œil barré = angle mort) ;
// les autres sont dessinés au même gabarit. L'icône hérite de la couleur (currentColor) de sa puce.
const RUN_ICONS = {
  prev: '<path d="M8 1.6 13.4 3.6V7.6C13.4 10.6 11 12.9 8 14.1 5 12.9 2.6 10.6 2.6 7.6V3.6Z"/><path d="M5.7 7.8 7.3 9.4 10.4 6.2"/>',
  alert: '<path d="M8 2.2C6 2.2 4.8 3.6 4.8 5.6 4.8 8.2 3.9 9.6 3 10.4H13C12.1 9.6 11.2 8.2 11.2 5.6 11.2 3.6 10 2.2 8 2.2Z"/><path d="M6.6 12.2A1.5 1.5 0 0 0 9.4 12.2"/>',
  logged: '<rect x="3.2" y="2.4" width="9.6" height="11.2" rx="1.4"/><path d="M5.4 5.6H10.6M5.4 8H10.6M5.4 10.4H8.6"/>',
  blind: '<path d="M2.2 8S4.5 3.8 8 3.8s5.8 4.2 5.8 4.2-2.3 4.2-5.8 4.2c-1 0-1.9-.3-2.7-.7"/><circle cx="8" cy="8" r="1.9"/><path d="M2.5 2.5 13.5 13.5"/>',
  target: '<circle cx="8" cy="8" r="5.6"/><circle cx="8" cy="8" r="2.6"/><circle cx="8" cy="8" r="0.7"/>',
  play: '<path d="M5.5 3.4 12.2 8l-6.7 4.6Z"/>',
  clock: '<circle cx="8" cy="8" r="5.8"/><path d="M8 4.4V8l2.5 1.5"/>',
  wrench: '<path d="M11.7 2.3a2.7 2.7 0 0 0-3.2 3.4L2.9 11.3a1.3 1.3 0 0 0 1.8 1.8l5.6-5.6a2.7 2.7 0 0 0 3.4-3.2L11.9 5.1 10.9 4.1Z"/>',
  checks: '<path d="M1.8 8.2 4.4 10.8 9.4 4.6"/><path d="M7.7 10.6 8.5 11.4 13.6 5"/>',
  tag: '<path d="M2.6 2.6H8l5.4 5.4-5.4 5.4L2.6 8Z"/><circle cx="5.3" cy="5.3" r="0.9"/>',
  up: '<path d="M2.6 10.4 6 7l2.4 2.4L13.4 4.4"/><path d="M10.4 4.4H13.4V7.4"/>',
  down: '<path d="M2.6 5.6 6 9l2.4-2.4L13.4 11.6"/><path d="M10.4 11.6H13.4V8.6"/>',
  covered: '<circle cx="8" cy="8" r="5.8"/><path d="M5.4 8 7.1 9.7 10.6 6.2"/>',
  partial: '<circle cx="8" cy="8" r="5.8"/><path d="M8 2.2v11.6"/>',
  gap: '<circle cx="8" cy="8" r="5.8"/><path d="M5.9 5.9 10.1 10.1M10.1 5.9 5.9 10.1"/>',
  untested: '<path d="M3.6 8H12.4"/>',
}
const VERDICT_ICON = { prevented: 'prev', alerted: 'alert', logged: 'logged', no_telemetry: 'blind', not_tested: 'untested' }
function verdictIcon(v) { return RUN_ICONS[VERDICT_ICON[v] || 'untested'] }
const TAC_ICON = { detected: 'covered', covered: 'partial', gap: 'gap' }
function tacIcon(state) { return RUN_ICONS[TAC_ICON[state] || 'partial'] }

// Courbe de tendance : polyline SVG de la couverture (detPct) sur tous les RUNs de l'audit.
// Reprise du pattern d'AppDrawer.vue (viewBox étiré, preserveAspectRatio="none").
const TREND_W = 520, TREND_H = 80
const trendGeo = computed(() => {
  const pts = runs.value
  if (pts.length < 2) return null
  const xs = pts.map((_, i) => 12 + (TREND_W - 24) * (i / (pts.length - 1)))
  const ys = pts.map((p) => 10 + (TREND_H - 24) * (1 - (p.detPct || 0) / 100))
  return {
    line: xs.map((x, i) => `${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' '),
    dots: xs.map((x, i) => ({ x, y: ys[i], pct: pts[i].detPct, runNo: pts[i].runNo, last: i === pts.length - 1 })),
  }
})
</script>

<template>
  <DetailDrawer :subtitle="tr('subtitle')" wide @close="emit('close')">
    <template v-if="!readonly" #actions>
      <button class="btn slim" @click="editingExo = s">{{ tr('edit') }}</button>
    </template>

    <!-- 1. Identité (bandeau) + 2. Périmètre — le contexte d'abord, la mesure ensuite -->
    <section class="sec">
      <div class="idstrip">
        <span class="pill pill-violet">RUN {{ s.run_number ?? '—' }}</span>
        <span :class="['pill', 'pill-' + statutTone(s.statut)]"><span class="dot"></span>{{ s.statut }}</span>
        <span v-if="s.tlp" :class="['pill', 'pill-' + (TLP_TONE[s.tlp] || 'gray')]">TLP:{{ s.tlp }}</span>
        <span class="idstrip-date">{{ fmtDate(s.date) }}</span>
      </div>

      <div class="id-card">
        <div class="id-head">
          <div class="id-glyph">{{ initials }}</div>
          <div class="id-org">
            <div class="id-org-lbl"><span class="id-ico" v-html="PERIM_ICONS.client"></span>{{ tr('client') }}</div>
            <div class="id-org-name">{{ clientName || '—' }}</div>
            <div class="id-org-sub">{{ [audit?.nom, fmtPeriod(s.period), s.seq != null ? tr('run') + ' ' + String(s.seq).padStart(2, '0') : null].filter(Boolean).join(' · ') || '—' }}</div>
          </div>
        </div>

        <div class="id-grid">
          <div class="id-cell id-cell-wide">
            <div class="id-lbl"><span class="id-ico" v-html="PERIM_ICONS.apps"></span>{{ tr('apps') }}</div>
            <div class="id-val">
              <template v-if="appLabels.length"><span v-for="a in appLabels" :key="a" class="chip">{{ a }}</span></template>
              <template v-else>—</template>
            </div>
          </div>
          <div class="id-cell id-cell-wide">
            <div class="id-lbl"><span class="id-ico" v-html="PERIM_ICONS.nom"></span>{{ tr('nom') }}</div>
            <div class="id-val mono">{{ s.nom || '—' }}</div>
          </div>
          <div class="id-cell id-cell-wide">
            <div class="id-lbl"><span class="id-ico" v-html="PERIM_ICONS.audit"></span>{{ tr('audit') }}</div>
            <!-- En compagnon, l'audit remplace le panneau en place. -->
            <div class="id-val mono">
              <a v-if="audit && readonly" class="id-link" role="button" tabindex="0"
                 @click="emit('open-entity', { kind: 'audit', record: { id: audit.id } })"
                 @keydown.enter.prevent="emit('open-entity', { kind: 'audit', record: { id: audit.id } })">{{ audit.nom }}</a>
              <template v-else>{{ audit?.nom || '—' }}</template>
            </div>
          </div>
          <div class="id-cell">
            <div class="id-lbl"><span class="id-ico" v-html="PERIM_ICONS.period"></span>{{ tr('period') }}</div>
            <div class="id-val mono">{{ fmtPeriod(s.period) }}</div>
          </div>
          <div class="id-cell">
            <div class="id-lbl"><span class="id-ico" v-html="PERIM_ICONS.seq"></span>{{ tr('seq') }}</div>
            <div class="id-val mono">{{ s.seq != null ? tr('run') + ' ' + String(s.seq).padStart(2, '0') : '—' }}</div>
          </div>
          <div class="id-cell">
            <div class="id-lbl"><span class="id-ico" v-html="PERIM_ICONS.equipe"></span>{{ tr('equipe') }}</div>
            <div class="id-val">{{ equipeText }}</div>
          </div>
          <div class="id-cell">
            <div class="id-lbl"><span class="id-ico" v-html="PERIM_ICONS.creation"></span>{{ tr('creation') }}</div>
            <div class="id-val">{{ fmtCreated(s.created_at) }}</div>
          </div>
        </div>

        <div v-if="s.notes" class="id-notes">
          <div class="id-lbl"><span class="id-ico" v-html="PERIM_ICONS.note"></span>{{ tr('notes') }}</div>
          <div class="id-notes-body">{{ s.notes }}</div>
        </div>
      </div>
    </section>

    <!-- 3. Cockpit de posture (RUN courant) -->
    <section class="sec">
      <div class="ck-eyebrow eyebrow">{{ tr('cockpitEyebrow') }}</div>
      <p v-if="loading" class="faint">{{ tr('loading') }}</p>
      <p v-else-if="!current" class="faint">{{ tr('noRun') }}</p>
      <template v-else>
        <div class="ck-grid">
          <!-- Héro couverture + tendance -->
          <div class="ck-hero">
            <div class="ck-hero-top">
              <span class="ck-big" :class="current.detPct >= 75 ? 'is-green' : (current.detPct >= 50 ? 'is-amber' : 'is-red')">{{ current.detPct }}<span class="u">%</span></span>
              <span v-if="current.delta !== null" class="k-chip" :class="'k-' + (current.delta > 0 ? 'green' : (current.delta < 0 ? 'red' : 'gray'))">
                <svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS[current.delta > 0 ? 'up' : (current.delta < 0 ? 'down' : 'untested')]"></svg>{{ (current.delta > 0 ? '+' : '') + current.delta }} {{ tr('deltaUnit') }}
              </span>
            </div>
            <div class="ck-hero-foot"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.target"></svg>{{ tr('coverage') }} · <b>{{ current.detected }}/{{ current.tested }}</b> {{ tr('detectedFoot') }}<template v-if="current.delta !== null"> · {{ tr('vsRun') }} {{ current.runNo - 1 }}</template></div>
            <div v-if="trendGeo" class="ck-spark">
              <svg :viewBox="'0 0 ' + TREND_W + ' ' + TREND_H" preserveAspectRatio="none" class="ck-spark-svg">
                <polyline :points="trendGeo.line" fill="none" stroke="var(--violet-accent)" stroke-width="2" />
                <circle v-for="(pt, i) in trendGeo.dots" :key="i" :cx="pt.x" :cy="pt.y" :r="pt.last ? 4 : 3" :fill="pt.last ? 'var(--green)' : 'var(--violet-accent)'" />
              </svg>
              <div class="ck-spark-x">
                <span v-for="(pt, i) in trendGeo.dots" :key="i" class="ck-xr" :class="{ last: pt.last }">R{{ pt.runNo }} · {{ pt.pct }}%</span>
              </div>
            </div>
          </div>
          <!-- Tuiles secondaires -->
          <div class="ck-tiles">
            <div class="ck-tile"><div class="ck-tl"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.blind"></svg>{{ tr('blind') }}</div><div class="ck-tv" :class="{ 'is-red': current.gaps > 0 }">{{ current.gaps }}</div></div>
            <div class="ck-tile"><div class="ck-tl"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.play"></svg>{{ tr('played') }}</div><div class="ck-tv">{{ current.execTested }}/{{ current.execTotal }}</div></div>
            <div class="ck-tile"><div class="ck-tl"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.clock"></svg>MTTD</div><div class="ck-tv">{{ fmtDur(current.mttd) }}</div></div>
            <div class="ck-tile"><div class="ck-tl"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.wrench"></svg>{{ tr('mttrRem') }}</div><div class="ck-tv" :class="{ 'is-amber': current.mttrRem !== null }">{{ fmtDur(current.mttrRem) }}</div></div>
          </div>
        </div>

        <!-- Barre de posture agrégée (RUN courant) -->
        <div v-if="current.pTested > 0" class="pbar-wrap ck-pbar">
          <div class="pbar">
            <div v-if="current.pPrev > 0" class="pseg prev" :style="{ flexGrow: current.pPrev }"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.prev"></svg>{{ Math.round(current.pPrev / current.pTested * 100) }}%</div>
            <div v-if="current.pAlert > 0" class="pseg alrt" :style="{ flexGrow: current.pAlert }"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.alert"></svg>{{ Math.round(current.pAlert / current.pTested * 100) }}%</div>
            <div v-if="current.pLog > 0" class="pseg logd" :style="{ flexGrow: current.pLog }"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.logged"></svg>{{ Math.round(current.pLog / current.pTested * 100) }}%</div>
            <div v-if="current.pBlind > 0" class="pseg blnd" :style="{ flexGrow: current.pBlind }"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.blind"></svg>{{ Math.round(current.pBlind / current.pTested * 100) }}%</div>
          </div>
          <div class="pbar-legend">
            <span class="pleg prev"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.prev"></svg>{{ tr('pPrev') }} <b>{{ current.pPrev }}/{{ current.pTested }}</b></span>
            <span class="pleg alrt"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.alert"></svg>{{ tr('pAlert') }} <b>{{ current.pAlert }}/{{ current.pTested }}</b></span>
            <span class="pleg logd"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.logged"></svg>{{ tr('pLog') }} <b>{{ current.pLog }}/{{ current.pTested }}</b></span>
            <span class="pleg blnd"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.blind"></svg>{{ tr('pBlind') }} <b>{{ current.pBlind }}/{{ current.pTested }}</b></span>
          </div>
        </div>
      </template>
    </section>

    <!-- 4. RUNs de l'audit (tableau de bord groupé, lecture seule) -->
    <section class="sec">
      <div class="panel-card">
        <div class="panel-head">
          <div class="panel-title plain">{{ tr('runsOf') }}</div>
          <div class="cyc-legend">
            <span class="lz"><span class="cyc-lb stv-det"></span>{{ tr('legDet') }}</span>
            <span class="lz"><span class="cyc-lb stv-cov"></span>{{ tr('legPart') }}</span>
            <span class="lz"><span class="cyc-lb stv-gap"></span>{{ tr('legGap') }}</span>
          </div>
        </div>

        <p v-if="loading" class="faint">{{ tr('loading') }}</p>

        <div v-for="c in runs" :key="c.exo.id" class="cyc-sc" :class="{ open: runOpen(c.exo.id, c.isLast) }">
          <div class="cyc-head" role="button" tabindex="0"
               @click="toggleRun(c.exo.id, c.isLast)" @keydown.enter.prevent="toggleRun(c.exo.id, c.isLast)" @keydown.space.prevent="toggleRun(c.exo.id, c.isLast)">
            <span class="cyc-chev">▸</span>
            <span class="pill pill-violet">{{ tr('run') }} {{ c.runNo }}</span>
            <span class="cyc-name">{{ c.exo.nom }}</span>
            <div class="cyc-kpis">
              <span v-if="c.delta !== null" class="k-chip sm" :class="'k-' + (c.delta > 0 ? 'green' : (c.delta < 0 ? 'red' : 'gray'))">
                <svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS[c.delta > 0 ? 'up' : (c.delta < 0 ? 'down' : 'untested')]"></svg>{{ (c.delta > 0 ? '+' : '') + c.delta }} {{ tr('deltaUnit') }}
              </span>
              <span class="k-chip sm" :class="'k-' + (c.detPct >= 75 ? 'green' : (c.detPct >= 50 ? 'amber' : 'red'))"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.target"></svg>{{ tr('cov') }} {{ c.detPct }}%</span>
              <span class="k-chip sm" :class="c.gaps ? 'k-red' : 'k-gray'"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.blind"></svg>{{ c.gaps }} {{ c.gaps > 1 ? tr('gapsPl') : tr('gapsSg') }}</span>
            </div>
            <div class="cyc-tacmini">
              <span v-for="tt in c.tactics" :key="tt.id" class="cyc-tmb" :class="stvClass(tt.state)" :title="`${tt.label} · ${tt.det}/${tt.tot}`"></span>
            </div>
            <div v-if="!readonly" class="cyc-actions">
              <button class="btn slim" :title="tr('editRunT')" @click.stop="editingExo = c.exo">✎ {{ tr('editRun') }}</button>
              <button class="btn slim" :title="tr('editStepsT')" @click.stop="stepsExo = c.exo">☰ {{ tr('editSteps') }}</button>
            </div>
          </div>

          <div v-show="runOpen(c.exo.id, c.isLast)" class="cyc-body">
            <p v-if="!c.steps.length" class="faint" style="font-size:12.5px">{{ tr('noSteps') }}</p>

            <!-- Métriques défensives détaillées (déplacées hors de l'en-tête) -->
            <div class="run-metrics">
              <span class="k-chip sm" :class="c.execRate >= 70 ? 'k-gray' : 'k-amber'"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.play"></svg>{{ tr('exec') }} {{ c.execTested }}/{{ c.execTotal }} · {{ c.execRate }}%</span>
              <span class="k-chip k-green sm"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.checks"></svg>{{ c.detected }}/{{ c.tested }} {{ tr('detN') }}</span>
              <span v-if="c.prevention > 0" class="k-chip k-green sm"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.prev"></svg>{{ c.prevention }}% {{ tr('prev') }}</span>
              <span v-if="c.logged > 0" class="k-chip k-amber sm"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.logged"></svg>{{ c.logged }} {{ tr('logged') }}</span>
              <span v-if="c.mttd !== null" class="k-chip sm" :class="c.mttdN < 3 ? 'k-amber' : 'k-gray'"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.clock"></svg>MTTD {{ fmtDur(c.mttd) }}{{ c.mttdN < 3 ? ' · n=' + c.mttdN : '' }}</span>
              <span v-if="c.mttrResp !== null" class="k-chip sm" :class="c.mttrRespN < 3 ? 'k-amber' : 'k-gray'"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.clock"></svg>{{ tr('mttrResp') }} {{ fmtDur(c.mttrResp) }}{{ c.mttrRespN < 3 ? ' · n=' + c.mttrRespN : '' }}</span>
              <span v-if="c.mttrRem !== null" class="k-chip sm" :class="c.mttrRemN < 3 ? 'k-amber' : 'k-gray'"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.wrench"></svg>{{ tr('mttrRem') }} {{ fmtDur(c.mttrRem) }}{{ c.mttrRemN < 3 ? ' · n=' + c.mttrRemN : '' }}</span>
              <span v-if="c.exo.tlp" class="k-chip k-gray sm"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.tag"></svg>TLP:{{ c.exo.tlp }}</span>
            </div>

            <!-- Barre de posture -->
            <div v-if="c.pTested > 0" class="pbar-wrap">
              <div class="pbar-eyebrow eyebrow">{{ tr('posture') }} · {{ c.pTested }} {{ tr('testedN') }}</div>
              <div class="pbar">
                <div v-if="c.pPrev > 0" class="pseg prev" :style="{ flexGrow: c.pPrev }"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.prev"></svg>{{ Math.round(c.pPrev / c.pTested * 100) }}%</div>
                <div v-if="c.pAlert > 0" class="pseg alrt" :style="{ flexGrow: c.pAlert }"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.alert"></svg>{{ Math.round(c.pAlert / c.pTested * 100) }}%</div>
                <div v-if="c.pLog > 0" class="pseg logd" :style="{ flexGrow: c.pLog }"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.logged"></svg>{{ Math.round(c.pLog / c.pTested * 100) }}%</div>
                <div v-if="c.pBlind > 0" class="pseg blnd" :style="{ flexGrow: c.pBlind }"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.blind"></svg>{{ Math.round(c.pBlind / c.pTested * 100) }}%</div>
              </div>
              <div class="pbar-legend">
                <span class="pleg prev"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.prev"></svg>{{ tr('pPrev') }} <b>{{ c.pPrev }}/{{ c.pTested }}</b></span>
                <span class="pleg alrt"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.alert"></svg>{{ tr('pAlert') }} <b>{{ c.pAlert }}/{{ c.pTested }}</b></span>
                <span class="pleg logd"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.logged"></svg>{{ tr('pLog') }} <b>{{ c.pLog }}/{{ c.pTested }}</b></span>
                <span class="pleg blnd"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="RUN_ICONS.blind"></svg>{{ tr('pBlind') }} <b>{{ c.pBlind }}/{{ c.pTested }}</b></span>
              </div>
            </div>

            <!-- Timeline d'étapes -->
            <div v-if="c.steps.length" class="cyc-tl">
              <div v-for="st in c.steps" :key="st.id" class="cyc-step">
                <div class="cyc-row">
                  <div class="cyc-bead" :class="stvClass(st.state)">{{ st.ordre }}</div>
                  <div class="cyc-main">
                    <span class="mono-cell">{{ st.technique || '—' }}</span>
                    <span class="cell-strong">{{ st.titre }}</span>
                    <span class="k-chip" :class="'k-' + (VERDICT_TONE[st.verdict] || 'gray')"><svg class="ki" viewBox="0 0 16 16" aria-hidden="true" v-html="verdictIcon(st.verdict)"></svg>{{ verdictLabel(st.verdict) }}</span>
                    <span v-for="o in st.obs" :key="o.id" class="k-chip k-gray"><span class="dot"></span>{{ o.source || '—' }}{{ o.resultat ? ' · ' + verdictLabel(o.resultat) : '' }}</span>
                    <span class="cyc-tac">{{ (st.tac || tr('noTac')) }} · {{ fmtTs(st.horodatage) }}</span>
                  </div>
                </div>
                <!-- Remédiation liée (lecture seule) -->
                <div v-if="st.ticket" class="cyc-rem">
                  <span class="cyc-rl">{{ tr('remLabel') }}</span>
                  <span class="k-chip" :class="'k-' + ticketStatutTone(st.ticket.statut)"><span class="dot"></span>{{ st.ticket.statut }}</span>
                  <span v-for="m in d3Arr(st.ticket.mesure_d3fend)" :key="m" class="k-chip k-cyan">{{ m }}</span>
                  <span v-if="st.ticket.priorite" class="k-chip" :class="'k-' + prioTone(st.ticket.priorite)">{{ st.ticket.priorite }}</span>
                </div>
              </div>
            </div>

            <!-- Couverture par tactique MITRE -->
            <div v-if="c.tactics.length" class="cyc-tackpi">
              <div class="cyc-tackpi-h">{{ tr('tacKpi') }} <span class="faint">· {{ tr('killchain') }}</span></div>
              <div class="cyc-tstrip">
                <div v-for="tt in c.tactics" :key="tt.id" class="cyc-tcell" :class="stvClass(tt.state)">
                  <div class="cyc-tname">{{ tt.label }}</div>
                  <div class="cyc-tfoot">
                    <svg class="ki cyc-tki" viewBox="0 0 16 16" aria-hidden="true" v-html="tacIcon(tt.state)"></svg>
                    <span class="cyc-tfrac">{{ tt.det }}/{{ tt.tot }}</span>
                    <span class="cyc-tlbl">{{ tt.state === 'detected' ? tr('covered') : (tt.state === 'gap' ? tr('gap') : tr('partial')) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Édition en place (tiroirs empilés) : méta du RUN + étapes -->
    <EntityForm
      v-if="editingExo"
      entity="exercices"
      :fields="ENTITY_FIELDS.exercices"
      :record="editingExo"
      :hidden="['client_id']"
      :title="tr('edit')"
      @saved="onExoSaved"
      @close="editingExo = null"
    />
    <ExoStepsDrawer
      v-if="stepsExo"
      :exercise="stepsExo"
      @changed="load"
      @close="stepsExo = null"
    />
  </DetailDrawer>
</template>

<style scoped>
.slim{padding:3px 9px;font-size:11.5px}
.sec{margin-bottom:18px}
.sec-t{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight);margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--border-2)}
.dl{display:grid;grid-template-columns:150px 1fr;gap:7px 12px;margin:0;font-size:13px}
.dl dt{color:var(--muted)} .dl dd{margin:0;color:var(--text)}
.mono{font-family:var(--font-data);font-size:12.5px}
.prose{font-size:13px;color:var(--text);line-height:1.5;margin-top:10px}
/* Géométrie du .chip normatif (base.css §0.3) ; l'habillage reste la variante locale
   (rayon --r-mini, bordure pleine) propre à ce tiroir. */
.chip{display:inline-flex;align-items:center;height:22px;padding:0 9px;line-height:1;white-space:nowrap;
  background:var(--surface-3);border:1px solid var(--border);border-radius:var(--r-mini);
  font-size:11.5px;color:var(--text);margin:0 6px 4px 0}

.pill{display:inline-block;padding:2px 9px;border-radius:var(--r-pill);font-size:11px;font-weight:600;border:1px solid transparent}
.pill .dot{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block;margin-right:5px}
.pill-violet{background:var(--c-violet-bg);border-color:var(--c-violet-bd);color:var(--c-violet-tx)}
.pill-blue{background:var(--c-blue-bg);border-color:var(--c-blue-bd);color:var(--c-blue-tx)}
.pill-green{background:var(--c-green-bg);border-color:var(--c-green-bd);color:var(--green)}
.pill-amber{background:var(--c-amber-bg);border-color:var(--c-amber-bd);color:var(--c-amber-tx)}
.pill-red{background:var(--c-red-bg);border-color:var(--c-red-bd);color:var(--c-red-tx)}
.pill-cyan{background:var(--c-cyan-bg);border-color:var(--c-cyan-bd);color:var(--c-cyan-tx)}
.pill-gray{background:var(--c-gray-bg);border-color:var(--c-gray-bd);color:var(--c-gray-tx)}

/* Bandeau d'identité + cockpit de posture (RUN courant) */
.idstrip{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:14px}
.idstrip-date{font-family:var(--font-data);font-size:11.5px;color:var(--muted);margin-left:2px}
.ck-eyebrow{margin-bottom:10px}
.ck-grid{display:grid;grid-template-columns:1.35fr 1fr;gap:12px;margin-bottom:14px}
.ck-hero{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-card);padding:14px 16px;display:flex;flex-direction:column;box-shadow:var(--shadow)}
.ck-hero-top{display:flex;align-items:baseline;gap:10px}
.ck-big{font-family:var(--font-data);font-size:38px;font-weight:700;line-height:1}
.ck-big .u{font-size:18px;font-weight:600;margin-left:1px}
.ck-big.is-green{color:var(--c-green-tx)} .ck-big.is-amber{color:var(--c-amber-tx)} .ck-big.is-red{color:var(--c-red-tx)}
.ck-hero-foot{font-size:12px;color:var(--muted);margin-top:5px}
.ck-hero-foot b{font-family:var(--font-data);color:var(--text);font-weight:600}
.ck-spark{margin-top:auto;padding-top:10px}
.ck-spark-svg{width:100%;height:44px;display:block}
.ck-spark-x{display:flex;justify-content:space-between;margin-top:4px;gap:6px}
.ck-xr{font-family:var(--font-data);font-size:9.5px;color:var(--faint);white-space:nowrap}
.ck-xr.last{color:var(--c-green-tx);font-weight:600}
.ck-tiles{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:10px}
.ck-tile{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-card);padding:10px 12px;display:flex;flex-direction:column;justify-content:center;box-shadow:var(--shadow)}
.ck-tl{display:flex;align-items:center;gap:5px;font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:9.5px;color:var(--faint);margin-bottom:4px}
.ck-tl .ki{width:11px;height:11px}
.ck-tv{font-family:var(--font-data);font-size:20px;font-weight:700;color:var(--heading);line-height:1}
.ck-tv.is-red{color:var(--c-red-tx)} .ck-tv.is-amber{color:var(--c-amber-tx)}
.ck-pbar{margin-bottom:0}

/* Périmètre — carte d'identité du client (reprise d'AppDrawer.vue) */
.id-card{border:1px solid var(--border);border-radius:12px;overflow:hidden}
.id-head{display:flex;align-items:center;gap:12px;padding:14px 15px;background:var(--surface-2);border-bottom:1px solid var(--border-2)}
.id-glyph{width:42px;height:42px;flex:0 0 auto;border-radius:10px;background:var(--violet-soft);color:var(--violet-accent);display:flex;align-items:center;justify-content:center;font-family:var(--font-display);font-weight:600;font-size:15px}
.id-org{min-width:0}
.id-org-lbl{display:flex;align-items:center;gap:6px;font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.id-org-name{font-family:var(--font-display);font-size:15px;font-weight:600;color:var(--heading);margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.id-org-sub{font-family:var(--font-data);font-size:11.5px;color:var(--muted);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.id-grid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--border-2)}
.id-cell{background:var(--surface);padding:11px 15px;min-width:0}
.id-cell-wide{grid-column:1 / -1}
.id-lbl{display:flex;align-items:center;gap:6px;font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.id-val{font-size:13px;color:var(--text);margin-top:4px;overflow:hidden;text-overflow:ellipsis}
.id-val.mono{font-family:var(--font-data);font-size:12.5px}
.id-link{color:var(--violet-accent);cursor:pointer}
.id-link:hover{text-decoration:underline}
.id-ico{display:inline-flex;width:13px;height:13px;color:var(--faint);flex:0 0 auto}
.id-ico :deep(svg){width:100%;height:100%;display:block}
.id-notes{padding:11px 15px;border-top:1px solid var(--border-2);background:var(--surface)}
.id-notes-body{font-size:13px;color:var(--text);line-height:1.5;margin-top:5px}
.id-card .chip{margin:0 6px 0 0}

/* Métriques défensives déplacées sous l'en-tête de RUN */
.run-metrics{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;margin-bottom:4px}

.panel-card{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-card);padding:16px}
.panel-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.panel-title{display:flex;align-items:center;gap:9px;font-family:var(--font-display);font-weight:600;color:var(--heading);font-size:14px}
.panel-title.plain{font-size:14.5px}

.mono-cell{font-family:var(--font-data);font-size:10.5px;color:#c6b2ff}
.cell-strong{font-weight:600;color:var(--heading)}
.eyebrow{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10.5px;color:var(--muted);font-weight:var(--eyebrow-weight)}
.faint{color:var(--faint)}

/* Icône d'indicateur (viewBox 16, hérite de la couleur de sa puce via currentColor). */
.ki{width:12px;height:12px;flex:0 0 auto;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;vertical-align:-2px}
.k-chip.sm .ki{width:11px;height:11px}
.ck-hero-foot .ki{margin-right:5px}
.cyc-tki{color:var(--stt)}

/* Puces (tons doux). */
.k-chip{display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 9px;border-radius:var(--r-pill,999px);font-family:var(--font-data);font-size:11px;font-weight:500;border:1px solid transparent;white-space:nowrap;color:var(--muted)}
.k-chip.sm{height:19px;font-size:10px;padding:0 7px}
.k-chip .dot{width:6px;height:6px;border-radius:50%;background:currentColor;flex:0 0 auto}
.k-green{background:var(--c-green-bg);border-color:var(--c-green-bd);color:var(--c-green-tx)}
.k-red{background:var(--c-red-bg);border-color:var(--c-red-bd);color:var(--c-red-tx)}
.k-amber{background:var(--c-amber-bg);border-color:var(--c-amber-bd);color:var(--c-amber-tx)}
.k-cyan{background:var(--c-cyan-bg);border-color:var(--c-cyan-bd);color:var(--c-cyan-tx)}
.k-blue{background:var(--c-blue-bg);border-color:var(--c-blue-bd);color:var(--c-blue-tx)}
.k-violet{background:var(--c-violet-bg);border-color:var(--c-violet-bd);color:var(--c-violet-tx)}
.k-gray{background:var(--c-gray-bg);border-color:var(--c-gray-bd);color:var(--c-gray-tx)}

.stv-det{--stb:var(--c-green-bg);--std:var(--c-green-bd);--stt:var(--c-green-tx)}
.stv-gap{--stb:var(--c-red-bg);--std:var(--c-red-bd);--stt:var(--c-red-tx)}
.stv-cov{--stb:var(--c-amber-bg);--std:var(--c-amber-bd);--stt:var(--c-amber-tx)}
.stv-prev{--stb:var(--c-green-bg);--std:var(--c-green-bd);--stt:var(--c-green-tx)}
.stv-part{--stb:var(--c-amber-bg);--std:var(--c-amber-bd);--stt:var(--c-amber-tx)}
.stv-untested{--stb:transparent;--std:var(--border-2);--stt:var(--muted)}
.cyc-legend{display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-family:var(--font-data);font-size:10.5px;color:var(--muted)}
.cyc-legend .lz{display:inline-flex;align-items:center;gap:5px}
.cyc-lb{width:9px;height:9px;border-radius:50%;border:2px solid var(--std);background:var(--stb)}
.cyc-sc{border:1px solid var(--border);border-radius:12px;margin-bottom:12px;background:var(--surface);overflow:hidden}
.cyc-sc:last-child{margin-bottom:0}
.cyc-sc.open{box-shadow:0 0 0 1px var(--violet-soft)}
.cyc-head{display:flex;align-items:center;gap:11px;padding:12px 14px;cursor:pointer;user-select:none;flex-wrap:wrap}
.cyc-head:hover .cyc-name{color:var(--violet-accent)}
.cyc-chev{color:var(--faint);transition:transform .16s;flex:0 0 auto;font-family:var(--font-data)}
.cyc-sc.open .cyc-chev{transform:rotate(90deg)}
.cyc-name{font-family:var(--font-display);font-size:14px;font-weight:600;color:var(--heading);flex:0 0 auto}
.cyc-kpis{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.cyc-tacmini{display:flex;gap:4px;margin-left:auto;flex:0 0 auto}
.cyc-actions{display:flex;align-items:center;gap:8px;flex:1 0 100%;justify-content:flex-end;margin-top:4px}
.cyc-tmb{width:15px;height:15px;border-radius:50%;border:2px solid var(--std);background:var(--stb)}
.cyc-body{padding:6px 14px 14px;border-top:1px solid var(--border-2)}
.cyc-tl{display:flex;flex-direction:column;margin-top:8px}
.cyc-step{border-left:2px solid var(--border-2);margin-left:13px;position:relative}
.cyc-row{display:flex;align-items:center;gap:9px;padding:8px 2px 8px 15px;position:relative}
.cyc-bead{position:absolute;left:-9px;top:50%;transform:translateY(-50%);width:16px;height:16px;border-radius:50%;border:2px solid var(--std);background:var(--stb);color:var(--stt);font-family:var(--font-data);font-size:9px;font-weight:600;display:flex;align-items:center;justify-content:center}
.cyc-main{flex:1;min-width:0;display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.cyc-tac{font-family:var(--font-data);font-size:10.5px;color:var(--faint);margin-left:auto;white-space:nowrap}
.cyc-rem{margin:0 0 8px 15px;padding:8px 11px;border:1px dashed var(--c-violet-bd);border-radius:10px;background:var(--c-violet-bg);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.cyc-rl{font-family:var(--font-eyebrow);font-size:9.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--c-violet-tx)}
.cyc-tackpi{margin-top:12px;padding-top:12px;border-top:1px dashed var(--border-2)}
.cyc-tackpi-h{font-family:var(--font-eyebrow);font-size:10.5px;font-weight:var(--eyebrow-weight);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:9px}
.cyc-tackpi-h .faint{font-weight:400;text-transform:none;letter-spacing:0;color:var(--faint)}
.cyc-tstrip{display:flex;align-items:stretch;overflow-x:auto;padding-bottom:2px}
.cyc-tcell{flex:1;min-width:120px;display:flex;flex-direction:column;gap:5px;padding:9px 11px;border:1px solid var(--border-2);border-left:3px solid var(--std);border-radius:9px;background:var(--surface-2);position:relative}
.cyc-tcell + .cyc-tcell{margin-left:9px}
.cyc-tcell::before{content:"\203A";position:absolute;left:-13px;top:50%;transform:translateY(-50%);color:var(--faint);font-size:14px}
.cyc-tcell:first-child::before{content:none}
.cyc-tname{font-family:var(--font-display);font-size:12px;font-weight:600;color:var(--heading);line-height:1.1}
.cyc-tfoot{display:flex;align-items:center;gap:6px}
.cyc-tbead{width:12px;height:12px;border-radius:50%;border:2px solid var(--std);background:var(--stb);flex:0 0 auto}
.cyc-tfrac{font-family:var(--font-data);font-size:11px;font-weight:600;color:var(--stt)}
.cyc-tlbl{font-family:var(--font-data);font-size:9.5px;color:var(--faint);margin-left:auto}

.pbar-wrap{margin-bottom:14px}
.pbar-eyebrow{margin-bottom:8px}
.pbar{display:flex;height:34px;border-radius:8px;overflow:hidden;border:1px solid var(--border-2)}
.pseg{display:flex;align-items:center;justify-content:center;gap:5px;min-width:0;flex-basis:0;font-family:var(--font-data);font-size:11px;font-weight:600;background:var(--c-bg);color:var(--c-tx)}
.pseg .ki{width:13px;height:13px}
.pseg.prev{--c-bg:var(--c-green-bg);--c-tx:var(--c-green-tx)}
.pseg.alrt{--c-bg:var(--c-green-bg);--c-tx:var(--c-green-tx);border-left:2px dashed var(--c-green-bd)}
.pseg.logd{--c-bg:var(--c-amber-bg);--c-tx:var(--c-amber-tx)}
.pseg.blnd{--c-bg:var(--c-red-bg);--c-tx:var(--c-red-tx)}
.pbar-legend{display:flex;flex-wrap:wrap;gap:13px;margin-top:9px}
.pleg{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:var(--muted)}
.pleg b{font-family:var(--font-data);font-weight:600}
.pleg.prev,.pleg.prev b{color:var(--c-green-tx)}
.pleg.alrt,.pleg.alrt b{color:var(--c-green-tx)}
.pleg.logd,.pleg.logd b{color:var(--c-amber-tx)}
.pleg.blnd,.pleg.blnd b{color:var(--c-red-tx)}
@media (max-width:820px){ .ck-grid{grid-template-columns:1fr} }
@media (max-width:560px){ .id-grid{grid-template-columns:1fr} }
</style>
