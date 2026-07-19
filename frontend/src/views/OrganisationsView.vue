<script setup>
import { ref, computed } from 'vue'
import EntityTable from '../components/EntityTable.vue'
import OrganisationDrawer from '../components/OrganisationDrawer.vue'
import OrganisationsStats from '../components/OrganisationsStats.vue'
import RefacSelect from '../components/RefacSelect.vue'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'
import { fieldsFor } from '../fields'

const { t } = useI18n()
const { enumLabel } = useLabels()

// Colonnes : « Code court » retiré (cf. demande), « Statut » ajouté. Statut en pastille
// verte (actif) / grise (inactif). Le clic sur la ligne ouvre OrganisationDrawer.
const cols = [
  { key: 'nom', label: 'Nom' },
  { key: 'role', label: 'Rôle', pill: () => 'violet' },
  { key: 'secteur', label: 'Secteur' },
  { key: 'statut', label: 'Statut', pill: (v) => (v === 'inactif' ? 'gray' : 'green') },
  { key: 'tlp_defaut', label: 'TLP', tlp: true },
]

// Références : EntityTable (toolbar interne masquée, actions pilotées depuis l'en-tête via
// openCreate() / load()) et la section KPI (rechargée sur mutation via son reload() exposé).
const tableRef = ref(null)
const statsRef = ref(null)

// Bouton Rafraîchir : recharge le tableau ET les KPI (section découplée).
function refreshAll() {
  tableRef.value?.load()
  statsRef.value?.reload()
}

// Valeurs de filtre. Rôle / statut / TLP sont des ensembles fermés ; le secteur reprend
// le référentiel NACE du schéma (fields.js), traduit via enumLabel.
const ROLES = ['client', 'prestataire', 'interne']
const STATUTS = ['actif', 'inactif']
const TLPS = ['RED', 'AMBER', 'GREEN', 'CLEAR']
const secteurOptions = computed(() =>
  (fieldsFor('organisations').find((f) => f.key === 'secteur')?.options || [])
    .map((o) => ({ id: o.value, label: enumLabel(o.value) })))

// État de filtre local + filtrage client-side (aucun paramètre envoyé à l'API liste).
const showFilters = ref(false)
const fRoles = ref([])
const fStatuts = ref([])
const fSecteurs = ref([])
const fTlp = ref([])

function toggleIn(arr, val) {
  const i = arr.indexOf(val)
  if (i === -1) arr.push(val); else arr.splice(i, 1)
}

const activeFilterCount = computed(() =>
  (fRoles.value.length ? 1 : 0) + (fStatuts.value.length ? 1 : 0)
  + (fSecteurs.value.length ? 1 : 0) + (fTlp.value.length ? 1 : 0))

const filterFn = (r) => {
  if (fRoles.value.length && !fRoles.value.includes(r.role)) return false
  if (fStatuts.value.length && !fStatuts.value.includes(r.statut)) return false
  if (fSecteurs.value.length && !fSecteurs.value.includes(r.secteur)) return false
  if (fTlp.value.length && !fTlp.value.includes(r.tlp_defaut)) return false
  return true
}
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.organisations.eyebrow') }}</div>
    <h1>{{ t('views.organisations.title') }}</h1>
    <div class="subrow">
      <p class="subtitle">{{ t('views.organisations.subtitle') }}</p>
      <div class="acts">
        <button class="filters-toggle" :class="{ open: showFilters }" @click="showFilters = !showFilters">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="10" y1="18" x2="14" y2="18"/></svg>
          {{ t('views.organisations.filters') }}
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
      <span class="lead">{{ t('views.organisations.note.lead') }}</span>
      <ul>
        <li><b>{{ t('views.organisations.note.clients_label') }}</b> {{ t('views.organisations.note.clients_text') }}</li>
        <li><b>{{ t('views.organisations.note.autres_label') }}</b> {{ t('views.organisations.note.autres_text') }}</li>
      </ul>
    </div>
    <div v-if="showFilters" class="filters-panel">
      <div class="f-row">
        <label class="f-label">{{ t('views.organisations.filter_role') }}</label>
        <div class="chipset">
          <button v-for="ro in ROLES" :key="ro" type="button" :class="['chip-toggle', { on: fRoles.includes(ro) }]" @click="toggleIn(fRoles, ro)">{{ enumLabel(ro) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.organisations.filter_statut') }}</label>
        <div class="chipset">
          <button v-for="st in STATUTS" :key="st" type="button" :class="['chip-toggle', { on: fStatuts.includes(st) }]" @click="toggleIn(fStatuts, st)">{{ enumLabel(st) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.organisations.filter_secteur') }}</label>
        <RefacSelect :options="secteurOptions" multiple v-model="fSecteurs" :placeholder="t('views.organisations.filter_secteur_ph')" />
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.organisations.filter_tlp') }}</label>
        <div class="chipset">
          <button v-for="l in TLPS" :key="l" type="button" :class="['chip-toggle', { on: fTlp.includes(l) }]" @click="toggleIn(fTlp, l)">{{ l }}</button>
        </div>
      </div>
    </div>
    <OrganisationsStats ref="statsRef" :f-roles="fRoles" :f-statuts="fStatuts" :f-secteurs="fSecteurs" :f-tlp="fTlp" />
    <EntityTable ref="tableRef" entity="organisations" :columns="cols" title="organisation" action-variant="icon" :show-toolbar="false" :filter-fn="filterFn" :drawer="OrganisationDrawer" @changed="statsRef?.reload()" />
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
</style>
