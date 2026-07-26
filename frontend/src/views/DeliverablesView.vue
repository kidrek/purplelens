<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, ApiError } from '../api/client'
import DeliverableDrawer from '../components/DeliverableDrawer.vue'
import DetailDrawer from '../components/DetailDrawer.vue'
import RefacSelect from '../components/RefacSelect.vue'
const { t, locale } = useI18n()

// Générateur de livrables (cahier §5). Le rendu (lettre d'engagement, NDA, rapport
// PTES) est fait par le SERVEUR, qui masque les preuves secrètes (porte 5) et pose
// un Object Lock. Le PDF n'est jamais servi par l'API : on récupère une URL présignée
// courte. Le client ne décide rien — tout repasse par can() + RLS côté serveur.
// La page reprend le squelette de « Scénarios de menace » : en-tête + callout,
// barre d'outils (recherche / Filtres / action / rafraîchir), filtres dépliables,
// KPI, tableau à lignes cliquables. Filtrage et KPI sont dérivés côté client des
// lignes déjà chargées — aucune requête supplémentaire.
const TYPES = ['rapport', 'nda', 'engagement']
const TLPS = ['RED', 'AMBER', 'GREEN', 'CLEAR']
const LANGUES = ['fr', 'en']
const STATUTS = ['genere']

const clients = ref([])
const audits = ref([])
const deliverables = ref([])
const form = ref({ type: 'rapport', client_id: '', audit_id: '', langue: 'fr', tlp: 'AMBER' })
const busy = ref(false)
const msg = ref(null)
const loading = ref(true)
const viewFor = ref(null)
const showGen = ref(false)

const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))
// Le rapport PTES tire ses constats d'un audit → audit requis pour ce type.
const auditRequired = computed(() => form.value.type === 'rapport')
const auditsForClient = computed(() =>
  form.value.client_id ? audits.value.filter((a) => a.client_id === form.value.client_id) : audits.value
)

// Options {id,label} pour l'autocomplétion (RefacSelect) : préférable à un menu
// déroulant quand ces listes grossissent (nombreux clients / audits).
const clientOptions = computed(() => clients.value.map((c) => ({ id: c.id, label: `${c.code} · ${c.nom}` })))
const auditOptions = computed(() => auditsForClient.value.map((a) => ({ id: a.id, label: a.nom })))

// Changer de client purge l'audit choisi (il sortirait du périmètre du nouveau client).
watch(() => form.value.client_id, () => { form.value.audit_id = '' })

// --- Filtres (état local, filtrage client-side, aucun paramètre envoyé à l'API). ---
const showFilters = ref(false)
const q = ref('')
const fType = ref([])
const fLangue = ref([])
const fTlp = ref([])
const fStatut = ref([])
const fClient = ref('')
const fAudit = ref('')

function toggleIn(arr, val) {
  const i = arr.indexOf(val)
  if (i === -1) arr.push(val); else arr.splice(i, 1)
}

const activeFilterCount = computed(() =>
  (fType.value.length ? 1 : 0) + (fLangue.value.length ? 1 : 0) + (fTlp.value.length ? 1 : 0) +
  (fStatut.value.length ? 1 : 0) + (fClient.value ? 1 : 0) + (fAudit.value ? 1 : 0))

function matches(d) {
  const needle = q.value.trim().toLowerCase()
  if (needle) {
    const hay = `${d.titre || ''} ${clientName(d.client_id)} ${auditName(d.audit_id)}`.toLowerCase()
    if (!hay.includes(needle)) return false
  }
  if (fType.value.length && !fType.value.includes(d.type)) return false
  if (fLangue.value.length && !fLangue.value.includes(d.langue)) return false
  if (fTlp.value.length && !fTlp.value.includes(d.tlp)) return false
  if (fStatut.value.length && !fStatut.value.includes(d.statut)) return false
  if (fClient.value && d.client_id !== fClient.value) return false
  if (fAudit.value && d.audit_id !== fAudit.value) return false
  return true
}
const filtered = computed(() => deliverables.value.filter(matches))

// --- Tri par en-têtes cliquables. Par défaut : date de génération décroissante
// (les plus récents en haut). Tri purement client-side sur les lignes filtrées. ---
const sortKey = ref('created_at')
const sortDir = ref('desc')
const sortTs = (d) => new Date(d.created_at).getTime() || 0

function toggleSort(key) {
  if (sortKey.value === key) { sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'; return }
  sortKey.value = key
  sortDir.value = key === 'created_at' ? 'desc' : 'asc'
}

const sorted = computed(() => {
  const dir = sortDir.value === 'desc' ? -1 : 1
  const rows = [...filtered.value]
  rows.sort((a, b) => {
    let c = 0
    if (sortKey.value === 'type') c = typeLabel(a.type).localeCompare(typeLabel(b.type))
    else if (sortKey.value === 'client') c = clientName(a.client_id).localeCompare(clientName(b.client_id))
    else c = sortTs(a) - sortTs(b)
    // Départage stable : à valeur égale, le plus récent d'abord.
    return (c ? c * dir : sortTs(b) - sortTs(a))
  })
  return rows
})

// --- KPI dérivés des lignes filtrées. ---
const kpiRapports = computed(() => filtered.value.filter((d) => d.type === 'rapport').length)
const kpiClients = computed(() => new Set(filtered.value.map((d) => d.client_id)).size)
const kpiRecent = computed(() => {
  const cutoff = Date.now() - 30 * 864e5
  return filtered.value.filter((d) => {
    const ts = new Date(d.created_at).getTime()
    return ts && ts >= cutoff
  }).length
})

async function loadRefs() {
  loading.value = true
  try {
    [clients.value, audits.value, deliverables.value] = await Promise.all([
      api.list('organisations').then(unwrap).then((l) => l.filter((o) => o.role === 'client')),
      api.list('audits').then(unwrap),
      api.list('deliverables').then(unwrap),
    ])
  } catch (e) {
    msg.value = { kind: 'ko', text: e.message }
  } finally {
    loading.value = false
  }
}

async function generate() {
  msg.value = null
  if (!form.value.client_id) { msg.value = { kind: 'ko', text: t('views.deliverables.msg.need_client') }; return }
  if (auditRequired.value && !form.value.audit_id) { msg.value = { kind: 'ko', text: t('views.deliverables.msg.need_audit') }; return }
  busy.value = true
  try {
    const payload = {
      client_id: form.value.client_id,
      audit_id: form.value.audit_id || null,
      type: form.value.type,
      langue: form.value.langue,
      tlp: form.value.tlp,
    }
    const res = await api.post('/deliverables/generate', payload)
    msg.value = { kind: 'ok', text: t('views.deliverables.msg.generated', { type: typeLabel(res.type) }) }
    showGen.value = false
    await loadRefs()
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) msg.value = { kind: 'ko', text: t('views.deliverables.msg.gen_denied') }
    else if (e instanceof ApiError && e.status === 404) msg.value = { kind: 'ko', text: t('views.deliverables.msg.client_not_found') }
    else msg.value = { kind: 'ko', text: e.message || t('views.deliverables.msg.gen_error') }
  } finally {
    busy.value = false
  }
}

async function download(d) {
  msg.value = null
  try {
    const res = await api.get(`/deliverables/${d.id}/download`)
    // URL présignée courte → ouverture directe (le binaire ne transite pas par l'API).
    window.open(res.url, '_blank', 'noopener')
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) msg.value = { kind: 'ko', text: t('views.deliverables.msg.dl_not_ready') }
    else if (e instanceof ApiError && e.status === 403) msg.value = { kind: 'ko', text: t('views.deliverables.msg.dl_denied') }
    else msg.value = { kind: 'ko', text: e.message || t('views.deliverables.msg.error') }
  }
}

const typeLabel = (v) => (v ? t('views.deliverables.types.' + v) : v)
const langueLabel = (v) => (v === 'fr' || v === 'en' ? t('views.deliverables.langues.' + v) : (v || '—'))
const clientName = (id) => { const c = clients.value.find((x) => x.id === id); return c ? c.nom : '—' }
const auditName = (id) => { if (!id) return '—'; const a = audits.value.find((x) => x.id === id); return a ? a.nom : '—' }
const statutTone = (s) => (s === 'genere' ? 'green' : 'gray')
const statutLabel = (s) => (s === 'genere' ? t('views.deliverables.statut_genere') : (s || '—'))

// Date de génération + fuseau : conversion vers le fuseau local du navigateur.
function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return new Intl.DateTimeFormat(locale.value === 'en' ? 'en-GB' : 'fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', timeZoneName: 'short',
  }).format(d)
}

function openGen() { msg.value = null; showGen.value = true }

onMounted(loadRefs)
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.deliverables.eyebrow') }}</div>
    <h1>{{ t('views.deliverables.title') }}</h1>
    <div class="subrow">
      <p class="subtitle">{{ t('views.deliverables.subtitle') }}</p>
      <div class="acts">
        <label class="search">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/></svg>
          <input v-model="q" type="search" :placeholder="t('views.deliverables.search_ph')" />
        </label>
        <button class="filters-toggle" :class="{ open: showFilters }" @click="showFilters = !showFilters">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="10" y1="18" x2="14" y2="18"/></svg>
          {{ t('views.deliverables.filters') }}
          <span v-if="activeFilterCount" class="count-badge sm">{{ activeFilterCount }}</span>
          <span class="chevron">{{ showFilters ? '⌃' : '⌄' }}</span>
        </button>
        <button class="btn btn-primary" @click="openGen">+ {{ t('views.deliverables.generate') }}</button>
        <button class="icon-btn" :title="t('common.refresh')" :aria-label="t('common.refresh')" @click="loadRefs">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
        </button>
      </div>
    </div>
    <div class="note">
      <span class="lead">{{ t('views.deliverables.note.lead') }}</span>
      <ul>
        <li><b>{{ t('views.deliverables.note.contenu_label') }}</b> {{ t('views.deliverables.note.contenu_text') }}</li>
        <li><b>{{ t('views.deliverables.note.usage_label') }}</b> {{ t('views.deliverables.note.usage_text') }}</li>
      </ul>
    </div>

    <p v-if="msg" :class="['msg', msg.kind]">{{ msg.text }}</p>

    <!-- Panneau de filtres dépliable -->
    <div v-if="showFilters" class="filters-panel">
      <div class="f-row">
        <label class="f-label">{{ t('views.deliverables.col.type') }}</label>
        <div class="chipset">
          <button v-for="v in TYPES" :key="v" type="button" :class="['chip-toggle', { on: fType.includes(v) }]" @click="toggleIn(fType, v)">{{ typeLabel(v) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.deliverables.col.langue') }}</label>
        <div class="chipset">
          <button v-for="v in LANGUES" :key="v" type="button" :class="['chip-toggle', { on: fLangue.includes(v) }]" @click="toggleIn(fLangue, v)">{{ langueLabel(v) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.deliverables.col.tlp') }}</label>
        <div class="chipset">
          <button v-for="v in TLPS" :key="v" type="button" :class="['chip-toggle', { on: fTlp.includes(v) }]" @click="toggleIn(fTlp, v)">{{ v }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.deliverables.col.statut') }}</label>
        <div class="chipset">
          <button v-for="v in STATUTS" :key="v" type="button" :class="['chip-toggle', { on: fStatut.includes(v) }]" @click="toggleIn(fStatut, v)">{{ statutLabel(v) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.deliverables.col.client') }}</label>
        <select class="field" v-model="fClient">
          <option value="">{{ t('views.deliverables.filter_client_all') }}</option>
          <option v-for="c in clients" :key="c.id" :value="c.id">{{ c.code }} · {{ c.nom }}</option>
        </select>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.deliverables.col.audit') }}</label>
        <select class="field" v-model="fAudit">
          <option value="">{{ t('views.deliverables.filter_audit_all') }}</option>
          <option v-for="a in audits" :key="a.id" :value="a.id">{{ a.nom }}</option>
        </select>
      </div>
    </div>

    <!-- KPI -->
    <div class="kpis">
      <div class="kpi">
        <div class="klab">{{ t('views.deliverables.kpi.total') }}</div>
        <div class="kpi-value">{{ filtered.length }}</div>
        <div class="kpi-foot">{{ t('views.deliverables.kpi.total_foot') }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.deliverables.kpi.rapports') }}</div>
        <div class="kpi-value">{{ kpiRapports }}</div>
        <div class="kpi-foot">{{ t('views.deliverables.kpi.rapports_foot') }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.deliverables.kpi.clients') }}</div>
        <div class="kpi-value" :class="{ good: kpiClients }">{{ kpiClients }}</div>
        <div class="kpi-foot">{{ t('views.deliverables.kpi.clients_foot') }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.deliverables.kpi.recents') }}</div>
        <div class="kpi-value">{{ kpiRecent }}</div>
        <div class="kpi-foot">{{ t('views.deliverables.kpi.recents_foot') }}</div>
      </div>
    </div>

    <!-- Tableau des livrables produits -->
    <p v-if="loading" class="muted">{{ t('common.loading') }}</p>
    <p v-else-if="!deliverables.length" class="muted">{{ t('views.deliverables.empty') }}</p>
    <p v-else-if="!filtered.length" class="muted">{{ t('common.empty') }}</p>
    <table v-else>
      <thead>
        <tr>
          <th class="th-sort" :aria-sort="sortKey === 'type' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'" @click="toggleSort('type')">
            {{ t('views.deliverables.col.type') }}<span v-if="sortKey === 'type'" class="sort-ind">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
          </th>
          <th class="th-sort" :aria-sort="sortKey === 'client' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'" @click="toggleSort('client')">
            {{ t('views.deliverables.col.client') }}<span v-if="sortKey === 'client'" class="sort-ind">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
          </th>
          <th>{{ t('views.deliverables.col.audit') }}</th>
          <th>{{ t('views.deliverables.col.langue') }}</th>
          <th>{{ t('views.deliverables.col.tlp') }}</th>
          <th>{{ t('views.deliverables.col.statut') }}</th>
          <th class="th-sort" :aria-sort="sortKey === 'created_at' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'" @click="toggleSort('created_at')">
            {{ t('views.deliverables.col.generation') }}<span v-if="sortKey === 'created_at'" class="sort-ind">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
          </th>
          <th class="actions-col"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="d in sorted" :key="d.id" class="row-clickable" @click="viewFor = d">
          <td class="cell-link">{{ typeLabel(d.type) }}</td>
          <td>{{ clientName(d.client_id) }}</td>
          <td>{{ auditName(d.audit_id) }}</td>
          <td>{{ langueLabel(d.langue) }}</td>
          <td><span v-if="d.tlp" :class="['tlp', 'tlp-' + d.tlp]">{{ d.tlp }}</span><span v-else>—</span></td>
          <td><span class="pill" :class="'pill-' + statutTone(d.statut)">{{ statutLabel(d.statut) }}</span></td>
          <td class="gen-date">{{ fmtDate(d.created_at) }}</td>
          <td class="actions" @click.stop>
            <button class="icon-btn-sm" :title="t('views.deliverables.actions.view')" :aria-label="t('views.deliverables.actions.view')" @click="viewFor = d">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
            </button>
            <button class="icon-btn-sm" :title="t('views.deliverables.actions.download')" :aria-label="t('views.deliverables.actions.download')" @click="download(d)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Modal de génération -->
    <DetailDrawer v-if="showGen" :title="t('views.deliverables.gen.title')" :subtitle="t('views.deliverables.eyebrow')" @close="showGen = false">
      <div class="gen-grid">
        <div class="fr">
          <label class="lbl">{{ t('views.deliverables.gen.type') }}</label>
          <select class="field" v-model="form.type">
            <option v-for="v in TYPES" :key="v" :value="v">{{ typeLabel(v) }}</option>
          </select>
        </div>
        <div class="fr">
          <label class="lbl">{{ t('views.deliverables.gen.client') }}</label>
          <RefacSelect :options="clientOptions" v-model="form.client_id" :placeholder="t('views.deliverables.gen.client_search_ph')" />
        </div>
        <div class="fr">
          <label class="lbl">{{ t('views.deliverables.gen.audit') }}
            <span v-if="auditRequired" class="req">*</span><span v-else class="opt">{{ t('views.deliverables.gen.audit_optional') }}</span>
          </label>
          <RefacSelect v-if="form.client_id" :options="auditOptions" v-model="form.audit_id" :placeholder="t('views.deliverables.gen.audit_search_ph')" />
          <div v-else class="audit-locked">{{ t('views.deliverables.gen.audit_locked') }}</div>
        </div>
        <div class="fr">
          <label class="lbl">{{ t('views.deliverables.gen.langue') }}</label>
          <select class="field" v-model="form.langue">
            <option v-for="v in LANGUES" :key="v" :value="v">{{ langueLabel(v) }}</option>
          </select>
        </div>
        <div class="fr">
          <label class="lbl">{{ t('views.deliverables.gen.tlp') }}</label>
          <select class="field" v-model="form.tlp"><option v-for="v in TLPS" :key="v" :value="v">{{ v }}</option></select>
        </div>
      </div>
      <p class="hint">{{ t('views.deliverables.gen.hint') }}</p>

      <template #footer>
        <button class="btn" @click="showGen = false">{{ t('common.cancel') }}</button>
        <button class="btn btn-primary" :disabled="busy" @click="generate">
          {{ busy ? t('views.deliverables.gen.submitting') : t('views.deliverables.gen.submit') }}
        </button>
      </template>
    </DetailDrawer>

    <DeliverableDrawer v-if="viewFor" :deliverable="viewFor"
      :client-name="clientName(viewFor.client_id)" :type-label="typeLabel(viewFor.type)"
      @close="viewFor = null" @open="(d) => { download(d) }" />
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
.msg{font-size:13px;margin:10px 0 0}
.msg.ok{color:var(--green)} .msg.ko{color:var(--red)}
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
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0 14px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:14px 16px;display:flex;flex-direction:column}
.klab{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;line-height:1.25;color:var(--faint);font-weight:var(--eyebrow-weight);min-height:26px}
.kpi-value{font-family:var(--font-data);font-size:30px;font-weight:600;color:var(--heading);line-height:1.1;height:34px;margin-top:6px}
.kpi-value.good{color:var(--green)}
.kpi-foot{font-size:11px;color:var(--muted);margin-top:8px}
.actions-col{width:1%}
.actions{white-space:nowrap;display:flex;gap:6px;justify-content:flex-end}
.icon-btn-sm{border:1px solid var(--border);background:var(--surface);color:var(--muted);
  border-radius:var(--r-mini);width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;cursor:pointer}
.icon-btn-sm:hover{border-color:var(--violet-accent);color:var(--violet-accent)}
.cell-link{cursor:pointer}
.cell-link:hover{color:var(--violet-accent)}
.row-clickable{cursor:pointer}
.row-clickable:hover td{background:var(--surface-2)}
.row-clickable .cell-link{font-weight:500}
.gen-date{color:var(--muted);white-space:nowrap}
.th-sort{cursor:pointer;user-select:none;white-space:nowrap}
.th-sort:hover{color:var(--heading)}
.sort-ind{margin-left:5px;font-size:10.5px;color:var(--violet-accent)}
.gen-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.gen-grid .fr{display:flex;flex-direction:column}
.lbl{display:block;font-size:12px;color:var(--muted);margin-bottom:5px}
.req{color:var(--red)} .opt{color:var(--faint);font-size:11px}
.audit-locked{display:flex;align-items:center;min-height:34px;border:1px dashed var(--border);
  border-radius:var(--r-mini);padding:0 10px;color:var(--faint);font-size:12.5px;background:var(--surface-2)}
.hint{font-size:11.5px;color:var(--faint);margin:14px 0 0;line-height:1.5}
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} }
@media (max-width:640px){ .gen-grid{grid-template-columns:1fr} }
</style>
