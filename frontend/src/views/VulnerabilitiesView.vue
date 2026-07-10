<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, ApiError } from '../api/client'
import { useUiStore } from '../stores/ui'
import { useLabels } from '../composables/useLabels'
import { useOrgNames } from '../composables/useOrgNames'
import { fieldsFor } from '../fields'
import EntityForm from '../components/EntityForm.vue'
import RefacSelect from '../components/RefacSelect.vue'
import VulnDrawer from '../components/VulnDrawer.vue'
import DetailDrawer from '../components/DetailDrawer.vue'
const { t } = useI18n()
const { enumLabel } = useLabels()
const { preload: preloadOrgs, orgName } = useOrgNames()

// Vue vulnérabilités enrichie, portée à l'identique de la maquette (capture d'écran) :
// carte « Vulnérabilités & écarts », filtres repliables (CVE ID, clients, applications,
// sévérité/SLA/statut en puces), colonnes Client/Applications (résolues depuis l'audit
// lié)/Statut, actions de ligne réduites à Modifier/Supprimer (le reste — CIRCL, détail —
// se fait depuis le drawer). Tout reste cloisonné RLS.
const ui = useUiStore()
const items = ref([])
const loading = ref(true)
const msg = ref(null)

// Référentiels locaux pour les filtres et l'affichage (Client/Applications résolus).
const orgOptions = ref([])
const appOptions = ref([])
const appMap = ref({})

// Filtres — alignés sur la maquette : recherche CVE, clients/applications en
// autocomplétion multi-valeurs, sévérité/SLA/statut en puces à sélection multiple.
const fCve = ref('')
const fClients = ref([])
const fApps = ref([])
const fSeverites = ref([])
const fSlas = ref([])
const fStatuts = ref([])
const showFilters = ref(false)
const activeFilterCount = computed(() =>
  (fCve.value ? 1 : 0) + fClients.value.length + fApps.value.length +
  fSeverites.value.length + fSlas.value.length + fStatuts.value.length)

function toggleIn(arr, val) {
  const i = arr.indexOf(val)
  if (i === -1) arr.push(val)
  else arr.splice(i, 1)
}

const STATUT_VULN = ['ouverte', 'en_cours', 'corrigee', 'acceptee', 'faux_positif']
const SLA_LEVELS = ['P1', 'P2', 'P3', 'P4']

// Modales
const showForm = ref(false)
const editRecord = ref(null)
const enrichFor = ref(null) // vuln en cours d'enrichissement (manuel)
const detailFor = ref(null) // vuln affichée en drawer de détail
const editBusy = ref(null)  // id de la vuln en cours de chargement pour édition

const SEV_TONE = { critique: 'red', haute: 'amber', elevee: 'amber', moyenne: 'cyan', basse: 'green' }
const STATUT_TONE = { ouverte: 'red', en_cours: 'cyan', corrigee: 'green', acceptee: 'gray', faux_positif: 'gray' }
const VEX = ['', 'affected', 'not_affected', 'fixed', 'under_investigation']
const VEX_LABEL = { affected: 'Affecté', not_affected: 'Non affecté', fixed: 'Corrigé', under_investigation: 'En analyse' }

const enrich = reactive({ kev: false, kev_ransomware: false, epss_score: null, epss_percentile: null, vex_status: '' })

async function load() {
  loading.value = true
  try { items.value = (await api.get('/vulnerabilities-enriched')).items }
  catch (e) { msg.value = { kind: 'ko', text: e.message } }
  finally { loading.value = false }
}

async function loadFilterOptions() {
  try {
    const rows = await api.list('organisations')
    const list = Array.isArray(rows) ? rows : (rows.items ?? [])
    orgOptions.value = list.map((o) => ({ id: o.id, label: `${o.code || ''} ${o.nom}`.trim() }))
  } catch { orgOptions.value = [] }
  try {
    const rows = await api.list('applications')
    const list = Array.isArray(rows) ? rows : (rows.items ?? [])
    appOptions.value = list.map((a) => ({ id: a.id, label: a.nom }))
    appMap.value = Object.fromEntries(list.map((a) => [a.id, a.nom]))
  } catch { appOptions.value = []; appMap.value = {} }
}
// Résolution des noms d'application. Ce que /vulnerabilities-enriched fournit dans
// v.applications vient désormais de l'audit lié (audit.applications) — c'est ce que
// l'utilisateur voit et filtre ici, pas un champ propre à la vulnérabilité (qu'aucun
// formulaire ne permettait de renseigner : la colonne restait vide auparavant).
function appNames(ids) {
  if (!ids || !ids.length) return '—'
  return ids.map((id) => appMap.value[id] || id).join(', ')
}

const filtered = computed(() => items.value.filter((v) => {
  if (ui.activeClient && v.client_id !== ui.activeClient) return false
  if (fCve.value) {
    const h = `${v.cve || ''} ${v.titre || ''}`.toLowerCase()
    if (!h.includes(fCve.value.toLowerCase())) return false
  }
  if (fClients.value.length && !fClients.value.includes(v.client_id)) return false
  if (fApps.value.length && !(v.applications || []).some((a) => fApps.value.includes(a))) return false
  if (fSeverites.value.length && !fSeverites.value.includes(v.severite)) return false
  if (fSlas.value.length && !fSlas.value.includes(v.sla_niveau)) return false
  if (fStatuts.value.length && !fStatuts.value.includes(v.statut)) return false
  return true
}))

function openNew() { editRecord.value = null; showForm.value = true }
async function openEdit(v) {
  // La ligne de la liste vient de /vulnerabilities-enriched (projection partielle :
  // KEV/EPSS/SSVC/SLA...) — elle ne porte pas description/impact_metier/techniques/
  // decouvreur_id/phase_decouverte/etc. Sans ce rechargement, le formulaire d'édition
  // affichait ces champs vides alors que les données existaient bien en base.
  editBusy.value = v.id
  try {
    editRecord.value = await api.get(`/vulnerabilities/${v.id}`)
  } catch (e) {
    msg.value = { kind: 'ko', text: e.message || "Impossible de charger la vulnérabilité." }
    editBusy.value = null
    return
  }
  editBusy.value = null
  showForm.value = true
}
function onSaved() { showForm.value = false; load() }

async function removeVuln(v) {
  if (!window.confirm(`Supprimer « ${v.titre} » ? Cette action est journalisée.`)) return
  try {
    await api.remove('vulnerabilities', v.id)
    await load()
  } catch (e) {
    msg.value = { kind: 'ko', text: e instanceof ApiError && e.status === 403 ? 'Suppression refusée.' : (e.message || 'Erreur.') }
  }
}

function openEnrich(v) {
  enrichFor.value = v
  Object.assign(enrich, {
    kev: !!v.kev, kev_ransomware: !!v.kev_ransomware,
    epss_score: v.epss_score, epss_percentile: v.epss_percentile,
    vex_status: v.vex_status || '',
  })
}
async function saveEnrich() {
  msg.value = null
  try {
    const r = await api.put(`/vulnerabilities/${enrichFor.value.id}/enrichment`, {
      kev: enrich.kev, kev_ransomware: enrich.kev_ransomware,
      epss_score: enrich.epss_score !== '' ? Number(enrich.epss_score) : null,
      epss_percentile: enrich.epss_percentile !== '' ? Number(enrich.epss_percentile) : null,
      vex_status: enrich.vex_status || null,
    })
    msg.value = { kind: 'ok', text: `Enrichi — décision SSVC : ${r.ssvc_decision}.` }
    enrichFor.value = null
    await load()
  } catch (e) {
    msg.value = { kind: 'ko', text: e instanceof ApiError && e.status === 403 ? 'Enrichissement réservé (droit d’édition).' : (e.message || 'Erreur.') }
  }
}

// Export CSV de la vue courante (respecte les filtres actifs), séparé de l'export STIX
// (qui n'a pas de sens ici — ce ne sont pas des scénarios).
function downloadCsv(rows, filename) {
  const headers = ['Nom', 'CVE', 'Client', 'Applications', 'Sévérité', 'CVSS', 'SLA', 'Statut']
  const esc = (s) => `"${String(s ?? '').replace(/"/g, '""')}"`
  const lines = [headers.join(',')]
  for (const v of rows) {
    lines.push([
      v.titre, v.cve || '', v.client_id ? orgName(v.client_id) : '', appNames(v.applications),
      v.severite ? enumLabel(v.severite) : '', v.cvss_score ?? '', v.sla_niveau || '',
      v.statut ? enumLabel(v.statut) : '',
    ].map(esc).join(','))
  }
  const blob = new Blob(['\uFEFF' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}
function exportCsv() { downloadCsv(filtered.value, 'vulnerabilites.csv') }

onMounted(async () => {
  await Promise.all([load(), loadFilterOptions(), preloadOrgs()])
})
</script>

<template>
  <div>
    <div class="head">
      <div>
        <div class="eyebrow">{{ t('views.vulnerabilities.eyebrow') }}</div>
        <h1>{{ t('views.vulnerabilities.title') }}</h1>
        <p class="subtitle">{{ t('views.vulnerabilities.subtitle') }}</p>
      </div>
      <div class="head-actions">
        <button class="btn" @click="exportCsv">Exporter</button>
        <button class="btn btn-primary" @click="openNew">+ Nouvelle vulnérabilité</button>
      </div>
    </div>

    <p v-if="msg" :class="['msg', msg.kind]">{{ msg.text }}</p>

    <div class="panel">
      <div class="panel-head">
        <div class="panel-title">{{ t('views.vulnerabilities.title') }}</div>
        <div class="panel-meta"><span class="count-badge">{{ filtered.length }}</span> vulnérabilité(s)</div>
      </div>

      <button class="filters-toggle" :class="{ open: showFilters }" @click="showFilters = !showFilters">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="4" y1="6" x2="20" y2="6"/><circle cx="9" cy="6" r="2" fill="currentColor" stroke="none"/>
          <line x1="4" y1="12" x2="20" y2="12"/><circle cx="15" cy="12" r="2" fill="currentColor" stroke="none"/>
          <line x1="4" y1="18" x2="20" y2="18"/><circle cx="11" cy="18" r="2" fill="currentColor" stroke="none"/>
        </svg>
        Filtres
        <span v-if="activeFilterCount" class="count-badge sm">{{ activeFilterCount }}</span>
        <span class="chevron">{{ showFilters ? '⌃' : '⌄' }}</span>
      </button>

      <div v-if="showFilters" class="filters-panel">
        <div class="f-row">
          <label class="f-label">CVE ID</label>
          <input class="field" v-model="fCve" placeholder="Rechercher un CVE…" />
        </div>
        <div class="f-row">
          <label class="f-label">Clients</label>
          <RefacSelect :options="orgOptions" multiple placeholder="Ajouter un client…" v-model="fClients" />
        </div>
        <div class="f-row">
          <label class="f-label">Applications</label>
          <RefacSelect :options="appOptions" multiple placeholder="Ajouter une application…" v-model="fApps" />
        </div>
        <div class="f-row">
          <label class="f-label">Sévérité</label>
          <div class="chipset">
            <button v-for="s in ['faible', 'moyenne', 'haute', 'critique']" :key="s" type="button"
                    :class="['chip-toggle', { on: fSeverites.includes(s) }]" @click="toggleIn(fSeverites, s)">
              {{ enumLabel(s) }}
            </button>
          </div>
        </div>
        <div class="f-row">
          <label class="f-label">SLA</label>
          <div class="chipset">
            <button v-for="p in SLA_LEVELS" :key="p" type="button"
                    :class="['chip-toggle', { on: fSlas.includes(p) }]" @click="toggleIn(fSlas, p)">{{ p }}</button>
          </div>
        </div>
        <div class="f-row">
          <label class="f-label">Statut</label>
          <div class="chipset">
            <button v-for="st in STATUT_VULN" :key="st" type="button"
                    :class="['chip-toggle', { on: fStatuts.includes(st) }]" @click="toggleIn(fStatuts, st)">
              {{ enumLabel(st) }}
            </button>
          </div>
        </div>
      </div>

      <p v-if="loading" class="muted">{{ t('common.loading') }}</p>
      <p v-else-if="!filtered.length" class="muted">{{ t('vv.none_match') }}</p>

      <table v-else class="vtable">
        <thead><tr>
          <th>{{ t('fields.nom') }}</th><th>CVE</th><th>Client</th><th>Applications</th>
          <th>{{ t('fields.severite') }}</th><th>CVSS</th><th>SLA</th>
          <th>{{ t('fields.statut') }}</th><th></th>
        </tr></thead>
        <tbody>
          <tr v-for="v in filtered" :key="v.id" class="row-clickable" :class="{ over: v.sla_overdue }" @click="detailFor = v">
            <td class="nom">{{ v.titre }}</td>
            <td class="mono cve-cell">
              <span v-if="v.cve">{{ v.cve }}</span><span v-else class="faint">–</span>
              <span v-if="v.kev" class="kev-dot" :title="v.kev_ransomware ? 'CISA KEV — utilisée par des rançongiciels' : 'CISA KEV'"></span>
            </td>
            <td>{{ v.client_id ? orgName(v.client_id) : '—' }}</td>
            <td class="apps-cell">{{ appNames(v.applications) }}</td>
            <td><span :class="['pill', 'pill-' + (SEV_TONE[String(v.severite).toLowerCase()] || 'gray')]">{{ enumLabel(v.severite) }}</span></td>
            <td class="mono">{{ v.cvss_score != null ? v.cvss_score.toFixed(1) : '—' }}</td>
            <td><span v-if="v.sla_niveau" :class="['pill', v.sla_overdue ? 'pill-red' : 'pill-gray']">{{ v.sla_niveau }}<span v-if="v.sla_overdue"> !</span></span>
              <span v-else class="faint">—</span>
            </td>
            <td><span :class="['pill', 'pill-' + (STATUT_TONE[v.statut] || 'gray')]">{{ enumLabel(v.statut) }}</span></td>
            <td class="ta" @click.stop>
              <button class="icon-btn-sm" title="Modifier" :disabled="editBusy === v.id" @click="openEdit(v)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
              </button>
              <button class="icon-btn-sm danger" title="Supprimer" @click="removeVuln(v)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Formulaire création/édition -->
    <EntityForm
      v-if="showForm" entity="vulnerabilities" :fields="fieldsFor('vulnerabilities')"
      :record="editRecord" :title="editRecord ? 'Modifier la vulnérabilité' : 'Nouvelle vulnérabilité'"
      @saved="onSaved" @close="showForm = false"
    />

    <!-- Détail (drawer) : CIRCL, enrichissement manuel et édition s'y font désormais -->
    <VulnDrawer v-if="detailFor" :vuln="detailFor" @close="detailFor = null"
      @saved="load"
      @edit="(v) => { detailFor = null; openEdit(v) }"
      @manual-enrich="(v) => { detailFor = null; openEnrich(v) }" />

    <!-- Éditeur d'enrichissement manuel -->
    <DetailDrawer v-if="enrichFor" :title="'Enrichissement — ' + enrichFor.titre"
                  subtitle="Vulnérabilité" @close="enrichFor = null">
      <p class="hint">CVSS {{ enrichFor.cvss_score != null ? enrichFor.cvss_score.toFixed(1) : '—' }} · la décision SSVC est recalculée automatiquement (CVSS + KEV + EPSS).</p>
      <div class="egrid">
        <label class="chk"><input type="checkbox" v-model="enrich.kev" /> Présente au catalogue CISA KEV (exploitation active)</label>
        <label class="chk"><input type="checkbox" v-model="enrich.kev_ransomware" :disabled="!enrich.kev" /> Utilisée par des rançongiciels</label>
        <div class="frow"><label>Score EPSS (0–1)</label><input class="field" type="number" step="0.001" min="0" max="1" v-model="enrich.epss_score" /></div>
        <div class="frow"><label>Percentile EPSS (0–1)</label><input class="field" type="number" step="0.001" min="0" max="1" v-model="enrich.epss_percentile" /></div>
        <div class="frow"><label>{{ t('fields.statut') }} VEX</label>
          <select class="field" v-model="enrich.vex_status">
            <option v-for="x in VEX" :key="x" :value="x">{{ x ? (VEX_LABEL[x] || x) : '—' }}</option>
          </select>
        </div>
      </div>
      <template #footer>
        <button class="btn" @click="enrichFor = null">{{ t('common.cancel') }}</button>
        <button class="btn btn-primary" @click="saveEnrich">{{ t('common.save') }}</button>
      </template>
    </DetailDrawer>
  </div>
</template>

<style scoped>
.mono{font-family:var(--font-data);font-size:12px}
.head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.subtitle{font-size:13px;color:var(--muted);margin:2px 0 0}
.head-actions{display:flex;gap:8px;flex:0 0 auto}
.msg{font-size:13px;margin:8px 0} .msg.ok{color:var(--green)} .msg.ko{color:var(--red)} .msg.warn{color:var(--amber)}

.panel{margin-top:16px}
.panel-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:14px}
.panel-title{font-family:var(--font-display);color:var(--heading);font-weight:600;font-size:15px}
.panel-meta{font-size:12px;color:var(--faint)}
.count-badge{display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:20px;
  border-radius:99px;background:var(--surface-3);color:var(--text);font-size:11px;font-family:var(--font-data);padding:0 6px;margin-left:4px}
.count-badge.sm{min-width:16px;height:16px;font-size:10px;background:var(--violet);color:#fff}

.filters-toggle{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--violet);
  background:var(--c-violet-bg);color:var(--violet-accent);border-radius:var(--r-mini);
  padding:8px 14px;font-size:13px;font-weight:600;cursor:pointer;margin-bottom:4px}
.filters-toggle .chevron{font-size:11px;margin-left:2px}
.filters-panel{display:flex;flex-direction:column;gap:14px;padding:16px 2px 6px;margin-bottom:6px}
.f-row{display:flex;flex-direction:column;gap:6px}
.f-label{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.chipset{display:flex;flex-wrap:wrap;gap:8px}
.chip-toggle{border:1px solid var(--border);background:var(--surface);color:var(--muted);
  border-radius:var(--r-pill);padding:6px 14px;font-size:12.5px;cursor:pointer;transition:border-color var(--t) var(--ease)}
.chip-toggle:hover{border-color:var(--violet)}
.chip-toggle.on{background:var(--c-violet-bg);border-color:var(--c-violet-bd);color:var(--c-violet-tx);font-weight:600}

.vtable{width:100%;border-collapse:collapse;margin-top:14px}
.vtable th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--faint);padding:8px 8px;border-bottom:1px solid var(--border)}
.vtable td{padding:9px 8px;border-bottom:1px solid var(--border-2);font-size:12.5px}
.vtable tr.over td{background:var(--c-red-bg)}
.vtable .nom{font-family:var(--font-data);color:var(--heading);font-weight:600}
.row-clickable{cursor:pointer}
.row-clickable:hover td{background:var(--surface-2)}
.vtable tr.over.row-clickable:hover td{background:var(--c-red-bg)}
.cve-cell{display:flex;align-items:center;gap:5px}
.kev-dot{width:6px;height:6px;border-radius:50%;background:var(--red);display:inline-block}
.apps-cell{color:var(--muted);max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

.ta{text-align:right;white-space:nowrap;display:flex;gap:6px;justify-content:flex-end}
.icon-btn-sm{border:1px solid var(--border);background:var(--surface);color:var(--muted);
  border-radius:var(--r-mini);width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;cursor:pointer}
.icon-btn-sm:hover{border-color:var(--violet-accent);color:var(--violet-accent)}
.icon-btn-sm.danger:hover{border-color:var(--red);color:var(--red)}
.icon-btn-sm:disabled{opacity:.5;cursor:not-allowed}

.hint{font-size:12px;color:var(--faint);margin-bottom:12px}
.egrid{display:flex;flex-direction:column;gap:12px}
.chk{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--text)}
.frow{display:flex;flex-direction:column;gap:4px}
.frow label{font-size:12px;color:var(--muted)}
@media (max-width:820px){ .apps-cell{max-width:120px} }
</style>
