<script setup>
import { ref, computed, onMounted } from 'vue'
import EntityTable from '../components/EntityTable.vue'
import AuditDrawer from '../components/AuditDrawer.vue'
import RefacSelect from '../components/RefacSelect.vue'
import AuditsStats from '../components/AuditsStats.vue'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'
import { fieldsFor } from '../fields'
import { api } from '../api/client'

const { t } = useI18n()
const { enumLabel } = useLabels()

// Colonnes : Organisation (client) et Application en tête, Date de début en fin.
// `th` force l'en-tête (fields.client_id vaut « Client », fields.nom « Nom »).
const cols = [
  { key: 'client_id', label: 'Organisation', org: true, th: 'views.audits.col_org' },
  { key: 'applications', label: 'Application', apps: true, th: 'views.audits.col_app' },
  { key: 'categorie', label: 'Catégorie', pill: () => 'violet' },
  { key: 'type_test', label: 'Type' },
  { key: 'statut', label: 'Statut', pill: () => 'cyan' },
  { key: 'priorite', label: 'Priorité' },
  { key: 'date_debut', label: 'Date de début', date: true },
]

// Valeurs de filtre dérivées du schéma (fields.js), comme la page Ressources — évite
// de dupliquer des listes qui vivent déjà dans le schéma d'entité.
const auditFields = fieldsFor('audits')
const CATEGORIES = (auditFields.find((f) => f.key === 'categorie')?.options || []).map((o) => o.value)
const STATUTS = auditFields.find((f) => f.key === 'statut')?.options || []
const TYPES = auditFields.find((f) => f.key === 'type_test')?.options || []
const PRIOS = auditFields.find((f) => f.key === 'priorite')?.options || []
const TLPS = ['RED', 'AMBER', 'GREEN', 'CLEAR']

// Références : EntityTable (toolbar interne masquée, actions pilotées depuis l'en-tête)
// et la section KPI (rechargée sur mutation via son reload() exposé).
const tableRef = ref(null)
const statsRef = ref(null)

// Bouton Rafraîchir : recharge le tableau ET les KPI (section découplée).
function refreshAll() {
  tableRef.value?.load()
  statsRef.value?.reload()
}

// État de filtre local + filtrage client-side (aucun paramètre envoyé à l'API de liste).
const showFilters = ref(false)
const q = ref('')
const fOrgs = ref([])
const fApps = ref([])
const fCats = ref([])
const fStatuts = ref([])
const fTypes = ref([])
const fPrios = ref([])
const fTlp = ref([])
const orgOptions = ref([])
const appOptions = ref([])

function toggleIn(arr, val) {
  const i = arr.indexOf(val)
  if (i === -1) arr.push(val); else arr.splice(i, 1)
}

const activeFilterCount = computed(() =>
  (fOrgs.value.length ? 1 : 0) + (fApps.value.length ? 1 : 0) + (fCats.value.length ? 1 : 0)
  + (fStatuts.value.length ? 1 : 0) + (fTypes.value.length ? 1 : 0)
  + (fPrios.value.length ? 1 : 0) + (fTlp.value.length ? 1 : 0))

const filterFn = (r) => {
  const needle = q.value.trim().toLowerCase()
  if (needle && !String(r.nom || '').toLowerCase().includes(needle)) return false
  if (fOrgs.value.length && !fOrgs.value.includes(r.client_id)) return false
  // applications est un tableau d'UUID : recouvrement avec la sélection.
  if (fApps.value.length && !(r.applications || []).some((a) => fApps.value.includes(a))) return false
  if (fCats.value.length && !fCats.value.includes(r.categorie)) return false
  if (fStatuts.value.length && !fStatuts.value.includes(r.statut)) return false
  if (fTypes.value.length && !fTypes.value.includes(r.type_test)) return false
  if (fPrios.value.length && !fPrios.value.includes(r.priorite)) return false
  if (fTlp.value.length && !fTlp.value.includes(r.tlp)) return false
  return true
}

onMounted(async () => {
  try {
    const rows = await api.list('organisations')
    const list = Array.isArray(rows) ? rows : (rows?.items ?? [])
    orgOptions.value = list.map((o) => ({ id: o.id, label: `${o.code || ''} ${o.nom}`.trim() }))
  } catch { orgOptions.value = [] }
  try {
    const rows = await api.list('applications')
    const list = Array.isArray(rows) ? rows : (rows?.items ?? [])
    appOptions.value = list.map((a) => ({ id: a.id, label: a.nom }))
  } catch { appOptions.value = [] }
})
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.audits.eyebrow') }}</div>
    <h1>{{ t('views.audits.title') }}</h1>
    <div class="subrow">
      <p class="subtitle">{{ t('views.audits.subtitle') }}</p>
      <div class="acts">
        <label class="search">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/></svg>
          <input v-model="q" type="search" :placeholder="t('views.audits.search_ph')" />
        </label>
        <button class="filters-toggle" :class="{ open: showFilters }" @click="showFilters = !showFilters">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="10" y1="18" x2="14" y2="18"/></svg>
          {{ t('views.audits.filters') }}
          <span v-if="activeFilterCount" class="count-badge sm">{{ activeFilterCount }}</span>
          <span class="chevron">{{ showFilters ? '⌃' : '⌄' }}</span>
        </button>
        <button class="btn btn-primary" @click="tableRef?.openCreate()">+ {{ t('common.new') }}</button>
        <button class="icon-btn" :title="t('common.refresh')" :aria-label="t('common.refresh')" @click="refreshAll">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
        </button>
      </div>
    </div>
    <div class="note">
      <span class="lead">{{ t('views.audits.note.lead') }}</span>
      <ul>
        <li><b>{{ t('views.audits.note.categories_label') }}</b> {{ t('views.audits.note.categories_text') }}</li>
        <li><b>{{ t('views.audits.note.cycle_label') }}</b> {{ t('views.audits.note.cycle_text') }}</li>
      </ul>
    </div>
    <div v-if="showFilters" class="filters-panel">
      <div class="f-row">
        <label class="f-label">{{ t('views.audits.filter_org') }}</label>
        <RefacSelect :options="orgOptions" multiple v-model="fOrgs" :placeholder="t('views.audits.filter_org_ph')" />
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.audits.filter_app') }}</label>
        <RefacSelect :options="appOptions" multiple v-model="fApps" :placeholder="t('views.audits.filter_app_ph')" />
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.audits.filter_cat') }}</label>
        <div class="chipset">
          <button v-for="c in CATEGORIES" :key="c" type="button" :class="['chip-toggle', { on: fCats.includes(c) }]" @click="toggleIn(fCats, c)">{{ enumLabel(c) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.audits.filter_statut') }}</label>
        <div class="chipset">
          <button v-for="s in STATUTS" :key="s" type="button" :class="['chip-toggle', { on: fStatuts.includes(s) }]" @click="toggleIn(fStatuts, s)">{{ enumLabel(s) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.audits.filter_type') }}</label>
        <div class="chipset">
          <button v-for="ty in TYPES" :key="ty" type="button" :class="['chip-toggle', { on: fTypes.includes(ty) }]" @click="toggleIn(fTypes, ty)">{{ enumLabel(ty) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.audits.filter_prio') }}</label>
        <div class="chipset">
          <button v-for="p in PRIOS" :key="p" type="button" :class="['chip-toggle', { on: fPrios.includes(p) }]" @click="toggleIn(fPrios, p)">{{ enumLabel(p) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.audits.filter_tlp') }}</label>
        <div class="chipset">
          <button v-for="tl in TLPS" :key="tl" type="button" :class="['chip-toggle', { on: fTlp.includes(tl) }]" @click="toggleIn(fTlp, tl)">{{ tl }}</button>
        </div>
      </div>
    </div>
    <AuditsStats ref="statsRef" :f-orgs="fOrgs" :f-apps="fApps" :f-cats="fCats" :f-statuts="fStatuts" :f-types="fTypes" :f-prios="fPrios" :f-tlp="fTlp" />
    <EntityTable ref="tableRef" entity="audits" :columns="cols" title="audit" action-variant="icon" :show-toolbar="false" :filter-fn="filterFn" :drawer="AuditDrawer" @changed="statsRef?.reload()" />
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
.acts{display:flex;gap:8px;align-items:center}
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
.filters-toggle{display:inline-flex;align-items:center;gap:8px;height:34px;border:1px solid var(--violet);
  background:var(--c-violet-bg);color:var(--violet-accent);border-radius:var(--r-pill);
  padding:0 14px;font-size:13px;font-weight:600;cursor:pointer}
.filters-toggle .chevron{font-size:11px;margin-left:2px}
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
</style>
