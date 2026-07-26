<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import EntityTable from '../components/EntityTable.vue'
import ExercicesStats from '../components/ExercicesStats.vue'
import ExerciceDrawer from '../components/ExerciceDrawer.vue'
import RefacSelect from '../components/RefacSelect.vue'
import { useLabels } from '../composables/useLabels'
import { useOrgNames } from '../composables/useOrgNames'
import { STATUT_EXO_TONE } from '../tones'
import { api, ApiError } from '../api/client'

// Page « Exercices Purple » — même composition que les Scénarios de menace :
// en-tête d'actions + note contextuelle + panneau de filtres repliable + bande KPI
// + tableau. Chaque ligne est un exercice/RUN (purple_exercise). La vue « groupée »
// (par défaut) replie les RUNs successifs d'un même audit sur le RUN courant ; le
// tiroir de lecture déroule tout l'historique + le tableau de bord de posture.
const { t, locale } = useI18n()
const { enumLabel } = useLabels()
const { preload: preloadOrgs, orgName } = useOrgNames()

const STATUTS = ['planifie', 'en_cours', 'termine', 'suspendu', 'annule']
const TLPS = ['RED', 'AMBER', 'GREEN', 'CLEAR']

// Références : le tableau détient les lignes ; KPI et options de filtre en dérivent.
const tableRef = ref(null)
const allRows = computed(() => tableRef.value?.rows ?? [])
function refreshAll() { tableRef.value?.load() }

// Lookups audit/application (résolution Application + Audit des colonnes dérivées).
const auditById = ref({})
const appById = ref({})
const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))
async function loadLookups() {
  const [auds, apps] = await Promise.all([
    api.list('audits').then(unwrap).catch(() => []),
    api.list('applications').then(unwrap).catch(() => []),
  ])
  const am = {}; for (const a of auds) am[a.id] = a; auditById.value = am
  const pm = {}; for (const a of apps) pm[a.id] = a; appById.value = pm
}
function appLabelsForAudit(auditId) {
  const aud = auditById.value[auditId]
  const ids = aud?.applications || []
  return ids.map((id) => appById.value[id]?.nom || appById.value[id]?.code).filter(Boolean)
}
function appText(r) { const l = appLabelsForAudit(r.audit_id); return l.length ? l.join(', ') : '—' }
function auditNom(r) { return auditById.value[r.audit_id]?.nom || '—' }

// État de filtre local + filtrage client-side (aucun paramètre envoyé à l'API).
const showFilters = ref(false)
const grouped = ref(true)
const q = ref('')
const fStatut = ref([])
const fTlp = ref([])
const fClient = ref([])
const fApp = ref([])

function toggleIn(arr, val) { const i = arr.indexOf(val); if (i === -1) arr.push(val); else arr.splice(i, 1) }

const activeFilterCount = computed(() =>
  (fStatut.value.length ? 1 : 0) + (fTlp.value.length ? 1 : 0) +
  (fClient.value.length ? 1 : 0) + (fApp.value.length ? 1 : 0))

// Options {id,label} pour l'autocomplétion (RefacSelect) — id = valeur filtrée
// (nom client / libellé application), cohérent avec baseFilter.
const clientOptions = computed(() => {
  const set = new Set()
  for (const r of allRows.value) { const n = orgName(r.client_id); if (n) set.add(n) }
  return [...set].sort((a, b) => a.localeCompare(b)).map((n) => ({ id: n, label: n }))
})
// Application dépend du Client : si des clients sont sélectionnés, on ne propose que
// les applications de leurs exercices (filtre en cascade).
const appOptions = computed(() => {
  const set = new Set()
  for (const r of allRows.value) {
    if (fClient.value.length && !fClient.value.includes(orgName(r.client_id))) continue
    for (const a of appLabelsForAudit(r.audit_id)) set.add(a)
  }
  return [...set].sort((a, b) => a.localeCompare(b)).map((n) => ({ id: n, label: n }))
})
// Quand le périmètre client change, on élague les applications sélectionnées devenues
// hors périmètre (sinon elles filtreraient à vide).
watch(fClient, () => {
  const valid = new Set(appOptions.value.map((o) => o.id))
  fApp.value = fApp.value.filter((a) => valid.has(a))
}, { deep: true })

const normTlp = (v) => (v === 'WHITE' ? 'CLEAR' : v)
// Filtre par ligne/RUN (recherche + facettes), avant tout regroupement.
function baseFilter(r) {
  const needle = q.value.trim().toLowerCase()
  if (needle) {
    const hay = `${orgName(r.client_id) || ''} ${appText(r)} ${auditNom(r)} ${r.nom || ''}`.toLowerCase()
    if (!hay.includes(needle)) return false
  }
  if (fStatut.value.length && !fStatut.value.includes(r.statut)) return false
  if (fTlp.value.length && !fTlp.value.includes(normTlp(r.tlp))) return false
  if (fClient.value.length && !fClient.value.includes(orgName(r.client_id))) return false
  if (fApp.value.length) {
    const labels = appLabelsForAudit(r.audit_id)
    if (!labels.some((a) => fApp.value.includes(a))) return false
  }
  return true
}

// Regroupement par exercice : parmi les lignes filtrées, on ne garde que le RUN courant
// (run_number max) de chaque audit. `currentRunIds` = ids visibles en mode groupé.
const currentRunIds = computed(() => {
  if (!grouped.value) return null
  const byAudit = {}
  for (const r of allRows.value) {
    if (!baseFilter(r)) continue
    const k = r.audit_id || r.id
    if (!byAudit[k] || (r.run_number ?? 0) > (byAudit[k].run_number ?? 0)) byAudit[k] = r
  }
  return new Set(Object.values(byAudit).map((r) => r.id))
})

const filterFn = (r) => {
  if (!baseFilter(r)) return false
  if (grouped.value && currentRunIds.value && !currentRunIds.value.has(r.id)) return false
  return true
}

// Lignes visibles (KPI) + total RUNs sous-jacents (pied de carte « Exercices »).
const filteredRows = computed(() => allRows.value.filter(filterFn))
const runsTotal = computed(() => allRows.value.filter(baseFilter).length)

// Colonnes : Client, Application (dérivée de l'audit), Audit, RUN (+ badge n runs),
// Statut (pill), TLP (pastille), Création (date + heure + fuseau).
const cols = computed(() => [
  { key: 'client_id', label: 'Client', org: true },
  { key: '_app', label: 'Application', get: (r) => appText(r) },
  { key: '_audit', label: 'Audit', get: (r) => auditNom(r) },
  {
    key: 'run_number', label: 'RUN', pill: () => 'violet', center: true,
    get: (r) => `RUN ${r.run_number ?? '—'}`,
  },
  { key: 'statut', label: 'Statut', pill: (v) => STATUT_EXO_TONE[v] || 'gray', format: enumLabel, center: true },
  { key: 'created_at', label: 'Création', date: true, center: true },
])

// --- Téléchargement : rapport PDF d'exercice (pipeline livrables). ---
const msg = ref(null)
async function downloadReport(r) {
  msg.value = null
  try {
    const gen = await api.post('/deliverables/generate', {
      client_id: r.client_id, audit_id: r.audit_id, type: 'exercice',
      langue: locale.value === 'en' ? 'en' : 'fr', tlp: r.tlp || 'AMBER',
    })
    const dl = await api.get(`/deliverables/${gen.id}/download`)
    if (dl?.url) {
      const a = document.createElement('a')
      a.href = dl.url; a.download = dl.filename || `exercice-${r.id}.pdf`; a.target = '_blank'; a.rel = 'noopener'
      a.click()
    }
  } catch (e) {
    msg.value = e instanceof ApiError && e.status === 403
      ? t('views.exercices.download_denied')
      : (e instanceof ApiError && e.status === 503 ? t('views.exercices.download_unavailable') : (e.message || 'Erreur.'))
  }
}

const extraActions = computed(() => [
  { label: t('views.exercices.download'), icon: 'download', fn: downloadReport },
])

onMounted(() => { preloadOrgs(); loadLookups() })
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.exercices.eyebrow') }}</div>
    <h1>{{ t('views.exercices.title') }}</h1>
    <div class="subrow">
      <p class="subtitle">{{ t('views.exercices.subtitle') }}</p>
      <label class="search">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/></svg>
        <input v-model="q" type="search" :placeholder="t('views.exercices.search_ph')" />
      </label>
    </div>
    <!-- Boutons d'action alignés juste sous le champ de recherche. -->
    <div class="acts">
      <button class="group-toggle" :class="{ on: grouped }" @click="grouped = !grouped"
              :title="t('views.exercices.group_hint')" :aria-pressed="grouped">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M4 12h16M4 17h10"/></svg>
        {{ t('views.exercices.group') }}
        <svg v-if="grouped" class="chk" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6 9 17l-5-5"/></svg>
      </button>
      <button class="filters-toggle" :class="{ open: showFilters }" @click="showFilters = !showFilters">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="10" y1="18" x2="14" y2="18"/></svg>
        {{ t('views.exercices.filters') }}
        <span v-if="activeFilterCount" class="count-badge sm">{{ activeFilterCount }}</span>
        <span class="chevron">{{ showFilters ? '⌃' : '⌄' }}</span>
      </button>
      <button class="btn btn-primary" @click="tableRef?.openCreate()">+ {{ t('common.new') }}</button>
      <button class="icon-btn" :title="t('common.refresh')" :aria-label="t('common.refresh')" @click="refreshAll">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
      </button>
    </div>
    <div class="note">
      <span class="lead">{{ t('views.exercices.note.lead') }}</span>
      <ul>
        <li><b>{{ t('views.exercices.note.ligne_label') }}</b> {{ t('views.exercices.note.ligne_text') }}</li>
        <li><b>{{ t('views.exercices.note.cotation_label') }}</b> {{ t('views.exercices.note.cotation_text') }}</li>
      </ul>
    </div>
    <p v-if="msg" class="err">{{ msg }}</p>
    <div v-if="showFilters" class="filters-panel">
      <div class="f-row">
        <label class="f-label">{{ t('views.exercices.filter_statut') }}</label>
        <div class="chipset">
          <button v-for="s in STATUTS" :key="s" type="button" :class="['chip-toggle', { on: fStatut.includes(s) }]" @click="toggleIn(fStatut, s)">{{ enumLabel(s) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.exercices.filter_tlp') }}</label>
        <div class="chipset">
          <button v-for="l in TLPS" :key="l" type="button" :class="['chip-toggle', { on: fTlp.includes(l) }]" @click="toggleIn(fTlp, l)">{{ l }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.exercices.filter_client') }}</label>
        <RefacSelect :options="clientOptions" multiple v-model="fClient" :placeholder="t('views.exercices.filter_client_ph')" />
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.exercices.filter_app') }}</label>
        <RefacSelect :options="appOptions" multiple v-model="fApp" :placeholder="t('views.exercices.filter_app_ph')" />
      </div>
    </div>
    <ExercicesStats :rows="filteredRows" :runs-total="grouped ? runsTotal : null" />
    <EntityTable ref="tableRef" entity="exercices" :columns="cols" title="exercice"
                 action-variant="icon" :show-toolbar="false" :filter-fn="filterFn"
                 :extra-actions="extraActions" :drawer="ExerciceDrawer" />
  </div>
</template>

<style scoped>
.subrow{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:8px 0 0}
.subtitle{font-size:13px;color:var(--muted);margin:0}
.note{margin:16px 0 4px;color:var(--muted);font-size:12.5px;line-height:1.55;
  border-left:3px solid var(--violet);padding:2px 0 2px 14px;max-width:92ch}
.note .lead{color:var(--text);font-weight:500}
.note ul{margin:6px 0 0;padding-left:18px}
.note li{margin:3px 0}
.note b{color:var(--c-violet-tx);font-weight:600}
/* Boutons d'action : rangée alignée à droite, juste sous le champ de recherche. */
.acts{display:flex;gap:8px;align-items:center;justify-content:flex-end;margin-top:10px;flex-wrap:wrap}
.acts .btn{height:34px;display:inline-flex;align-items:center}
.search{display:inline-flex;align-items:center;gap:7px;height:34px;border:1px solid var(--border);
  background:var(--surface);border-radius:var(--r-pill);padding:0 12px;color:var(--faint);
  transition:border-color var(--t) var(--ease)}
.search:focus-within{border-color:var(--violet)}
.search input{border:none;background:transparent;outline:none;color:var(--text);font-size:13px;width:170px}
.search input::placeholder{color:var(--faint)}
.icon-btn{width:34px;height:34px;border:1px solid var(--border);background:var(--surface);color:var(--muted);
  border-radius:var(--r-pill);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;
  transition:border-color var(--t) var(--ease), color var(--t) var(--ease)}
.icon-btn:hover{border-color:var(--violet-accent);color:var(--violet-accent)}
/* Bascule « Grouper » : même gabarit que le filtre, actif = violet plein. */
.group-toggle{display:inline-flex;align-items:center;gap:7px;height:34px;border:1px solid var(--border);
  background:var(--surface);color:var(--muted);border-radius:var(--r-pill);padding:0 13px;font-size:13px;
  font-weight:600;cursor:pointer;transition:border-color var(--t) var(--ease), color var(--t) var(--ease)}
.group-toggle:hover{border-color:var(--violet)}
.group-toggle.on{background:var(--c-violet-bg);border-color:var(--violet);color:var(--violet-accent);font-weight:600}
.group-toggle .chk{margin-left:-1px;color:var(--violet-accent)}
.filters-toggle{display:inline-flex;align-items:center;gap:8px;height:34px;border:1px solid var(--violet);
  background:var(--c-violet-bg);color:var(--violet-accent);border-radius:var(--r-pill);
  padding:0 14px;font-size:13px;font-weight:600;cursor:pointer}
.filters-toggle .chevron{font-size:11px;margin-left:2px}
.chevron{font-size:11px}
.filters-panel{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;
  padding:16px;margin:12px 0 0;border:1px solid var(--border);border-radius:var(--r-card);background:var(--surface-2)}
.f-row{display:flex;flex-direction:column;gap:6px}
.f-label{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.chipset{display:flex;flex-wrap:wrap;gap:8px}
.chip-toggle{border:1px solid var(--border);background:var(--surface);color:var(--muted);
  border-radius:var(--r-pill);padding:6px 14px;font-size:12.5px;cursor:pointer;transition:border-color var(--t) var(--ease)}
.chip-toggle:hover{border-color:var(--violet)}
.chip-toggle.on{background:var(--c-violet-bg);border-color:var(--c-violet-bd);color:var(--c-violet-tx);font-weight:600}
.count-badge{display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:20px;
  border-radius:99px;background:var(--surface-3);color:var(--text);font-size:11px;font-family:var(--font-data);padding:0 6px;margin-left:4px}
.count-badge.sm{min-width:16px;height:16px;font-size:10px;background:var(--violet);color:#fff}
.faint.sm{font-size:12px;color:var(--faint)}
.err{color:var(--red);font-size:13px;margin:10px 0 0}
</style>
