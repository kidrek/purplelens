<script setup>
import { onMounted, onBeforeUnmount, ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import RefacSelect from '../components/RefacSelect.vue'
import JournalStats from '../components/JournalStats.vue'
import { useAuthStore } from '../stores/auth'
import { api, ApiError } from '../api/client'

// Le journal est consultable (lecture seule pour tous les rôles, y compris admin).
// Le filtrage et l'export sont décidés côté serveur ; la page ne fait qu'afficher.
const { t } = useI18n()
const auth = useAuthStore()

const entries = ref([])
const stats = ref(null)
const loading = ref(true)
const error = ref(null)
const verify = ref(null)
const msg = ref(null)               // { kind: 'ok'|'ko'|'warn', text }

// ── Filtres (envoyés au serveur) ────────────────────────────────────────────
const showFilters = ref(false)
const q = ref('')
const fDomain = ref([])
const fResult = ref('')             // '' | 'ok' | 'denied'
const fActors = ref([])
const fFrom = ref('')
const fTo = ref('')

const DOMAINS = ['auth', 'evidence', 'deliverable', 'admin', 'reference', 'scenario', 'journal']
const RESULTS = ['ok', 'denied']

function toggleIn(arr, val) {
  const i = arr.indexOf(val)
  if (i === -1) arr.push(val); else arr.splice(i, 1)
}
function toggleResult(val) { fResult.value = fResult.value === val ? '' : val }

const activeFilterCount = computed(() =>
  (fDomain.value.length ? 1 : 0) + (fResult.value ? 1 : 0) +
  (fActors.value.length ? 1 : 0) + (fFrom.value || fTo.value ? 1 : 0))

// Options d'acteur : accumulées au fil des chargements (l'API filtrée ne renvoie
// qu'un sous-ensemble ; on ne retire jamais un acteur déjà vu pour garder un choix stable).
const knownActors = ref(new Set())
const actorOptions = computed(() =>
  [...knownActors.value].sort((a, b) => a.localeCompare(b)).map((a) => ({ id: a, label: a })))

// ── Requête serveur ─────────────────────────────────────────────────────────
function buildParams(withScope) {
  const p = new URLSearchParams()
  if (withScope) p.set('scope', withScope)
  const needle = q.value.trim()
  if (needle) p.set('q', needle)
  for (const d of fDomain.value) p.append('domain', d)
  if (fResult.value) p.set('result', fResult.value)
  for (const a of fActors.value) p.append('actor', a)
  if (fFrom.value) p.set('date_from', fFrom.value)
  if (fTo.value) p.set('date_to', fTo.value)
  const qs = p.toString()
  return qs ? '?' + qs : ''
}

async function load() {
  loading.value = true; error.value = null
  try {
    const d = await api.journal(buildParams())
    const items = Array.isArray(d) ? d : (d?.items ?? [])
    entries.value = items
    for (const e of items) if (e.actor_label) knownActors.value.add(e.actor_label)
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? t('common.forbidden') : e.message
  } finally { loading.value = false }
}

async function loadStats() {
  try { stats.value = await api.journalStats() } catch { stats.value = null }
}

async function runVerify() {
  msg.value = null
  try { verify.value = await api.journalVerify() }
  catch (e) { verify.value = { intact: false, error: e.message } }
}

function refreshAll() { load(); loadStats() }

// Rechargement débouncé sur changement de filtre / recherche.
let timer = null
watch([q, fDomain, fResult, fActors, fFrom, fTo], () => {
  clearTimeout(timer)
  timer = setTimeout(load, 300)
}, { deep: true })

// ── Export JSON (backup manuel) — rôles globaux + step-up ────────────────────
const exportOpen = ref(false)
const exportWrap = ref(null)
const otp = ref('')
const pendingAction = ref(null)

function downloadJson(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

async function withStepUp(action) {
  msg.value = null
  try {
    await action()
    pendingAction.value = null
    return true
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      pendingAction.value = action
      msg.value = { kind: 'warn', text: t('common.step_up') }
      return false
    }
    msg.value = { kind: 'ko', text: e instanceof ApiError && e.status === 403 ? t('views.journal.export.denied') : e.message }
    return false
  }
}

async function confirmStepUp() {
  try {
    await api.stepUp(otp.value)
    otp.value = ''
    const action = pendingAction.value
    if (action) await withStepUp(action)
  } catch {
    msg.value = { kind: 'ko', text: 'Code TOTP refusé.' }
  }
}

function doExport(scope) {
  exportOpen.value = false
  const qs = scope === 'filtered' ? buildParams('filtered') : '?scope=full'
  return withStepUp(async () => {
    const dump = await api.journalExport(qs)
    downloadJson(dump, `journal-export-${scope}-${dump.generated_at || ''}.json`)
    msg.value = { kind: 'ok', text: t('views.journal.export.done', { count: dump.count }) }
  })
}

function onDocClick(ev) {
  if (exportOpen.value && exportWrap.value && !exportWrap.value.contains(ev.target)) exportOpen.value = false
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  load(); loadStats(); runVerify()
})
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.journal.eyebrow') }}</div>
    <h1>{{ t('views.journal.title') }}</h1>
    <div class="subrow">
      <p class="subtitle">{{ t('views.journal.subtitle') }}</p>
      <div class="acts">
        <label class="search">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/></svg>
          <input v-model="q" type="search" :placeholder="t('views.journal.search_ph')" />
        </label>
        <button class="filters-toggle" :class="{ open: showFilters }" @click="showFilters = !showFilters">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="10" y1="18" x2="14" y2="18"/></svg>
          {{ t('views.journal.filters') }}
          <span v-if="activeFilterCount" class="count-badge sm">{{ activeFilterCount }}</span>
          <span class="chevron">{{ showFilters ? '⌃' : '⌄' }}</span>
        </button>
        <button class="icon-btn primary" :title="t('views.journal.verify')" :aria-label="t('views.journal.verify')" @click="runVerify">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l7 3v6c0 4-3 6.5-7 9-4-2.5-7-5-7-9V6z"/><path d="m9 12 2 2 4-4"/></svg>
        </button>
        <div ref="exportWrap" class="export-wrap">
          <button class="icon-btn wide" :title="t('views.journal.export.label')" :aria-label="t('views.journal.export.label')" @click="exportOpen = !exportOpen">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12"/><path d="m7 12 5 4 5-4"/><path d="M5 21h14"/></svg>
            <span class="chevron">{{ exportOpen ? '⌃' : '⌄' }}</span>
          </button>
          <div v-if="exportOpen" class="export-menu">
            <button class="export-item" @click="doExport('full')">{{ t('views.journal.export.full') }}</button>
            <button class="export-item" @click="doExport('filtered')">{{ t('views.journal.export.filtered') }}</button>
          </div>
        </div>
        <button class="icon-btn" :title="t('common.refresh')" :aria-label="t('common.refresh')" @click="refreshAll">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
        </button>
      </div>
    </div>

    <div class="note">
      <span class="lead">{{ t('views.journal.note.lead') }}</span>
      <ul>
        <li><b>{{ t('views.journal.note.contenu_label') }}</b> {{ t('views.journal.note.contenu_text') }}</li>
        <li><b>{{ t('views.journal.note.garantie_label') }}</b> {{ t('views.journal.note.garantie_text') }}</li>
      </ul>
    </div>

    <!-- Step-up : demandé par le serveur pour l'export (action à haut risque). -->
    <div v-if="pendingAction" class="stepup">
      <b>Réauthentification requise</b> — l'export du journal est à haut risque.
      <div class="row">
        <input class="otpf" v-model="otp" inputmode="numeric" placeholder="Code TOTP" @keyup.enter="confirmStepUp" />
        <button class="btn btn-primary" @click="confirmStepUp">Confirmer</button>
        <button class="btn" @click="pendingAction = null">{{ t('common.cancel') }}</button>
      </div>
      <p class="hint" v-if="!auth.user?.mfa">
        Votre compte n'a pas encore de TOTP : enrôlez-le d'abord dans « Mon compte ».
      </p>
    </div>

    <p v-if="msg" :class="['msg', msg.kind]">{{ msg.text }}</p>

    <div v-if="showFilters" class="filters-panel">
      <div class="f-row">
        <label class="f-label">{{ t('views.journal.filter_domain') }}</label>
        <div class="chipset">
          <button v-for="d in DOMAINS" :key="d" type="button" :class="['chip-toggle', { on: fDomain.includes(d) }]" @click="toggleIn(fDomain, d)">{{ t('views.journal.domains.' + d) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.journal.filter_result') }}</label>
        <div class="chipset">
          <button v-for="r in RESULTS" :key="r" type="button" :class="['chip-toggle', { on: fResult === r }]" @click="toggleResult(r)">{{ t('views.journal.results.' + r) }}</button>
        </div>
      </div>
      <div class="f-row">
        <label class="f-label">{{ t('views.journal.filter_actor') }}</label>
        <RefacSelect :options="actorOptions" multiple v-model="fActors" :placeholder="t('views.journal.filter_actor_ph')" />
      </div>
      <div class="f-row wide">
        <label class="f-label">{{ t('views.journal.filter_periode') }}</label>
        <div class="periode">
          <span class="sep">{{ t('views.journal.filter_from') }}</span>
          <input class="date-in" type="date" v-model="fFrom" />
          <span class="sep">{{ t('views.journal.filter_to') }}</span>
          <input class="date-in" type="date" v-model="fTo" />
        </div>
      </div>
    </div>

    <JournalStats :stats="stats" :verify="verify" />

    <p v-if="loading" class="muted">{{ t('common.loading') }}</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <table v-else>
      <thead><tr>
        <th>{{ t('views.journal.col.seq') }}</th>
        <th>{{ t('views.journal.col.event') }}</th>
        <th>{{ t('views.journal.col.actor') }}</th>
        <th>{{ t('views.journal.col.subject') }}</th>
        <th>{{ t('views.journal.col.hash') }}</th>
        <th>{{ t('views.journal.col.date') }}</th>
      </tr></thead>
      <tbody>
        <tr v-for="e in entries" :key="e.seq || e.id">
          <td class="mono">{{ e.seq }}</td>
          <td><span class="pill pill-violet">{{ e.event_type }}</span></td>
          <td>{{ e.actor_label || '—' }}</td>
          <td>{{ e.subject || '—' }}</td>
          <td class="mono">{{ String(e.curr_hash || '').slice(0, 14) }}…</td>
          <td class="mono">{{ e.created_at }}</td>
        </tr>
      </tbody>
    </table>
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
/* Variante primaire (action « Vérifier ») : même dégradé que .btn-primary. */
.icon-btn.primary{color:#fff;border:0}
.icon-btn.primary:hover{color:#fff}
body[data-theme="light"] .icon-btn.primary{background:linear-gradient(180deg,#8B49F0,#7C3AED)}
body[data-theme="dark"] .icon-btn.primary{background:linear-gradient(180deg,#8B5CF6,#7C3AED);
  box-shadow:0 0 0 1px rgba(167,139,250,.25),0 2px 16px rgba(124,58,237,.35)}
/* Variante « large » pour loger l'icône + le chevron (export). */
.icon-btn.wide{width:auto;padding:0 10px;gap:5px}
.filters-toggle{display:inline-flex;align-items:center;gap:8px;height:34px;border:1px solid var(--violet);
  background:var(--c-violet-bg);color:var(--violet-accent);border-radius:var(--r-pill);
  padding:0 14px;font-size:13px;font-weight:600;cursor:pointer}
.filters-toggle .chevron{font-size:11px;margin-left:2px}
.chevron{font-size:11px}
.export-wrap{position:relative}
.export-wrap .btn{display:inline-flex;align-items:center;gap:6px}
.export-menu{position:absolute;top:calc(100% + 6px);right:0;z-index:30;min-width:210px;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);
  box-shadow:var(--shadow);padding:6px;display:flex;flex-direction:column;gap:2px}
.export-item{display:block;width:100%;text-align:left;border:none;background:transparent;color:var(--text);
  font-size:12.5px;padding:8px 10px;border-radius:var(--r-mini);cursor:pointer}
.export-item:hover{background:var(--surface-2);color:var(--violet-accent)}
.filters-panel{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;
  padding:16px;margin:12px 0 0;border:1px solid var(--border);border-radius:var(--r-card);background:var(--surface-2)}
.f-row{display:flex;flex-direction:column;gap:6px}
.f-row.wide{grid-column:1/-1;border-top:1px solid var(--border-2);padding-top:12px}
.f-label{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.chipset{display:flex;flex-wrap:wrap;gap:8px}
.chip-toggle{border:1px solid var(--border);background:var(--surface);color:var(--muted);
  border-radius:var(--r-pill);padding:6px 14px;font-size:12.5px;cursor:pointer;transition:border-color var(--t) var(--ease)}
.chip-toggle:hover{border-color:var(--violet)}
.chip-toggle.on{background:var(--c-violet-bg);border-color:var(--c-violet-bd);color:var(--c-violet-tx);font-weight:600}
.periode{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.periode .sep{font-size:12px;color:var(--muted)}
.date-in{height:32px;border:1px solid var(--border);background:var(--surface);border-radius:var(--r-pill);
  padding:0 10px;font-size:12.5px;color:var(--text);font-family:var(--font-body)}
.date-in:focus{outline:none;border-color:var(--violet)}
.count-badge{display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:20px;
  border-radius:99px;background:var(--surface-3);color:var(--text);font-size:11px;font-family:var(--font-data);padding:0 6px;margin-left:4px}
.count-badge.sm{min-width:16px;height:16px;font-size:10px;background:var(--violet);color:#fff}
.stepup{border-left:3px solid var(--violet);background:var(--surface-2);border-radius:var(--r-card);
  padding:14px 16px;margin:14px 0 0;font-size:13px;color:var(--text)}
.stepup .row{display:flex;gap:10px;margin-top:10px;align-items:center;flex-wrap:wrap}
.stepup .hint{font-size:11.5px;color:var(--muted);margin:8px 0 0}
.otpf{max-width:160px;height:34px;border:1px solid var(--border);background:var(--surface);
  border-radius:var(--r-pill);padding:0 12px;font-size:13px;color:var(--text);font-family:var(--font-data)}
.msg{font-size:13px;margin:12px 0 0}
.msg.ok{color:var(--green)} .msg.ko{color:var(--red)} .msg.warn{color:var(--amber)}
.err{color:var(--red);font-size:13px;margin:10px 0 0}
.mono{font-family:var(--font-data)}
</style>
