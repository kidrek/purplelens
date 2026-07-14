<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, ApiError } from '../api/client'
import EntityForm from '../components/EntityForm.vue'
import ExoStepsDrawer from '../components/ExoStepsDrawer.vue'
import { fieldsFor } from '../fields'

// Page « Exercices Purple » — portage de la maquette (cycle Red → Blue → Détection).
// Tout est INLINE : regroupement par audit, cartes de run repliables, KPI mesurés
// (couverture, MTTD/MTTR, posture), timeline d'étapes avec verdicts/observations,
// remédiation (tickets détection D3FEND/Sigma) et couverture par tactique MITRE.
// L'édition se fait via drawers (EntityForm) ouverts depuis les cartes.
//
// Données réelles (liens directs, plus propres que la maquette) :
//   exercices ← attack_steps(?exercise_id) ← observations(?attack_step_id)
//   tickets.source_attack_step_id → étape ; /analytics/attack-matrix → tactique.
const { t, locale } = useI18n()

// Dictionnaire bilingue local (labels bespoke de cette page — évite d'alourdir i18n/*.json).
const DICT = {
  fr: {
    eyebrow: 'Pilotage', title: 'Exercices Purple', sub: 'Boucle Attack ↔ Defense, KPI, debrief.',
    newExo: '+ Nouvel exercice', empty: 'Aucun exercice Purple pour l’instant.',
    cycleDoc: 'Cycle Purple Team — 6 phases & entités : consulter la fiche méthodologique',
    cycle: 'Cycle Purple — boucle Red → Blue → Détection', scenarios: 'scénarios', runs: 'run(s)', run: 'Run',
    legDet: 'Détectée', legPart: 'Partielle', legGap: 'Angle mort', noAudit: 'Sans audit',
    editExo: 'Éditer l’exercice', editSteps: 'Éditer les étapes', addStep: 'Ajouter une étape',
    noSteps: 'Aucune étape testée sur cet exercice.',
    delExo: 'Supprimer', delExoConfirm: 'Supprimer l’exercice « {nom} » ? Cette action est journalisée.',
    cov: 'Couv.', exec: 'joué', detN: 'détectés', prev: 'prévenu', logged: 'journalisé',
    gapsSg: 'angle mort', gapsPl: 'angles morts', mttrResp: 'MTTR réponse', mttrRem: 'MTTR remédiation',
    posture: 'Décomposition de la posture', testedN: 'étapes testées',
    pPrev: 'Prévention', pAlert: 'Alerting', pLog: 'Journalisé', pBlind: 'Angle mort',
    tacKpi: 'Couverture par tactique MITRE', killchain: 'ordre kill-chain',
    covered: 'couverte', gap: 'angle mort', partial: 'partielle', noTac: 'Non mappée',
    remLabel: 'Purple — Remédiation', remLinked: 'Remédiation liée', advance: 'Faire avancer',
    editTicket: 'Éditer', createTicket: 'Créer un ticket', sigma: 'Règle Sigma',
    verdicts: { prevented: 'Prévenu', alerted: 'Alerté', logged: 'Journalisé (non alerté)', no_telemetry: 'Aucune télémétrie', not_tested: 'Non testé' },
    deltaUnit: 'pts', loading: 'Chargement…',
  },
  en: {
    eyebrow: 'Operations', title: 'Purple exercises', sub: 'Attack ↔ Defense loop, KPIs, debrief.',
    newExo: '+ New exercise', empty: 'No Purple exercise yet.',
    cycleDoc: 'Purple Team cycle — 6 phases & entities: read the methodology sheet',
    cycle: 'Purple cycle — Red → Blue → Detection loop', scenarios: 'scenarios', runs: 'run(s)', run: 'Run',
    legDet: 'Detected', legPart: 'Partial', legGap: 'Blind spot', noAudit: 'No audit',
    editExo: 'Edit exercise', editSteps: 'Edit steps', addStep: 'Add a step',
    noSteps: 'No tested step on this exercise.',
    delExo: 'Delete', delExoConfirm: 'Delete exercise “{nom}”? This action is logged.',
    cov: 'Cov.', exec: 'played', detN: 'detected', prev: 'prevented', logged: 'logged',
    gapsSg: 'blind spot', gapsPl: 'blind spots', mttrResp: 'MTTR response', mttrRem: 'MTTR remediation',
    posture: 'Posture breakdown', testedN: 'tested steps',
    pPrev: 'Prevention', pAlert: 'Alerting', pLog: 'Logged', pBlind: 'Blind spot',
    tacKpi: 'Coverage by MITRE tactic', killchain: 'kill-chain order',
    covered: 'covered', gap: 'blind spot', partial: 'partial', noTac: 'Unmapped',
    remLabel: 'Purple — Remediation', remLinked: 'Linked remediation', advance: 'Advance',
    editTicket: 'Edit', createTicket: 'Create ticket', sigma: 'Sigma rule',
    verdicts: { prevented: 'Prevented', alerted: 'Alerted', logged: 'Logged (not alerted)', no_telemetry: 'No telemetry', not_tested: 'Not tested' },
    deltaUnit: 'pts', loading: 'Loading…',
  },
}
const L = computed(() => DICT[locale.value === 'en' ? 'en' : 'fr'])
const tr = (k) => L.value[k] ?? k

// Le panneau pédagogique « Cycle Purple Team — 6 phases & entités » vit désormais
// dans la Bibliothèque (article corpus `corp-mgr-cycle-purple`, seedé) : la page
// garde un simple lien d'ancrage contextuel vers l'article (motif §4.6 de la DA).
const CYCLE_ARTICLE_SLUG = 'corp-mgr-cycle-purple'

// ── Verdicts / états (miroir de la spec §2 et de la maquette) ────────────────
const VERDICT_TONE = { prevented: 'green', alerted: 'green', logged: 'amber', no_telemetry: 'red', not_tested: 'gray' }
function verdictLabel(v) { return L.value.verdicts[v] || v }
// Statut de ticket « remédié » dans CETTE app = 'clos' (STATUT_GEN : ouvert→en_cours→traite→clos).
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
function sigmaStub(step) {
  return `title: Detection — ${step.technique}\nstatus: experimental\nlogsource:\n  category: process_creation\ndetection:\n  selection:\n    Technique: ${step.technique}\n  condition: selection\nlevel: high`
}

// ── Format temps ─────────────────────────────────────────────────────────────
function parseTs(v) { if (!v) return null; const t = new Date(v).getTime(); return isNaN(t) ? null : t }
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
const d3Arr = (v) => (Array.isArray(v) ? v : (v ? [v] : []))
const normTech = (s) => String(s || '').split('.')[0]

// ── État & chargement ────────────────────────────────────────────────────────
const loading = ref(true)
const error = ref(null)
const exos = ref([])
const audits = ref([])
const orgs = ref([])
const tickets = ref([])
const stepsByExo = reactive({})   // exoId -> [step]
const obsByStep = reactive({})    // stepId -> [obs]
const tacMap = reactive({})       // technique ext_id -> tactic label
const tacOrder = reactive({})     // tactic label -> index (kill-chain)

const cycleOpen = reactive({})    // exoId -> bool (défaut : dernier run ouvert)
const remOpen = reactive({})      // "exoId:ordre" -> bool

const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))
const orgName = (id) => orgs.value.find((o) => o.id === id)?.nom || ''

async function loadAll() {
  loading.value = true; error.value = null
  try {
    const [ex, au, og, tk, mx] = await Promise.all([
      api.list('exercices').then(unwrap),
      api.list('audits').then(unwrap).catch(() => []),
      api.list('organisations').then(unwrap).catch(() => []),
      api.list('tickets').then(unwrap).catch(() => []),
      api.get('/analytics/attack-matrix').catch(() => null),
    ])
    exos.value = ex; audits.value = au; orgs.value = og; tickets.value = tk
    buildTacMap(mx)
    // Étapes de chaque exercice, puis observations de chaque étape (en parallèle).
    const stepLists = await Promise.all(
      ex.map((e) => api.list('attack_steps', `?exercise_id=${e.id}`).then(unwrap).catch(() => []))
    )
    ex.forEach((e, i) => { stepsByExo[e.id] = stepLists[i].slice().sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0)) })
    const allSteps = stepLists.flat()
    const obsLists = await Promise.all(
      allSteps.map((s) => api.list('observations', `?attack_step_id=${s.id}`).then(unwrap).catch(() => []))
    )
    allSteps.forEach((s, i) => { obsByStep[s.id] = obsLists[i] })
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? t('common.forbidden') : (e.message || 'Erreur')
  } finally {
    loading.value = false
  }
}

function buildTacMap(matrix) {
  for (const k of Object.keys(tacMap)) delete tacMap[k]
  for (const k of Object.keys(tacOrder)) delete tacOrder[k]
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

// ── Agrégation par exercice (KPI mesurés) ────────────────────────────────────
function buildCycle(exo) {
  const raw = stepsByExo[exo.id] || []
  const steps = raw.map((st) => {
    const ticket = tickets.value.find((tk) => tk.source_attack_step_id === st.id) || null
    const obs = obsByStep[st.id] || []
    const state = stepState(st, ticket)
    return { ...st, obs, ticket, state, tac: techTac(st.technique) }
  })
  const tested = steps.filter((s) => s.state !== 'untested')
  const prevented = steps.filter((s) => s.verdict === 'prevented').length
  const alerted = steps.filter((s) => s.verdict === 'alerted').length
  const logged = tested.filter((s) => s.verdict === 'logged').length
  const blind = tested.filter((s) => s.verdict === 'no_telemetry').length
  const detected = prevented + alerted
  const gaps = steps.filter((s) => s.state === 'gap').length
  const nTested = tested.length
  const detPct = nTested ? Math.round(detected / nTested * 100) : 0

  // MTTD / MTTR (sur étapes alertées horodatées) + MTTR remédiation (tickets validés).
  const dDet = [], dResp = [], dRem = []
  steps.forEach((s) => {
    if (s.verdict === 'alerted') {
      const a = tsDeltaMin(s.horodatage, s.horodatage_detection); if (a != null) dDet.push(a)
      const b = tsDeltaMin(s.horodatage_detection, s.horodatage_reponse); if (b != null) dResp.push(b)
    }
  })
  steps.forEach((s) => {
    const tk = s.ticket
    if (tk && tk.statut === TICKET_DONE && tk.valide_le) {
      const anchor = tk.gap_decouvert_le || s.horodatage || exo.date
      const d = tsDeltaMin(anchor, tk.valide_le); if (d != null) dRem.push(d)
    }
  })
  const mean = (a) => (a.length ? Math.round(a.reduce((s, x) => s + x, 0) / a.length) : null)

  // Couverture par tactique (kill-chain).
  const tm = {}
  tested.forEach((s) => {
    const id = s.tac || '—'
    const e = tm[id] || (tm[id] = { id, det: 0, tot: 0 })
    e.tot++
    if (s.state === 'prevented' || s.state === 'alerted' || s.state === 'covered') e.det++
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

const exoGroups = computed(() => {
  const cycles = exos.value.map(buildCycle)
  const groups = {}
  cycles.forEach((c) => { const aid = c.exo.audit_id || '__none__'; (groups[aid] || (groups[aid] = [])).push(c) })
  return Object.keys(groups).map((aid) => {
    const aud = aid !== '__none__' ? audits.value.find((a) => a.id === aid) : null
    const runs = groups[aid].slice().sort((a, b) =>
      String(a.exo.date || '').localeCompare(String(b.exo.date || '')) || String(a.exo.id).localeCompare(String(b.exo.id)))
    runs.forEach((r, i) => { r.runNo = i + 1; r.isLast = i === runs.length - 1; r.delta = i > 0 ? (r.detPct - runs[i - 1].detPct) : null })
    return { aid, auditNom: aud ? aud.nom : tr('noAudit'), client: aud ? orgName(aud.client_id) : '', runs }
  }).sort((a, b) => String(a.auditNom).localeCompare(String(b.auditNom)))
})

function exoIsOpen(id, dflt) { return id in cycleOpen ? cycleOpen[id] : !!dflt }
function toggleExo(id, dflt) { cycleOpen[id] = !exoIsOpen(id, dflt) }
const remKey = (exoId, ordre) => `${exoId}:${ordre}`
function toggleRem(k) { remOpen[k] = !remOpen[k] }

// ── Édition inline (drawers) ─────────────────────────────────────────────────
const form = ref(null)
const stepsExo = ref(null) // exercice dont on édite les étapes (drawer)
function openSteps(exo) { stepsExo.value = exo }
function newExo() { form.value = { entity: 'exercices', record: {}, hidden: [], prefill: {} } }
function editExo(exo) { form.value = { entity: 'exercices', record: exo, hidden: [], prefill: {} } }
async function delExo(exo) {
  if (!window.confirm(tr('delExoConfirm').replace('{nom}', exo.nom || exo.id))) return
  try { await api.remove('exercices', exo.id); await loadAll() }
  catch (e) { error.value = e instanceof ApiError && e.status === 403 ? t('common.forbidden') : (e.message || 'Erreur') }
}
function addStep(exo) {
  form.value = { entity: 'attack_steps', record: {}, hidden: ['client_id', 'exercise_id'],
    prefill: { client_id: exo.client_id, exercise_id: exo.id, ordre: (stepsByExo[exo.id]?.length || 0) + 1 } }
}
function editTicket(tk) { form.value = { entity: 'tickets', record: tk, hidden: [], prefill: {} } }
// Création directe (le schéma tickets n'expose pas source_attack_step_id → EntityForm ne
// le soumettrait pas ; on crée donc le ticket lié en un appel, comme la maquette).
async function createTicket(step, exo) {
  const payload = {
    client_id: exo.client_id, source_attack_step_id: step.id, technique_attack: step.technique,
    priorite: 'P2', statut: 'ouvert', description: `Détection à créer — ${step.technique}`,
    regle_sigma: sigmaStub(step),
  }
  try { await api.create('tickets', payload); await loadAll() }
  catch (e) { error.value = e instanceof ApiError && e.status === 403 ? t('common.forbidden') : (e.message || 'Erreur') }
}
async function advanceTicket(tk) {
  const order = ['ouvert', 'en_cours', 'traite', 'clos']
  const next = order[Math.min(order.indexOf(tk.statut) + 1, order.length - 1)]
  try { await api.update('tickets', tk.id, { statut: next }); await loadAll() }
  catch (e) { error.value = e instanceof ApiError && e.status === 403 ? t('common.forbidden') : (e.message || 'Erreur') }
}
async function onSaved() { form.value = null; await loadAll() }

onMounted(loadAll)
</script>

<template>
  <div>
    <div class="head">
      <div>
        <div class="eyebrow">{{ tr('eyebrow') }}</div>
        <h1>{{ tr('title') }}</h1>
        <p class="subtitle">{{ tr('sub') }}</p>
      </div>
      <button class="btn btn-primary" @click="newExo">{{ tr('newExo') }}</button>
    </div>

    <p v-if="loading" class="muted">{{ tr('loading') }}</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <p v-else-if="!exos.length" class="muted">{{ tr('empty') }}</p>

    <template v-else>
      <!-- Fiche méthodo du cycle : déportée dans la Bibliothèque (ancrage ?open=slug) -->
      <RouterLink class="cycle-doc" :to="`/bibliotheque?open=${CYCLE_ARTICLE_SLUG}`">
        <span class="cd-ic">📖</span>{{ tr('cycleDoc') }} →
      </RouterLink>

      <!-- Cycle Purple -->
      <section class="panel">
        <div class="panel-head" style="flex-wrap:wrap;gap:8px">
          <span class="panel-title">{{ tr('cycle') }}</span>
          <span class="spacer"></span>
          <div class="cyc-legend">
            <span class="lz"><span class="cyc-lb stv-det"></span>{{ tr('legDet') }}</span>
            <span class="lz"><span class="cyc-lb stv-cov"></span>{{ tr('legPart') }}</span>
            <span class="lz"><span class="cyc-lb stv-gap"></span>{{ tr('legGap') }}</span>
          </div>
        </div>
        <div class="panel-body">
          <div v-for="g in exoGroups" :key="g.aid" class="cyc-group">
            <div class="cyc-group-head">
              <span class="cyc-group-title">{{ g.auditNom }}</span>
              <span v-if="g.client" class="muted" style="font-size:11.5px">{{ g.client }}</span>
              <span class="k-chip k-gray sm">{{ g.runs.length }} {{ tr('runs') }}</span>
              <span class="cyc-group-line"></span>
            </div>

            <div v-for="c in g.runs" :key="c.exo.id" class="cyc-sc" :class="{ open: exoIsOpen(c.exo.id, c.isLast) }">
              <div class="cyc-head" role="button" tabindex="0"
                   @click="toggleExo(c.exo.id, c.isLast)" @keydown.enter.prevent="toggleExo(c.exo.id, c.isLast)" @keydown.space.prevent="toggleExo(c.exo.id, c.isLast)">
                <span class="cyc-chev">▸</span>
                <span class="k-chip k-violet sm">{{ tr('run') }} {{ c.runNo }}</span>
                <span class="cyc-name">{{ c.exo.nom }}</span>
                <div class="cyc-kpis">
                  <span v-if="c.delta !== null" class="k-chip sm" :class="'k-' + (c.delta > 0 ? 'green' : (c.delta < 0 ? 'red' : 'gray'))">
                    {{ (c.delta > 0 ? '▲ +' : (c.delta < 0 ? '▼ ' : '')) + c.delta }} {{ tr('deltaUnit') }}
                  </span>
                  <span class="k-chip sm" :class="'k-' + (c.detPct >= 75 ? 'green' : (c.detPct >= 50 ? 'amber' : 'red'))"><span class="dot"></span>{{ tr('cov') }} {{ c.detPct }}%</span>
                  <span class="k-chip sm" :class="c.execRate >= 70 ? 'k-gray' : 'k-amber'">{{ tr('exec') }} {{ c.execTested }}/{{ c.execTotal }} · {{ c.execRate }}%</span>
                  <span class="k-chip k-green sm">{{ c.detected }}/{{ c.tested }} {{ tr('detN') }}</span>
                  <span v-if="c.prevention > 0" class="k-chip k-green sm">{{ c.prevention }}% {{ tr('prev') }}</span>
                  <span v-if="c.logged > 0" class="k-chip k-amber sm">{{ c.logged }} {{ tr('logged') }}</span>
                  <span class="k-chip sm" :class="c.gaps ? 'k-red' : 'k-gray'">{{ c.gaps }} {{ c.gaps > 1 ? tr('gapsPl') : tr('gapsSg') }}</span>
                  <span v-if="c.mttd !== null" class="k-chip sm" :class="c.mttdN < 3 ? 'k-amber' : 'k-gray'">MTTD {{ fmtDur(c.mttd) }}{{ c.mttdN < 3 ? ' · n=' + c.mttdN : '' }}</span>
                  <span v-if="c.mttrResp !== null" class="k-chip sm" :class="c.mttrRespN < 3 ? 'k-amber' : 'k-gray'">{{ tr('mttrResp') }} {{ fmtDur(c.mttrResp) }}{{ c.mttrRespN < 3 ? ' · n=' + c.mttrRespN : '' }}</span>
                  <span v-if="c.mttrRem !== null" class="k-chip sm" :class="c.mttrRemN < 3 ? 'k-amber' : 'k-gray'">{{ tr('mttrRem') }} {{ fmtDur(c.mttrRem) }}{{ c.mttrRemN < 3 ? ' · n=' + c.mttrRemN : '' }}</span>
                  <span v-if="c.exo.tlp" class="k-chip k-gray sm">TLP:{{ c.exo.tlp }}</span>
                </div>
                <div class="cyc-tacmini">
                  <span v-for="tt in c.tactics" :key="tt.id" class="cyc-tmb" :class="stvClass(tt.state)" :title="`${tt.label} · ${tt.det}/${tt.tot}`"></span>
                </div>
              </div>

              <div v-show="exoIsOpen(c.exo.id, c.isLast)" class="cyc-body">
                <div class="cyc-toolbar">
                  <span class="spacer"></span>
                  <button class="exo-tbtn" @click="editExo(c.exo)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20h4L19 9l-4-4L4 16v4Z"/><path d="M14 6l4 4"/></svg>
                    {{ tr('editExo') }}
                  </button>
                  <button class="exo-tbtn" @click="openSteps(c.exo)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16M4 12h16M4 18h10"/></svg>
                    {{ tr('editSteps') }}
                  </button>
                  <button class="exo-tbtn" @click="addStep(c.exo)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
                    {{ tr('addStep') }}
                  </button>
                  <button class="exo-tbtn danger" @click="delExo(c.exo)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 7h14M9 7V5h6v2M7 7l1 13h8l1-13"/></svg>
                    {{ tr('delExo') }}
                  </button>
                </div>

                <p v-if="!c.steps.length" class="muted" style="font-size:12.5px">{{ tr('noSteps') }}</p>

                <!-- Barre de posture -->
                <div v-if="c.pTested > 0" class="pbar-wrap">
                  <div class="pbar-eyebrow eyebrow">{{ tr('posture') }} · {{ c.pTested }} {{ tr('testedN') }}</div>
                  <div class="pbar">
                    <div v-if="c.pPrev > 0" class="pseg prev" :style="{ flexGrow: c.pPrev }">{{ Math.round(c.pPrev / c.pTested * 100) }}%</div>
                    <div v-if="c.pAlert > 0" class="pseg alrt" :style="{ flexGrow: c.pAlert }">{{ Math.round(c.pAlert / c.pTested * 100) }}%</div>
                    <div v-if="c.pLog > 0" class="pseg logd" :style="{ flexGrow: c.pLog }">{{ Math.round(c.pLog / c.pTested * 100) }}%</div>
                    <div v-if="c.pBlind > 0" class="pseg blnd" :style="{ flexGrow: c.pBlind }">{{ Math.round(c.pBlind / c.pTested * 100) }}%</div>
                  </div>
                  <div class="pbar-legend">
                    <span class="pleg prev">{{ tr('pPrev') }} <b>{{ c.pPrev }}/{{ c.pTested }}</b></span>
                    <span class="pleg alrt">{{ tr('pAlert') }} <b>{{ c.pAlert }}/{{ c.pTested }}</b></span>
                    <span class="pleg logd">{{ tr('pLog') }} <b>{{ c.pLog }}/{{ c.pTested }}</b></span>
                    <span class="pleg blnd">{{ tr('pBlind') }} <b>{{ c.pBlind }}/{{ c.pTested }}</b></span>
                  </div>
                </div>

                <!-- Timeline d'étapes -->
                <div v-if="c.steps.length" class="cyc-tl">
                  <div v-for="s in c.steps" :key="s.id" class="cyc-step">
                    <div class="cyc-row">
                      <div class="cyc-bead" :class="stvClass(s.state)">{{ s.ordre }}</div>
                      <div class="cyc-main">
                        <span class="mono-cell">{{ s.technique || '—' }}</span>
                        <span class="cell-strong">{{ s.titre }}</span>
                        <span class="k-chip" :class="'k-' + (VERDICT_TONE[s.verdict] || 'gray')"><span class="dot"></span>{{ verdictLabel(s.verdict) }}</span>
                        <span v-for="o in s.obs" :key="o.id" class="k-chip k-gray"><span class="dot"></span>{{ o.source || '—' }}{{ o.resultat ? ' · ' + verdictLabel(o.resultat) : '' }}</span>
                        <span class="cyc-tac">{{ (s.tac || tr('noTac')) }} · {{ fmtTs(s.horodatage) }}</span>
                      </div>
                    </div>

                    <!-- Remédiation (angle mort ou journalisé non alerté) -->
                    <div v-if="s.state === 'gap' || s.state === 'logged'" class="cyc-rem">
                      <span class="cyc-rl">{{ tr('remLabel') }}</span>
                      <template v-if="s.ticket">
                        <span class="k-chip" :class="'k-' + ticketStatutTone(s.ticket.statut)"><span class="dot"></span>{{ s.ticket.statut }}</span>
                        <span v-for="m in d3Arr(s.ticket.mesure_d3fend)" :key="m" class="k-chip k-cyan">{{ m }}</span>
                        <span v-if="s.ticket.priorite" class="k-chip" :class="'k-' + prioTone(s.ticket.priorite)">{{ s.ticket.priorite }}</span>
                        <button v-if="s.ticket.statut !== 'clos'" class="btn slim" @click="advanceTicket(s.ticket)">{{ tr('advance') }}</button>
                        <button class="btn slim" @click="editTicket(s.ticket)">{{ tr('editTicket') }}</button>
                        <details v-if="s.ticket.regle_sigma" class="sig"><summary>{{ tr('sigma') }}</summary><pre class="sigma">{{ s.ticket.regle_sigma }}</pre></details>
                      </template>
                      <button v-else class="btn btn-primary slim" @click="createTicket(s, c.exo)">{{ tr('createTicket') }}</button>
                    </div>

                    <!-- Remédiation liée (repliée) quand l'étape est prise en charge -->
                    <div v-else-if="s.ticket">
                      <div class="cyc-tog"><button class="lk" @click="toggleRem(remKey(c.exo.id, s.ordre))">{{ (remOpen[remKey(c.exo.id, s.ordre)] ? '▾ ' : '▸ ') + tr('remLinked') }} (1)</button></div>
                      <div v-show="remOpen[remKey(c.exo.id, s.ordre)]" class="cyc-rem">
                        <span class="cyc-rl">{{ tr('remLabel') }}</span>
                        <span class="k-chip" :class="'k-' + ticketStatutTone(s.ticket.statut)"><span class="dot"></span>{{ s.ticket.statut }}</span>
                        <span v-for="m in d3Arr(s.ticket.mesure_d3fend)" :key="m" class="k-chip k-cyan">{{ m }}</span>
                        <span v-if="s.ticket.priorite" class="k-chip" :class="'k-' + prioTone(s.ticket.priorite)">{{ s.ticket.priorite }}</span>
                        <button class="btn slim" @click="editTicket(s.ticket)">{{ tr('editTicket') }}</button>
                      </div>
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
                        <span class="cyc-tbead"></span>
                        <span class="cyc-tfrac">{{ tt.det }}/{{ tt.tot }}</span>
                        <span class="cyc-tlbl">{{ tt.state === 'detected' ? tr('covered') : (tt.state === 'gap' ? tr('gap') : tr('partial')) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </template>

    <EntityForm
      v-if="form"
      :entity="form.entity"
      :fields="fieldsFor(form.entity)"
      :record="form.record && form.record.id ? form.record : null"
      :prefill="form.prefill"
      :hidden="form.hidden"
      :title="(form.record && form.record.id ? 'Modifier' : 'Nouveau') + ' — ' + form.entity"
      @saved="onSaved"
      @close="form = null"
    />

    <!-- Éditeur des étapes (drawer) : rechargement de l'agrégat à chaque modification. -->
    <ExoStepsDrawer
      v-if="stepsExo"
      :exercise="stepsExo"
      @changed="loadAll"
      @close="stepsExo = null"
    />
  </div>
</template>

<style scoped>
.head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px}
.subtitle{font-size:13px;color:var(--muted);margin:2px 0 0}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);margin-bottom:14px}
.panel-head{display:flex;align-items:center;gap:11px;padding:12px 16px;border-bottom:1px solid var(--border-2)}
.panel-title{font-family:var(--font-display);font-size:15px;font-weight:600;color:var(--heading)}
.panel-body{padding:14px 16px}
.spacer{flex:1}
.muted{color:var(--muted)}
.mono-cell{font-family:var(--font-data);font-size:10.5px;color:var(--cyan)}
.cell-strong{font-weight:600;color:var(--heading)}

/* Puces (tons doux) — indépendantes des variantes globales de chip. */
.k-chip{display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 9px;border-radius:var(--r-pill,999px);
  font-family:var(--font-data);font-size:11px;font-weight:500;border:1px solid transparent;white-space:nowrap;color:var(--muted)}
.k-chip.sm{height:19px;font-size:10px;padding:0 7px}
.k-chip .dot{width:6px;height:6px;border-radius:50%;background:currentColor;flex:0 0 auto}
.k-green{background:var(--c-green-bg);border-color:var(--c-green-bd);color:var(--c-green-tx)}
.k-red{background:var(--c-red-bg);border-color:var(--c-red-bd);color:var(--c-red-tx)}
.k-amber{background:var(--c-amber-bg);border-color:var(--c-amber-bd);color:var(--c-amber-tx)}
.k-cyan{background:var(--c-cyan-bg);border-color:var(--c-cyan-bd);color:var(--c-cyan-tx)}
.k-blue{background:var(--c-blue-bg);border-color:var(--c-blue-bd);color:var(--c-blue-tx)}
.k-violet{background:var(--c-violet-bg);border-color:var(--c-violet-bd);color:var(--c-violet-tx)}
.k-gray{background:var(--c-gray-bg);border-color:var(--c-gray-bd);color:var(--c-gray-tx)}

/* Lien vers la fiche méthodo du cycle (Bibliothèque) */
.cycle-doc{display:inline-flex;align-items:center;gap:7px;margin-bottom:12px;font-size:12.5px;
  color:var(--violet-accent);text-decoration:none;border:1px dashed var(--c-violet-bd);
  border-radius:var(--r-pill,999px);padding:5px 13px;background:var(--c-violet-bg)}
.cycle-doc:hover{border-style:solid}
.cycle-doc .cd-ic{font-size:13px}

/* Cycle Purple — timeline + KPI par tactique */
.stv-det{--stb:var(--c-green-bg);--std:var(--c-green-bd);--stt:var(--c-green-tx)}
.stv-gap{--stb:var(--c-red-bg);--std:var(--c-red-bd);--stt:var(--c-red-tx)}
.stv-cov{--stb:var(--c-amber-bg);--std:var(--c-amber-bd);--stt:var(--c-amber-tx)}
.stv-prev{--stb:var(--c-green-bg);--std:var(--c-green-bd);--stt:var(--c-green-tx)}
.stv-part{--stb:var(--c-amber-bg);--std:var(--c-amber-bd);--stt:var(--c-amber-tx)}
.stv-untested{--stb:transparent;--std:var(--border-2);--stt:var(--muted)}
.cyc-legend{display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-family:var(--font-data);font-size:10.5px;color:var(--muted)}
.cyc-legend .lz{display:inline-flex;align-items:center;gap:5px}
.cyc-lb{width:9px;height:9px;border-radius:50%;border:2px solid var(--std);background:var(--stb)}
.cyc-group{margin-bottom:18px}
.cyc-group:last-child{margin-bottom:0}
.cyc-group-head{display:flex;align-items:center;gap:9px;padding:2px 2px 10px;flex-wrap:wrap}
.cyc-group-title{font-family:var(--font-display);font-size:13.5px;font-weight:600;color:var(--heading)}
.cyc-group-line{flex:1;height:1px;background:var(--border-2);min-width:16px}
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
.cyc-tmb{width:15px;height:15px;border-radius:50%;border:2px solid var(--std);background:var(--stb)}
.cyc-body{padding:6px 14px 14px;border-top:1px solid var(--border-2)}
.cyc-toolbar{display:flex;align-items:center;gap:6px;margin-bottom:8px}
.cyc-tl{display:flex;flex-direction:column;margin-top:8px}
.cyc-step{border-left:2px solid var(--border-2);margin-left:13px;position:relative}
.cyc-row{display:flex;align-items:center;gap:9px;padding:8px 2px 8px 15px;position:relative}
.cyc-bead{position:absolute;left:-9px;top:8px;width:16px;height:16px;border-radius:50%;border:2px solid var(--std);background:var(--stb);color:var(--stt);font-family:var(--font-data);font-size:9px;font-weight:600;display:flex;align-items:center;justify-content:center}
.cyc-main{flex:1;min-width:0;display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.cyc-tac{font-family:var(--font-data);font-size:10.5px;color:var(--faint);margin-left:auto;white-space:nowrap}
.cyc-rem{margin:0 0 8px 15px;padding:8px 11px;border:1px dashed var(--c-violet-bd);border-radius:10px;background:var(--c-violet-bg);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.cyc-rl{font-family:var(--font-eyebrow);font-size:9.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--c-violet-tx)}
.cyc-tog{margin:0 0 8px 15px}
.cyc-tog .lk{background:none;border:0;padding:0;font-family:inherit;font-size:11.5px;color:var(--violet-accent);cursor:pointer}
.cyc-tog .lk:hover{text-decoration:underline}
.sig summary{cursor:pointer;list-style:none;color:var(--violet-accent);font-size:11.5px;font-weight:600}
.sig summary::-webkit-details-marker{display:none}
.sigma{font-family:var(--font-data);font-size:10.5px;background:var(--surface-2);border:1px solid var(--border-2);border-radius:8px;padding:9px 11px;overflow-x:auto;white-space:pre;color:var(--muted);margin:6px 0 0;line-height:1.4}
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

/* Barre de posture */
.pbar-wrap{margin-bottom:14px}
.pbar-eyebrow{margin-bottom:8px}
.pbar{display:flex;height:34px;border-radius:8px;overflow:hidden;border:1px solid var(--border-2)}
.pseg{display:flex;align-items:center;justify-content:center;min-width:0;flex-basis:0;font-family:var(--font-data);font-size:11px;font-weight:600;background:var(--c-bg);color:var(--c-tx)}
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
.eyebrow{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10.5px;color:var(--muted);font-weight:var(--eyebrow-weight)}
.slim{padding:4px 9px;font-size:12px}
.btn.danger{color:var(--red);border-color:var(--c-red-bd)}
.err{color:var(--red)}
/* Boutons de la barre d'outils — thème « ghost » de la maquette (DA §0.3) :
   fond transparent, texte discret, icône 14px, survol posé sur surface-2. */
.exo-tbtn{display:inline-flex;align-items:center;gap:7px;height:28px;padding:0 10px;border-radius:8px;
  font-family:inherit;font-size:11.5px;font-weight:600;border:1px solid transparent;background:transparent;
  color:var(--muted);cursor:pointer;transition:background var(--t-fast,.14s),color var(--t-fast,.14s)}
.exo-tbtn:hover{background:var(--surface-2);color:var(--text)}
.exo-tbtn:active{transform:translateY(1px)}
.exo-tbtn svg{width:14px;height:14px;flex:0 0 auto}
.exo-tbtn.danger{color:var(--muted)}
.exo-tbtn.danger:hover{background:var(--c-red-bg);color:var(--c-red-tx)}
</style>
