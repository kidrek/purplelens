<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import EntityTable from '../components/EntityTable.vue'
import RefacSelect from '../components/RefacSelect.vue'
import RefPicker from '../components/RefPicker.vue'
import ScenarioDrawer from '../components/ScenarioDrawer.vue'
import ScenariosStats from '../components/ScenariosStats.vue'
import { useLabels } from '../composables/useLabels'
import { ENGAGEMENT_TONE, SOPH_TONE, credTone } from '../tones'
import { api, ApiError } from '../api/client'

const { t, te } = useI18n()
const { enumLabel } = useLabels()

// Crédibilité Admiralty : libellé court « 2 · Probable » dans la pill de colonne.
const credLabel = (v) => (te(`views.scenarios.cred.${v}`) ? `${v} · ${t('views.scenarios.cred.' + v)}` : String(v))

// Ordre validé : identité (nom, référence) puis contenu métier ; TLP en marqueur de fin.
const cols = [
  { key: 'nom', label: 'Nom' },
  { key: 'reference', label: 'Référence' },
  { key: 'acteur_emule', label: 'Acteur émulé' },
  { key: 'type_engagement', label: 'Engagement', pill: (v) => ENGAGEMENT_TONE[v] || 'gray' },
  { key: 'sophistication', label: 'Sophistication', pill: (v) => SOPH_TONE[v] || 'gray' },
  { key: 'credibilite', label: 'Crédibilité', pill: credTone, format: credLabel },
  { key: 'tlp', label: 'TLP', tlp: true },
]

const ENGAGEMENTS = ['red-team', 'purple-team', 'tabletop', 'assumed-breach']
const SOPHISTICATIONS = ['basique', 'intermediaire', 'avancee', 'apt']
// Crédibilité filtrée par groupes Admiralty (1-2 / 3-4 / 5-6).
const CRED_GROUPS = [
  { key: 'fiable', values: [1, 2] },
  { key: 'confirmer', values: [3, 4] },
  { key: 'faible', values: [5, 6] },
]
const TLPS = ['RED', 'AMBER', 'GREEN', 'CLEAR']

// Références : EntityTable (toolbar interne masquée, actions pilotées depuis l'en-tête).
// Les KPI et options de filtre dérivent des lignes exposées par le tableau (rows) —
// bibliothèque globale entièrement chargée, aucun fetch supplémentaire.
const tableRef = ref(null)
const allRows = computed(() => tableRef.value?.rows ?? [])

function refreshAll() { tableRef.value?.load() }

// État de filtre local + filtrage client-side (aucun paramètre envoyé à l'API).
const showFilters = ref(false)
const q = ref('')
const fEng = ref([])
const fSoph = ref([])
const fCred = ref([])
const fTlp = ref([])
const fActors = ref([])
const fTechs = ref([])          // ext_id ATT&CK sélectionnés, ex. ['T1566','T1486']
const fTechsMode = ref('any')   // 'any' (au moins une) | 'all' (toutes)

function toggleIn(arr, val) {
  const i = arr.indexOf(val)
  if (i === -1) arr.push(val); else arr.splice(i, 1)
}

const activeFilterCount = computed(() =>
  (fEng.value.length ? 1 : 0) + (fSoph.value.length ? 1 : 0) + (fCred.value.length ? 1 : 0) +
  (fTlp.value.length ? 1 : 0) + (fActors.value.length ? 1 : 0) + (fTechs.value.length ? 1 : 0))

const actorOptions = computed(() => {
  const set = new Set()
  for (const r of allRows.value) if (r.acteur_emule) set.add(r.acteur_emule)
  return [...set].sort((a, b) => a.localeCompare(b)).map((a) => ({ id: a, label: a }))
})

const filterFn = (r) => {
  const needle = q.value.trim().toLowerCase()
  if (needle) {
    const hay = `${r.nom || ''} ${r.reference || ''} ${r.acteur_emule || ''}`.toLowerCase()
    if (!hay.includes(needle)) return false
  }
  if (fEng.value.length && !fEng.value.includes(r.type_engagement)) return false
  if (fSoph.value.length && !fSoph.value.includes(r.sophistication)) return false
  if (fCred.value.length) {
    const groups = CRED_GROUPS.filter((g) => fCred.value.includes(g.key))
    if (!groups.some((g) => g.values.includes(r.credibilite))) return false
  }
  if (fTlp.value.length) {
    const tlp = r.tlp === 'WHITE' ? 'CLEAR' : r.tlp
    if (!fTlp.value.includes(tlp)) return false
  }
  if (fActors.value.length && !fActors.value.includes(r.acteur_emule)) return false
  if (fTechs.value.length) {
    // `techniques` est dérivé des étapes offensives : un scénario sans étapes ne matche pas.
    const techs = Array.isArray(r.techniques) ? r.techniques : []
    const ok = fTechsMode.value === 'all'
      ? fTechs.value.every((t) => techs.includes(t))
      : fTechs.value.some((t) => techs.includes(t))
    if (!ok) return false
  }
  return true
}

// Lignes filtrées pour les KPI : mêmes règles que le tableau (entité globale, sans client_id).
const filteredRows = computed(() => allRows.value.filter(filterFn))

// --- STIX : menu groupé (import + export global) + export par ligne. ---
const msg = ref(null)
const importBusy = ref(false)
const stixOpen = ref(false)
const stixWrap = ref(null)

function onDocClick(ev) {
  if (stixOpen.value && stixWrap.value && !stixWrap.value.contains(ev.target)) stixOpen.value = false
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

// Déclenche un téléchargement de fichier à partir d'un objet JSON (bundle STIX).
function downloadJson(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

async function exportOne(row) {
  msg.value = null
  try {
    const bundle = await api.get(`/stix/scenarios/${row.id}`)
    downloadJson(bundle, `scenario-${row.id}.stix.json`)
  } catch (e) {
    msg.value = e instanceof ApiError && e.status === 403 ? t('views.scenarios.stix.export_denied') : (e.message || 'Erreur.')
  }
}

async function exportAll() {
  stixOpen.value = false
  msg.value = null
  try {
    const bundle = await api.get('/stix/scenarios')
    downloadJson(bundle, 'scenarios.stix.json')
  } catch (e) {
    msg.value = e instanceof ApiError && e.status === 403 ? t('views.scenarios.stix.export_denied') : (e.message || 'Erreur.')
  }
}

// Import d'un bundle STIX 2.1 -> crée un/des scénario(s) dans la bibliothèque.
async function onStixImport(ev) {
  const file = ev.target.files?.[0]
  if (!file) return
  importBusy.value = true; msg.value = null
  try {
    const bundle = JSON.parse(await file.text())
    const r = await api.post('/stix/import', { bundle })
    msg.value = { ok: true, text: t('views.scenarios.stix.imported', { n: r.imported }) }
    tableRef.value?.load()
  } catch (e) {
    const txt = e instanceof ApiError
      ? (e.status === 403 ? t('views.scenarios.stix.import_denied')
        : e.status === 400 ? t('views.scenarios.stix.import_invalid') : (e.message || 'Erreur.'))
      : t('views.scenarios.stix.import_bad_file')
    msg.value = { ok: false, text: txt }
  } finally {
    importBusy.value = false; stixOpen.value = false; ev.target.value = ''
  }
}

const stixAction = [
  { label: 'STIX', icon: 'export', fn: exportOne },
]
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.scenarios.eyebrow') }}</div>
    <h1>{{ t('views.scenarios.title') }}</h1>
    <div class="subrow">
      <p class="subtitle">{{ t('views.scenarios.subtitle') }}</p>
      <div class="acts">
        <label class="search">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/></svg>
          <input v-model="q" type="search" :placeholder="t('views.scenarios.search_ph')" />
        </label>
        <button class="filters-toggle" :class="{ open: showFilters }" @click="showFilters = !showFilters">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="10" y1="18" x2="14" y2="18"/></svg>
          {{ t('views.scenarios.filters') }}
          <span v-if="activeFilterCount" class="count-badge sm">{{ activeFilterCount }}</span>
          <span class="chevron">{{ showFilters ? '⌃' : '⌄' }}</span>
        </button>
        <div ref="stixWrap" class="stix-wrap">
          <button class="icon-btn wide" :class="{ disabled: importBusy }"
                  :title="importBusy ? t('views.scenarios.stix.importing') : 'STIX'"
                  :aria-label="importBusy ? t('views.scenarios.stix.importing') : 'STIX'"
                  @click="stixOpen = !stixOpen">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 8h13"/><path d="m13 4 4 4-4 4"/><path d="M20 16H7"/><path d="m11 20-4-4 4-4"/></svg>
            <span class="chevron">{{ stixOpen ? '⌃' : '⌄' }}</span>
          </button>
          <div v-if="stixOpen" class="stix-menu">
            <label class="stix-item" :class="{ disabled: importBusy }">
              {{ t('views.scenarios.stix.import') }}
              <input type="file" accept="application/json,.json" @change="onStixImport" hidden :disabled="importBusy" />
            </label>
            <button class="stix-item" @click="exportAll">{{ t('views.scenarios.stix.export_all') }}</button>
          </div>
        </div>
        <button class="btn btn-primary" @click="tableRef?.openCreate()">+ {{ t('common.new') }}</button>
        <button class="icon-btn" :title="t('common.refresh')" :aria-label="t('common.refresh')" @click="refreshAll">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
        </button>
      </div>
    </div>
    <div class="note">
      <span class="lead">{{ t('views.scenarios.note.lead') }}</span>
      <ul>
        <li><b>{{ t('views.scenarios.note.contenu_label') }}</b> {{ t('views.scenarios.note.contenu_text') }}</li>
        <li><b>{{ t('views.scenarios.note.usage_label') }}</b> {{ t('views.scenarios.note.usage_text') }}</li>
      </ul>
    </div>
    <p v-if="msg" :class="typeof msg === 'object' ? (msg.ok ? 'ok' : 'err') : 'err'">
      {{ typeof msg === 'object' ? msg.text : msg }}
    </p>
    <div v-if="showFilters" class="filters-panel">
      <div class="f-row">
        <label class="f-label">{{ t('views.scenarios.filter_engagement') }}</label>
        <div class="chipset">
          <button v-for="e in ENGAGEMENTS" :key="e" type="button" :class="['chip-toggle', { on: fEng.includes(e) }]" @click="toggleIn(fEng, e)">{{ enumLabel(e) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.scenarios.filter_sophistication') }}</label>
        <div class="chipset">
          <button v-for="s in SOPHISTICATIONS" :key="s" type="button" :class="['chip-toggle', { on: fSoph.includes(s) }]" @click="toggleIn(fSoph, s)">{{ enumLabel(s) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.scenarios.filter_credibilite') }}</label>
        <div class="chipset">
          <button v-for="g in CRED_GROUPS" :key="g.key" type="button" :class="['chip-toggle', { on: fCred.includes(g.key) }]" @click="toggleIn(fCred, g.key)">{{ t('views.scenarios.cred_groups.' + g.key) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.scenarios.filter_tlp') }}</label>
        <div class="chipset">
          <button v-for="l in TLPS" :key="l" type="button" :class="['chip-toggle', { on: fTlp.includes(l) }]" @click="toggleIn(fTlp, l)">{{ l }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.scenarios.filter_acteur') }}</label>
        <RefacSelect :options="actorOptions" multiple v-model="fActors" :placeholder="t('views.scenarios.filter_acteur_ph')" />
      </div>
      <div class="f-row wide">
        <div class="f-head">
          <label class="f-label">{{ t('views.scenarios.filter_techniques') }}</label>
          <div class="mode-toggle" role="radiogroup" :aria-label="t('views.scenarios.filter_techniques')">
            <button type="button" :class="{ on: fTechsMode === 'any' }" @click="fTechsMode = 'any'">{{ t('views.scenarios.filter_techniques_any') }}</button>
            <button type="button" :class="{ on: fTechsMode === 'all' }" @click="fTechsMode = 'all'">{{ t('views.scenarios.filter_techniques_all') }}</button>
          </div>
        </div>
        <div class="tech-pick">
          <RefPicker catalog="attack" multiple v-model="fTechs" :placeholder="t('views.scenarios.filter_techniques_ph')" />
        </div>
      </div>
    </div>
    <ScenariosStats :rows="filteredRows" />
    <EntityTable ref="tableRef" entity="scenarios" :columns="cols" title="scénario"
                 action-variant="icon" :show-toolbar="false" :filter-fn="filterFn"
                 :extra-actions="stixAction" :drawer="ScenarioDrawer" />
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
.acts{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
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
/* Variante « large » : icône + chevron (déclencheur STIX). */
.icon-btn.wide{width:auto;padding:0 10px;gap:5px}
.icon-btn.disabled{opacity:.6;pointer-events:none}
.filters-toggle{display:inline-flex;align-items:center;gap:8px;height:34px;border:1px solid var(--violet);
  background:var(--c-violet-bg);color:var(--violet-accent);border-radius:var(--r-pill);
  padding:0 14px;font-size:13px;font-weight:600;cursor:pointer}
.filters-toggle .chevron{font-size:11px;margin-left:2px}
.chevron{font-size:11px}
.stix-wrap{position:relative}
.stix-wrap .btn{display:inline-flex;align-items:center;gap:6px}
.stix-wrap .btn.disabled{opacity:.6;pointer-events:none}
.stix-menu{position:absolute;top:calc(100% + 6px);right:0;z-index:30;min-width:190px;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);
  box-shadow:var(--shadow);padding:6px;display:flex;flex-direction:column;gap:2px}
.stix-item{display:block;width:100%;text-align:left;border:none;background:transparent;color:var(--text);
  font-size:12.5px;padding:8px 10px;border-radius:var(--r-mini);cursor:pointer}
.stix-item:hover{background:var(--surface-2);color:var(--violet-accent)}
.stix-item.disabled{opacity:.6;pointer-events:none}
.filters-panel{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;
  padding:16px;margin:12px 0 0;border:1px solid var(--border);border-radius:var(--r-card);background:var(--surface-2)}
.f-row{display:flex;flex-direction:column;gap:6px}
.f-row.wide{grid-column:1/-1;border-top:1px solid var(--border-2);padding-top:12px}
.f-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.mode-toggle{display:inline-flex;border:1px solid var(--border);border-radius:var(--r-pill);overflow:hidden}
.mode-toggle button{border:0;background:var(--surface);color:var(--faint);font-size:10.5px;padding:3px 10px;cursor:pointer}
.mode-toggle button.on{background:var(--c-violet-bg);color:var(--c-violet-tx);font-weight:600}
.tech-pick{max-width:420px}
.f-label{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.chipset{display:flex;flex-wrap:wrap;gap:8px}
.chip-toggle{border:1px solid var(--border);background:var(--surface);color:var(--muted);
  border-radius:var(--r-pill);padding:6px 14px;font-size:12.5px;cursor:pointer;transition:border-color var(--t) var(--ease)}
.chip-toggle:hover{border-color:var(--violet)}
.chip-toggle.on{background:var(--c-violet-bg);border-color:var(--c-violet-bd);color:var(--c-violet-tx);font-weight:600}
.count-badge{display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:20px;
  border-radius:99px;background:var(--surface-3);color:var(--text);font-size:11px;font-family:var(--font-data);padding:0 6px;margin-left:4px}
.count-badge.sm{min-width:16px;height:16px;font-size:10px;background:var(--violet);color:#fff}
.err{color:var(--red);font-size:13px;margin:10px 0 0}
.ok{color:var(--green);font-size:13px;margin:10px 0 0}
</style>
