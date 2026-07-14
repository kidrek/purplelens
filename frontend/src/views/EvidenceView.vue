<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, ApiError } from '../api/client'
import EvidenceCard from '../components/EvidenceCard.vue'
import EvidenceUpload from '../components/EvidenceUpload.vue'
import RefacSelect from '../components/RefacSelect.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const items = ref([])
const loading = ref(true)
const error = ref(null)

// Disposition d'affichage des preuves : 'table' (tableau, défaut) ou 'grid' (vignettes).
// Persistée localement pour retrouver le choix de l'opérateur d'une session à l'autre.
const viewMode = ref(localStorage.getItem('evidence.viewMode') === 'grid' ? 'grid' : 'table')
function setViewMode(mode) {
  viewMode.value = mode
  localStorage.setItem('evidence.viewMode', mode)
}

// Sélecteur d'audit pour l'upload de preuves.
const audits = ref([])
const selectedAuditId = ref('')
const showUploader = ref(false)
const uploadError = ref(null)

// ── Filtres (repliés par défaut) ─────────────────────────────────────────────
// Filtrage purement CÔTÉ CLIENT : la liste (≤ 200 lignes, déjà cloisonnée RLS côté
// serveur) porte tous les libellés résolus (organisation, application, audit, auditeur,
// fichier, date, hash). Aucun de ces champs n'est un secret ; on n'élargit donc pas la
// surface d'exposition. Les filtres texte sont insensibles à la casse (sous-chaîne) ;
// la date d'upload se filtre par plage [du, au] au jour (UTC, tel que renvoyé).
const showFilters = ref(false)
const emptyFilters = () => ({ org: '', app: '', audit: '', uploader: '', file: '', hash: '', dateFrom: '', dateTo: '' })
const filters = ref(emptyFilters())
function resetFilters() { filters.value = emptyFilters() }
const activeFilterCount = computed(
  () => Object.values(filters.value).filter((v) => String(v).trim() !== '').length
)

function matchesFilters(e) {
  const f = filters.value
  const has = (hay, needle) =>
    !needle.trim() || String(hay ?? '').toLowerCase().includes(needle.trim().toLowerCase())
  if (!has(e.organisation_nom, f.org)) return false
  if (!has(e.application_nom, f.app)) return false
  if (!has(e.audit_nom, f.audit)) return false
  if (!has(e.uploader_nom, f.uploader)) return false
  if (!has(e.original_filename, f.file)) return false
  if (!has(e.sha256_plaintext, f.hash)) return false
  if (f.dateFrom || f.dateTo) {
    const day = e.uploaded_at ? String(e.uploaded_at).slice(0, 10) : ''
    if (f.dateFrom && day < f.dateFrom) return false
    if (f.dateTo && day > f.dateTo) return false
  }
  return true
}

const filteredItems = computed(() => items.value.filter(matchesFilters))

// Suggestions d'autocomplétion : valeurs DISTINCTES effectivement présentes dans le
// coffre pour chaque champ, triées, au format {id,label} attendu par RefacSelect (le
// même combobox que le champ « Client » du formulaire d'audit). id = label = valeur :
// choisir une option pose la valeur exacte, que matchesFilters retrouve en sous-chaîne.
// Se recalculent avec la liste (rechargement, nouvel upload) → jamais de valeur périmée.
function optionsFor(key) {
  const seen = new Set()
  for (const e of items.value) {
    const v = e[key]
    if (v) seen.add(String(v))
  }
  return [...seen].sort((a, b) => a.localeCompare(b)).map((v) => ({ id: v, label: v }))
}
const orgOptions = computed(() => optionsFor('organisation_nom'))
const appOptions = computed(() => optionsFor('application_nom'))
const auditOptions = computed(() => optionsFor('audit_nom'))
const uploaderOptions = computed(() => optionsFor('uploader_nom'))
const fileOptions = computed(() => optionsFor('original_filename'))
const hashOptions = computed(() => optionsFor('sha256_plaintext'))

// ── Rafraîchissement automatique du statut d'ingestion ──────────────────────
// Le sas (worker Celery) fait évoluer le statut d'une preuve de façon ASYNCHRONE :
// quarantined → stored (succès) ou rejected (échec). On recharge donc la liste en
// tâche de fond tant qu'au moins une preuve est en quarantaine, puis on s'arrête
// tout seul. Un garde-fou borne le sondage pour ne jamais boucler indéfiniment
// (ex. worker à l'arrêt : une preuve resterait en quarantaine sans jamais évoluer).
const REFRESH_INTERVAL = 2000
const MAX_REFRESH_TICKS = 45 // ~90 s max
let refreshTimer = null
let refreshTicks = 0

function stopAutoRefresh() {
  if (refreshTimer) { clearTimeout(refreshTimer); refreshTimer = null }
}

function scheduleAutoRefresh() {
  stopAutoRefresh()
  const pending = items.value.some((e) => e.ingest_status === 'quarantined')
  if (!pending) { refreshTicks = 0; return }
  if (refreshTicks >= MAX_REFRESH_TICKS) return // garde-fou : arrêt si l'ingestion traîne
  refreshTicks += 1
  refreshTimer = setTimeout(() => load({ silent: true }), REFRESH_INTERVAL)
}

async function load({ silent = false } = {}) {
  // Un rechargement de fond (silent) ne touche ni au spinner de chargement ni au
  // message d'erreur : la vue ne « clignote » pas pendant le sondage.
  if (!silent) { loading.value = true; error.value = null; refreshTicks = 0 }
  try {
    const d = await api.list('evidence')
    items.value = Array.isArray(d) ? d : (d?.items ?? [])
  } catch (e) {
    if (!silent) error.value = e instanceof ApiError && e.status === 403 ? t('common.forbidden') : e.message
  } finally {
    if (!silent) loading.value = false
  }
  scheduleAutoRefresh()
}

// Charger la liste des audits pour le sélecteur.
async function loadAudits() {
  try {
    const d = await api.list('audits')
    audits.value = Array.isArray(d) ? d : (d?.items ?? [])
  } catch { /* silencieux : sans audit, l'upload est désactivé */ }
}

const selectedAudit = computed(() => audits.value.find((a) => a.id === selectedAuditId.value) || null)

function onUploaded() {
  showUploader.value = false
  selectedAuditId.value = ''
  // La preuve fraîchement déposée est en quarantaine : load() la fait apparaître puis
  // scheduleAutoRefresh() suit son statut jusqu'à stored/rejected, sans action manuelle.
  load()
}

onMounted(() => { load(); loadAudits() })
onUnmounted(stopAutoRefresh)
</script>

<template>
  <div>
    <div class="head">
      <div>
        <div class="eyebrow">Coffre-fort</div>
        <h1>{{ t('evidence.title') }}</h1>
        <p class="subtitle">{{ t('evidence.note') }}</p>
      </div>
      <div class="head-actions">
        <button class="btn" :class="{ 'btn-active': showFilters }"
                :aria-expanded="showFilters" @click="showFilters = !showFilters">
          {{ t('evidence.filters_title') }}<span v-if="activeFilterCount" class="filter-badge">{{ activeFilterCount }}</span>
        </button>
        <div class="view-toggle" role="group" :aria-label="t('evidence.view_grid') + ' / ' + t('evidence.view_table')">
          <button type="button" class="seg" :class="{ active: viewMode === 'grid' }"
                  :aria-pressed="viewMode === 'grid'" @click="setViewMode('grid')">
            {{ t('evidence.view_grid') }}
          </button>
          <button type="button" class="seg" :class="{ active: viewMode === 'table' }"
                  :aria-pressed="viewMode === 'table'" @click="setViewMode('table')">
            {{ t('evidence.view_table') }}
          </button>
        </div>
        <button class="btn btn-primary" @click="showUploader = !showUploader">
          {{ showUploader ? t('common.close') : t('upload.new') }}
        </button>
      </div>
    </div>

    <!-- Panneau d'upload (pliable) -->
    <div v-if="showUploader" class="upload-panel card">
      <div class="panel-head">
        <span class="panel-title">{{ t('upload.title') }}</span>
      </div>

      <!-- Sélecteur d'audit -->
      <div class="audit-select">
        <label class="f-label">{{ t('fields.audit_id') }}</label>
        <select class="field" v-model="selectedAuditId">
          <option value="" disabled>{{ audits.length ? '— Choisir un audit —' : 'Aucun audit disponible' }}</option>
          <option v-for="a in audits" :key="a.id" :value="a.id">{{ a.nom }}</option>
        </select>
      </div>

      <!-- Formulaire d'upload (désactivé tant qu'aucun audit n'est choisi) -->
      <EvidenceUpload
        v-if="selectedAudit"
        :audit-id="selectedAudit.id"
        :client-id="selectedAudit.client_id"
        @uploaded="onUploaded"
        @error="uploadError = $event"
      />
      <p v-else class="hint">{{ t('upload.select_audit') }}</p>
      <p v-if="uploadError" class="msg ko">{{ uploadError }}</p>
    </div>

    <!-- Panneau de filtres (replié par défaut) -->
    <div v-if="showFilters" class="filter-panel card">
      <div class="filter-grid">
        <div class="f-field">
          <span class="f-label">{{ t('evidence.col_org') }}</span>
          <RefacSelect :options="orgOptions" v-model="filters.org" />
        </div>
        <div class="f-field">
          <span class="f-label">{{ t('evidence.col_app') }}</span>
          <RefacSelect :options="appOptions" v-model="filters.app" />
        </div>
        <div class="f-field">
          <span class="f-label">{{ t('evidence.col_audit') }}</span>
          <RefacSelect :options="auditOptions" v-model="filters.audit" />
        </div>
        <div class="f-field">
          <span class="f-label">{{ t('evidence.col_uploader') }}</span>
          <RefacSelect :options="uploaderOptions" v-model="filters.uploader" />
        </div>
        <div class="f-field">
          <span class="f-label">{{ t('evidence.col_file') }}</span>
          <RefacSelect :options="fileOptions" v-model="filters.file" />
        </div>
        <div class="f-field">
          <span class="f-label">{{ t('evidence.col_hash') }}</span>
          <RefacSelect :options="hashOptions" v-model="filters.hash" />
        </div>
        <label class="f-field">
          <span class="f-label">{{ t('evidence.filter_date_from') }}</span>
          <input class="field" v-model="filters.dateFrom" type="date" />
        </label>
        <label class="f-field">
          <span class="f-label">{{ t('evidence.filter_date_to') }}</span>
          <input class="field" v-model="filters.dateTo" type="date" />
        </label>
      </div>
      <div class="filter-foot">
        <span class="hint">{{ t('evidence.filter_count', { shown: filteredItems.length, total: items.length }) }}</span>
        <button class="btn slim" :disabled="!activeFilterCount" @click="resetFilters">{{ t('evidence.filter_reset') }}</button>
      </div>
    </div>

    <p v-if="loading" class="muted">{{ t('common.loading') }}</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <p v-else-if="items.length === 0" class="muted">{{ t('common.empty') }}</p>
    <p v-else-if="filteredItems.length === 0" class="muted">{{ t('evidence.filter_no_match') }}</p>
    <table v-else-if="viewMode === 'table'" class="evi-table">
      <thead>
        <tr>
          <th>{{ t('evidence.col_org') }}</th>
          <th>{{ t('evidence.col_app') }}</th>
          <th>{{ t('evidence.col_audit') }}</th>
          <th>{{ t('evidence.col_uploader') }}</th>
          <th>{{ t('evidence.col_file') }}</th>
          <th>{{ t('evidence.col_date') }}</th>
          <th>{{ t('evidence.col_hash') }}</th>
          <th>{{ t('evidence.col_tlp') }}</th>
          <th class="th-action"></th>
        </tr>
      </thead>
      <tbody>
        <EvidenceCard v-for="e in filteredItems" :key="e.id" :item="e" layout="row" />
      </tbody>
    </table>
    <div v-else class="gallery">
      <EvidenceCard v-for="e in filteredItems" :key="e.id" :item="e" layout="card" />
    </div>
  </div>
</template>

<style scoped>
.note{margin:12px 0 18px;color:var(--muted);font-size:12px;border-left:3px solid var(--violet)}
/* Galerie responsive (DA §5.1) : grille de cartes, min 180px, plutôt qu'une liste verticale */
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:var(--gap-lg)}
/* Vue tableau : pleine largeur, la colonne d'action se cale à droite. La typographie
   du corps (Inter 12.5px) vient désormais de la règle globale des tables (base.css). */
.evi-table{width:100%}
.evi-table .th-action{width:1%}
.head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
/* Bascule Grille/Tableau (segmenté). */
.view-toggle{display:inline-flex;border:1px solid var(--border);border-radius:var(--r-mini);overflow:hidden}
.view-toggle .seg{padding:6px 12px;font-size:12px;background:var(--surface);color:var(--muted);border:0;cursor:pointer}
.view-toggle .seg+.seg{border-left:1px solid var(--border)}
.view-toggle .seg.active{background:var(--violet);color:#fff}
.subtitle{font-size:13px;color:var(--muted);margin:2px 0 0}
.head-actions{display:flex;gap:8px;flex:0 0 auto;align-items:center}
.msg.ko{color:var(--red);font-size:12px;margin:8px 0}
/* Bouton Filtres actif + pastille de compteur. */
.btn.btn-active{border-color:var(--violet);color:var(--violet)}
.filter-badge{display:inline-flex;align-items:center;justify-content:center;min-width:16px;height:16px;padding:0 4px;margin-left:6px;border-radius:8px;background:var(--violet);color:#fff;font-size:10px;line-height:1}

/* Panneau de filtres (replié par défaut). */
.filter-panel{margin-top:16px;padding:16px}
.filter-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.f-field{display:flex;flex-direction:column}
.filter-foot{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:12px}
.filter-foot .hint{margin:0}
.btn.slim{padding:4px 9px;font-size:12px}

/* Panneau d'upload */
.upload-panel{margin-top:16px;padding:16px}
.panel-head{margin-bottom:12px}
.panel-title{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.audit-select{margin-bottom:12px}
.f-label{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight);display:block;margin-bottom:4px}
.field{width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--r-mini);font-size:13px;background:var(--surface);color:var(--text)}
.hint{font-size:12px;color:var(--faint);margin:8px 0}
</style>
