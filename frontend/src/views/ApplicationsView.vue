<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'
import { api, ApiError } from '../api/client'
import { useUiStore } from '../stores/ui'
import { useOrgNames } from '../composables/useOrgNames'
import AppDrawer from '../components/AppDrawer.vue'
import EntityForm from '../components/EntityForm.vue'
import RefacSelect from '../components/RefacSelect.vue'
import { fieldsFor } from '../fields'
const { t } = useI18n()
const { enumLabel } = useLabels()

// Applications du périmètre, avec leur posture : vulnérabilités liées (total / hautes /
// ouvertes) et présence dans un audit. Filtres opérationnels (responsable, stack,
// criticité, exposition, audité). Données agrégées et cloisonnées RLS côté serveur.
const ui = useUiStore()
const { preload: preloadOrgs, orgName } = useOrgNames()
const items = ref([])
const loading = ref(true)
const msg = ref(null)

// Filtres client-side. La recherche reste toujours visible ; les autres filtres sont
// regroupés dans un panneau repliable piloté par « Filtres » (aligné sur la page Ressources).
const q = ref('')
const fCrit = ref([])
const fExpo = ref([])
const fOwner = ref([])
const fStack = ref('')
const fAudit = ref([])
const fVuln = ref([])
const showAdvanced = ref(false)
const activeAdvancedCount = computed(() =>
  [fCrit.value, fExpo.value, fOwner.value, fAudit.value, fVuln.value].filter((a) => a.length).length
  + (fStack.value ? 1 : 0))

function toggleIn(arr, val) {
  const i = arr.indexOf(val)
  if (i === -1) arr.push(val); else arr.splice(i, 1)
}

const detailFor = ref(null)
const showForm = ref(false)
const editRecord = ref(null)
const editBusy = ref(null)

const CRIT_TONE = { critique: 'red', haute: 'amber', elevee: 'amber', moyenne: 'cyan', basse: 'green' }
const CRIT_ORDER = ['critique', 'haute', 'elevee', 'moyenne', 'basse', 'faible']
const CRIT_HIGH = ['critique', 'haute']
const EXPO_PUBLIC = ['externe', 'partenaire']

async function load() {
  loading.value = true
  try { items.value = (await api.get('/analytics/applications-coverage' + (ui.clientQuery ? '?' + ui.clientQuery : ''))).items }
  catch (e) { msg.value = e instanceof ApiError && e.status === 403 ? 'Accès refusé.' : (e.message || 'Erreur.') }
  finally { loading.value = false }
}

// Options de filtres dérivées des données présentes (aucune liste figée).
const critValues = computed(() => {
  const present = new Set(items.value.map((a) => String(a.criticite || '').toLowerCase()).filter(Boolean))
  return CRIT_ORDER.filter((c) => present.has(c))
})
const expositions = computed(() => [...new Set(items.value.map((a) => a.exposition).filter(Boolean))].sort())
const owners = computed(() => [...new Set(items.value.map((a) => a.contact_metier).filter(Boolean))].sort())
const ownerOptions = computed(() => owners.value.map((o) => ({ id: o, label: o })))

const filtered = computed(() => items.value.filter((a) => {
  if (fCrit.value.length && !fCrit.value.includes(String(a.criticite || '').toLowerCase())) return false
  if (fExpo.value.length && !fExpo.value.includes(a.exposition)) return false
  if (fOwner.value.length && !fOwner.value.includes(a.contact_metier)) return false
  if (fStack.value && !String(a.stack || '').toLowerCase().includes(fStack.value.toLowerCase())) return false
  if (fAudit.value.length && !fAudit.value.includes(a.audited ? 'yes' : 'no')) return false
  if (fVuln.value.length) {
    const ok = fVuln.value.some((k) =>
      k === 'open' ? a.vuln_open > 0 : k === 'any' ? a.vuln_total > 0 : a.vuln_total === 0)
    if (!ok) return false
  }
  if (q.value) {
    const h = `${a.nom} ${a.code || ''}`.toLowerCase()
    if (!h.includes(q.value.toLowerCase())) return false
  }
  return true
}))

// KPI calculés côté client sur l'ensemble FILTRÉ (résumé live de ce qui est affiché) :
// ils suivent donc les filtres et la recherche. Le total (dénominateur) est aussi le
// nombre d'applications filtrées. Les options de filtres restent, elles, dérivées du
// périmètre complet (`items`) pour ne pas se réduire au fil de la sélection.
const round = (n) => Math.round(n)
const pct = (n, d) => (d ? round((n / d) * 100) : 0)
const kpiTotal = computed(() => filtered.value.length)
const kpiAudited = computed(() => filtered.value.filter((a) => a.audited).length)
const kpiWithVulns = computed(() => filtered.value.filter((a) => a.vuln_open > 0).length)
const kpiCrit = computed(() => filtered.value.filter((a) => CRIT_HIGH.includes(String(a.criticite || '').toLowerCase())).length)
const kpiExposed = computed(() => filtered.value.filter((a) => EXPO_PUBLIC.includes(a.exposition)).length)
// Un ensemble réduit par un filtre/recherche → « de la sélection », sinon « du périmètre ».
const footKey = computed(() => kpiTotal.value !== items.value.length
  ? 'views.applications.kpi.foot_selection'
  : 'views.applications.kpi.foot_scope')
const critTone = (c) => CRIT_TONE[String(c).toLowerCase()] || 'gray'

watch(() => ui.activeClient, load)
onMounted(() => { load(); preloadOrgs() }) // chargement initial (+ noms d'organisations)

async function remove(a) {
  if (!window.confirm(t('views.applications.confirm_delete', { nom: a.nom }))) return
  try {
    await api.remove('applications', a.id)
    if (detailFor.value?.id === a.id) detailFor.value = null
    await load()
  } catch (e) {
    // Le serveur décide (matrice RBAC) : un rôle sans droit S reçoit un 403.
    msg.value = e instanceof ApiError && e.status === 403 ? 'Accès refusé.' : (e.message || 'Erreur.')
  }
}
function openNew() { editRecord.value = null; showForm.value = true }
async function openEdit(a) {
  detailFor.value = null
  editBusy.value = a.id
  try {
    editRecord.value = await api.get(`/applications/${a.id}`)
  } catch (e) {
    msg.value = e instanceof ApiError && e.status === 403 ? 'Accès refusé.' : (e.message || 'Erreur.')
    editBusy.value = null
    return
  }
  editBusy.value = null
  showForm.value = true
}
function onSaved() { showForm.value = false; load() }
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.applications.eyebrow') }}</div>
    <h1>{{ t('views.applications.title') }}</h1>
    <p v-if="msg" class="err">{{ msg }}</p>

    <div class="subrow">
      <p class="subtitle">{{ t('views.applications.subtitle') }}</p>
      <div class="acts">
        <input class="field search" v-model="q" :placeholder="t('av.search')" />
        <button class="filters-toggle" :class="{ open: showAdvanced }" @click="showAdvanced = !showAdvanced">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="10" y1="18" x2="14" y2="18"/></svg>
          {{ t('views.applications.filters') }}
          <span v-if="activeAdvancedCount" class="count-badge sm">{{ activeAdvancedCount }}</span>
          <span class="chevron">{{ showAdvanced ? '⌃' : '⌄' }}</span>
        </button>
        <button class="btn btn-primary" @click="openNew">+ {{ t('av.new_f') }}</button>
        <button class="icon-btn" :title="t('common.refresh')" :aria-label="t('common.refresh')" @click="load">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
        </button>
      </div>
    </div>

    <div class="note">
      <span class="lead">{{ t('views.applications.note.lead') }}</span>
      <ul>
        <li><b>{{ t('views.applications.note.posture_label') }}</b> {{ t('views.applications.note.posture_text') }}</li>
        <li><b>{{ t('views.applications.note.audit_label') }}</b> {{ t('views.applications.note.audit_text') }}</li>
      </ul>
    </div>

    <div v-if="showAdvanced" class="filters-panel">
      <div class="f-row">
        <label class="f-label">{{ t('views.applications.filter_crit') }}</label>
        <div class="chipset">
          <button v-for="c in critValues" :key="c" type="button" :class="['chip-toggle', { on: fCrit.includes(c) }]" @click="toggleIn(fCrit, c)">{{ enumLabel(c) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.applications.filter_expo') }}</label>
        <div class="chipset">
          <button v-for="e in expositions" :key="e" type="button" :class="['chip-toggle', { on: fExpo.includes(e) }]" @click="toggleIn(fExpo, e)">{{ enumLabel(e) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.applications.filter_owner') }}</label>
        <RefacSelect :options="ownerOptions" multiple v-model="fOwner" :placeholder="t('views.applications.filter_owner_ph')" />
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.applications.filter_stack') }}</label>
        <input class="field" v-model="fStack" :placeholder="t('av.stack')" />
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.applications.filter_audit') }}</label>
        <div class="chipset">
          <button type="button" :class="['chip-toggle', { on: fAudit.includes('yes') }]" @click="toggleIn(fAudit, 'yes')">{{ t('av.audited_opt') }}</button>
          <button type="button" :class="['chip-toggle', { on: fAudit.includes('no') }]" @click="toggleIn(fAudit, 'no')">{{ t('av.not_audited') }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.applications.filter_vuln') }}</label>
        <div class="chipset">
          <button type="button" :class="['chip-toggle', { on: fVuln.includes('open') }]" @click="toggleIn(fVuln, 'open')">{{ t('views.applications.filter_vuln_open') }}</button>
          <button type="button" :class="['chip-toggle', { on: fVuln.includes('any') }]" @click="toggleIn(fVuln, 'any')">{{ t('views.applications.filter_vuln_any') }}</button>
          <button type="button" :class="['chip-toggle', { on: fVuln.includes('none') }]" @click="toggleIn(fVuln, 'none')">{{ t('views.applications.filter_vuln_none') }}</button>
        </div>
      </div>
    </div>

    <div class="kpis">
      <div class="kpi">
        <div class="klab">{{ t('views.applications.kpi.total') }}</div>
        <div class="kpi-value">{{ kpiTotal }}<span v-if="kpiTotal !== items.length" class="u">/{{ items.length }}</span></div>
        <div class="kpi-foot">{{ kpiTotal === items.length ? t('views.applications.kpi.total_foot') : t('views.applications.kpi.total_filtered_foot', { total: items.length }) }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.applications.kpi.audited') }}</div>
        <div class="kpi-value">{{ kpiAudited }}<span class="u">/{{ kpiTotal }}</span></div>
        <div class="kpi-foot">{{ t(footKey, { pct: pct(kpiAudited, kpiTotal) }) }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.applications.kpi.vulns_open') }}</div>
        <div class="kpi-value" :class="{ warn: kpiWithVulns }">{{ kpiWithVulns }}<span class="u">/{{ kpiTotal }}</span></div>
        <div class="kpi-foot">{{ t(footKey, { pct: pct(kpiWithVulns, kpiTotal) }) }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.applications.kpi.critiques') }}</div>
        <div class="kpi-value" :class="{ warn: kpiCrit }">{{ kpiCrit }}<span class="u">/{{ kpiTotal }}</span></div>
        <div class="kpi-foot">{{ t(footKey, { pct: pct(kpiCrit, kpiTotal) }) }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.applications.kpi.exposes') }}</div>
        <div class="kpi-value">{{ kpiExposed }}<span class="u">/{{ kpiTotal }}</span></div>
        <div class="kpi-foot">{{ t(footKey, { pct: pct(kpiExposed, kpiTotal) }) }}</div>
      </div>
    </div>

    <p v-if="loading" class="muted">{{ t('common.loading') }}</p>
    <p v-else-if="!filtered.length" class="muted">{{ t('av.none_match') }}</p>

    <table v-else class="atable">
      <thead><tr>
        <th>{{ t('fields.nom') }}</th><th>{{ t('fields.client_id') }}</th><th>{{ t('fields.contact_metier') }}</th><th>{{ t('fields.criticite') }}</th><th>{{ t('fields.exposition') }}</th>
        <th>{{ t('av.col_vulns') }}</th><th>{{ t('av.audit') }}</th><th class="actions-col"></th>
      </tr></thead>
      <tbody>
        <tr v-for="a in filtered" :key="a.id" class="row-clickable" @click="detailFor = a">
          <td class="nom link">{{ a.nom }}</td>
          <td class="sm">{{ orgName(a.client_id) || '—' }}</td>
          <td class="sm">{{ a.contact_metier || '—' }}</td>
          <td><span :class="['pill', 'pill-' + critTone(a.criticite)]">{{ a.criticite || '—' }}</span></td>
          <td class="sm">{{ a.exposition || '—' }}</td>
          <td>
            <span v-if="a.vuln_total" class="vulns">
              <span class="v-tot">{{ a.vuln_total }}</span>
              <span v-if="a.vuln_high" class="v-high" title="Hautes/critiques">{{ a.vuln_high }}⚠</span>
              <span v-if="a.vuln_open" class="v-open" title="Ouvertes">{{ a.vuln_open }} ouv.</span>
            </span>
            <span v-else class="faint">—</span>
          </td>
          <td><span v-if="a.audited" class="pill pill-green">{{ t('av.is_audited') }}</span><span v-else class="faint">{{ t('av.not') }}</span></td>
          <td class="actions" @click.stop>
            <button class="icon-btn-sm" :title="t('common.edit')" :disabled="editBusy === a.id" @click="openEdit(a)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
            </button>
            <button class="icon-btn-sm danger" :title="t('common.delete')" @click="remove(a)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <AppDrawer v-if="detailFor" :app="detailFor" @close="detailFor = null" @edit="openEdit" />
    <EntityForm v-if="showForm" entity="applications" :fields="fieldsFor('applications')"
      :record="editRecord" :title="editRecord ? t('views.applications.edit_title') : t('views.applications.new_title')"
      @saved="onSaved" @close="showForm = false" />
  </div>
</template>

<style scoped>
.sm{font-size:12px}
.subrow{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:8px 0 0}
.subtitle{font-size:13px;color:var(--muted);margin:0}
.acts{display:flex;gap:8px;align-items:center}
.acts .search{height:34px;width:200px}
.note{margin:16px 0 4px;color:var(--muted);font-size:12.5px;line-height:1.55;
  border-left:3px solid var(--violet);padding:2px 0 2px 14px;max-width:92ch}
.note .lead{color:var(--text);font-weight:500}
.note ul{margin:6px 0 0;padding-left:18px}
.note li{margin:3px 0}
.note b{color:var(--c-violet-tx);font-weight:600}
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
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:18px 0 14px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:14px 16px;display:flex;flex-direction:column}
.klab{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;line-height:1.25;color:var(--faint);font-weight:var(--eyebrow-weight);min-height:26px}
.kpi-value{font-family:var(--font-data);font-size:30px;font-weight:600;color:var(--heading);line-height:1.1;height:34px;margin-top:6px}
.kpi-value.warn{color:var(--amber)}
.kpi-value .u{font-size:16px;color:var(--muted);margin-left:3px}
.kpi-foot{font-size:11px;color:var(--muted);margin-top:8px}
.row-clickable{cursor:pointer}
.row-clickable:hover td{background:var(--surface-2)}
.atable{width:100%;border-collapse:collapse}
.atable th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--faint);padding:8px 8px;border-bottom:1px solid var(--border)}
.atable td{padding:8px 8px;border-bottom:1px solid var(--border-2);font-size:12.5px}
.atable .nom{font-weight:600;color:var(--heading)}
.atable .nom.link{cursor:pointer}
.atable .nom.link:hover{color:var(--violet-accent);text-decoration:underline}
.vulns{display:inline-flex;gap:6px;align-items:center;font-family:var(--font-data);font-size:11.5px}
.v-tot{color:var(--heading);font-weight:600}
.v-high{color:var(--red)} .v-open{color:var(--amber)}
.actions-col{width:1%}
.actions{white-space:nowrap;text-align:right}
.actions .icon-btn-sm{margin-left:6px}
.icon-btn-sm{border:1px solid var(--border);background:var(--surface);color:var(--muted);
  border-radius:var(--r-mini);width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;
  transition:border-color var(--t) var(--ease), color var(--t) var(--ease)}
.icon-btn-sm:hover{border-color:var(--violet-accent);color:var(--violet-accent)}
.icon-btn-sm.danger:hover{border-color:var(--red);color:var(--red)}
.icon-btn-sm:disabled{opacity:.5;cursor:not-allowed}
@media (max-width:1100px){ .kpis{grid-template-columns:repeat(3,1fr)} }
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} }
</style>
