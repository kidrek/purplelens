<script setup>
import { ref, computed, onMounted } from 'vue'
import EntityTable from '../components/EntityTable.vue'
import RefacSelect from '../components/RefacSelect.vue'
import RessourcesStats from '../components/RessourcesStats.vue'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'
import { fieldsFor } from '../fields'
import { api } from '../api/client'

const { t } = useI18n()
const { enumLabel } = useLabels()

const cols = [
  { key: 'nom', label: 'Nom' },
  { key: 'type', label: 'Type', pill: () => 'violet' },
  { key: 'organisation_id', label: 'Organisation', org: true },
  { key: 'role', label: 'Rôle', upper: true },
  { key: 'contact', label: 'Contact' },
]

// Valeurs du champ `type` (fields.js) ; options de rôle dérivées du schéma pour
// éviter d'exporter ROLE_OPTIONS. RefacSelect attend des options { id, label }.
const TYPES = ['humaine', 'materielle', 'logicielle', 'documentaire']
const roleValues = (fieldsFor('ressources').find((f) => f.key === 'role')?.options || [])
  .map((r) => r.value)
// computed (et non const figé) : les libellés via enumLabel se recalculent au changement
// de langue, à l'image de la colonne Rôle. Majuscules d'affichage appliquées par CSS.
const roleOptions = computed(() => roleValues.map((v) => ({ id: v, label: enumLabel(v) })))

// Références : EntityTable (toolbar interne masquée, actions pilotées depuis l'en-tête via
// openCreate() / load()) et la section KPI (rechargée sur mutation via son reload() exposé).
const tableRef = ref(null)
const statsRef = ref(null)

// Bouton Rafraîchir : recharge le tableau ET les KPI (section découplée).
function refreshAll() {
  tableRef.value?.load()
  statsRef.value?.reload()
}

// État de filtre local + filtrage client-side (aucun paramètre envoyé à l'API).
const showFilters = ref(false)
const fOrgs = ref([])
const fTypes = ref([])
const fRoles = ref([])
const orgOptions = ref([])

function toggleIn(arr, val) {
  const i = arr.indexOf(val)
  if (i === -1) arr.push(val); else arr.splice(i, 1)
}

const activeFilterCount = computed(() =>
  (fOrgs.value.length ? 1 : 0) + (fTypes.value.length ? 1 : 0) + (fRoles.value.length ? 1 : 0))

const filterFn = (r) => {
  if (fOrgs.value.length && !fOrgs.value.includes(r.organisation_id)) return false
  if (fTypes.value.length && !fTypes.value.includes(r.type)) return false
  if (fRoles.value.length && !fRoles.value.includes(r.role)) return false
  return true
}

onMounted(async () => {
  try {
    const rows = await api.list('organisations')
    const list = Array.isArray(rows) ? rows : (rows?.items ?? [])
    orgOptions.value = list.map((o) => ({ id: o.id, label: `${o.code || ''} ${o.nom}`.trim() }))
  } catch { orgOptions.value = [] }
})
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.ressources.eyebrow') }}</div>
    <h1>{{ t('views.ressources.title') }}</h1>
    <div class="subrow">
      <p class="subtitle">{{ t('views.ressources.subtitle') }}</p>
      <div class="acts">
        <button class="filters-toggle" :class="{ open: showFilters }" @click="showFilters = !showFilters">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="10" y1="18" x2="14" y2="18"/></svg>
          {{ t('views.ressources.filters') }}
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
      <span class="lead">{{ t('views.ressources.note.lead') }}</span>
      <ul>
        <li><b>{{ t('views.ressources.note.contacts_label') }}</b> {{ t('views.ressources.note.contacts_text') }}</li>
        <li><b>{{ t('views.ressources.note.externes_label') }}</b> {{ t('views.ressources.note.externes_text') }}</li>
      </ul>
    </div>
    <div v-if="showFilters" class="filters-panel">
      <div class="f-row">
        <label class="f-label">{{ t('views.ressources.filter_org') }}</label>
        <RefacSelect :options="orgOptions" multiple v-model="fOrgs" :placeholder="t('views.ressources.filter_org_ph')" />
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.ressources.filter_type') }}</label>
        <div class="chipset">
          <button v-for="ty in TYPES" :key="ty" type="button" :class="['chip-toggle', { on: fTypes.includes(ty) }]" @click="toggleIn(fTypes, ty)">{{ enumLabel(ty) }}</button>
        </div>
      </div>
      <div class="f-row role-upper">
        <label class="f-label">{{ t('views.ressources.filter_role') }}</label>
        <RefacSelect :options="roleOptions" multiple v-model="fRoles" :placeholder="t('views.ressources.filter_role_ph')" />
      </div>
    </div>
    <RessourcesStats ref="statsRef" :f-orgs="fOrgs" :f-types="fTypes" :f-roles="fRoles" />
    <EntityTable ref="tableRef" entity="ressources" :columns="cols" title="ressource" action-variant="icon" :show-toolbar="false" :filter-fn="filterFn" @changed="statsRef?.reload()" />
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
/* Filtre Rôle : chips et options en majuscules, aligné sur la colonne Rôle. */
.role-upper :deep(.chip),
.role-upper :deep(.opt){text-transform:uppercase}
</style>
