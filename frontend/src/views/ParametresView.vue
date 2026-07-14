<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, ApiError } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()

// Page Paramètres → « Référentiels de sécurité ». Liste l'état des catalogues (ATT&CK,
// D3FEND, OWASP, CWE, CAPEC) et permet à un administrateur de les importer/actualiser
// depuis le socle embarqué (peuple les tables ref_* utilisées par les formulaires).
const auth = useAuthStore()
const { locale } = useI18n()

const catalogs = ref([])
const loading = ref(true)
const busy = ref(null) // id en cours d'import, ou 'all'
const syncBusy = ref(null) // id en cours de sync en ligne
const SYNCABLE = ['attack', 'd3fend', 'attack_groups', 'misp_actors'] // catalogues synchronisables en ligne
const msg = ref(null)

const isAdmin = computed(() => auth.role === 'admin')

// Libellés bilingues des catalogues.
const META = {
  owasp: { fr: ['OWASP Top 10', 'Les dix risques applicatifs web les plus critiques (édition 2021).'],
           en: ['OWASP Top 10', 'The ten most critical web application security risks (2021 edition).'] },
  cwe: { fr: ['CWE Top 25', 'Faiblesses logicielles les plus dangereuses (édition 2023).'],
         en: ['CWE Top 25', 'Most dangerous software weaknesses (2023 edition).'] },
  capec: { fr: ['CAPEC', "Schémas d'attaque courants (sous-ensemble)."],
           en: ['CAPEC', 'Common attack patterns (subset).'] },
  attack: { fr: ['MITRE ATT&CK Enterprise', 'Socle de techniques adverses par tactique.'],
            en: ['MITRE ATT&CK Enterprise', 'Baseline of adversary techniques by tactic.'] },
  attack_groups: { fr: ['MITRE ATT&CK Groups', 'Acteurs de la menace et leurs TTPs connues (relations « uses »).'],
                   en: ['MITRE ATT&CK Groups', 'Threat actors and their known TTPs (via "uses" relationships).'] },
  misp_actors: { fr: ['MISP Threat Actors', 'Acteurs de la menace et synonymes (galaxie MISP).'],
                 en: ['MISP Threat Actors', 'Threat actors and synonyms (MISP galaxy).'] },
  d3fend: { fr: ['MITRE D3FEND', 'Contre-mesures défensives (socle).'],
            en: ['MITRE D3FEND', 'Defensive countermeasures (baseline).'] },
}
const GROUPS = [
  { id: 'vuln', fr: 'Vulnérabilités & faiblesses', en: 'Vulnerabilities & weaknesses' },
  { id: 'attack', fr: 'Techniques adverses', en: 'Adversary techniques' },
  { id: 'd3fend', fr: 'Défense', en: 'Defense' },
]

const name = (id) => (META[id]?.[locale.value] || META[id]?.fr || [id])[0]
const desc = (id) => (META[id]?.[locale.value] || META[id]?.fr || ['', ''])[1]
const groupLabel = (g) => { const x = GROUPS.find((y) => y.id === g); return x ? x[locale.value] || x.fr : g }
const byGroup = (g) => catalogs.value.filter((c) => c.group === g)
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString(locale.value) : '—')

async function load() {
  loading.value = true
  try {
    catalogs.value = (await api.get('/reference/catalogs')).catalogs
  } catch (e) {
    msg.value = { kind: 'ko', text: e.message || 'Erreur de chargement.' }
  } finally {
    loading.value = false
  }
}

async function importOne(id) {
  if (!isAdmin.value) return
  busy.value = id; msg.value = null
  try {
    const r = await api.post(`/reference/${id}/import`)
    msg.value = { kind: 'ok', text: `${name(id)} : ${r.entries} entrée(s) chargée(s).` }
    await load()
  } catch (e) {
    msg.value = { kind: 'ko', text: e instanceof ApiError && e.status === 403 ? 'Réservé à l’administrateur.' : (e.message || 'Erreur.') }
  } finally {
    busy.value = null
  }
}

async function syncOnline(id) {
  if (!isAdmin.value) return
  syncBusy.value = id; msg.value = null
  try {
    const r = await api.post(`/reference/${id}/sync`)
    msg.value = r.source === 'fallback'
      ? { kind: 'warn', text: `Source amont injoignable — socle embarqué chargé (${r.entries} entrées).` }
      : { kind: 'ok', text: `${name(id)} synchronisé depuis MITRE : ${r.entries} entrées.` }
    await load()
  } catch (e) {
    msg.value = { kind: 'ko', text: e instanceof ApiError && e.status === 403 ? 'Réservé à l’administrateur.' : (e.message || 'Erreur de synchronisation.') }
  } finally {
    syncBusy.value = null
  }
}

async function importAll() {
  if (!isAdmin.value) return
  busy.value = 'all'; msg.value = null
  try {
    const r = await api.post('/reference/import-all')
    const imp = r.imported || {}
    const up = Object.values(imp).filter((x) => x?.source === 'upstream').length
    const fb = Object.values(imp).filter((x) => x?.source === 'fallback').length
    msg.value = up
      ? { kind: fb ? 'warn' : 'ok',
          text: `Référentiels synchronisés — ${up} depuis MITRE en ligne${fb ? `, ${fb} en repli sur le socle (source injoignable)` : ''}.` }
      : { kind: 'warn', text: 'Sources MITRE injoignables — tous les catalogues rechargés depuis le socle embarqué.' }
    await load()
  } catch (e) {
    msg.value = { kind: 'ko', text: e instanceof ApiError && e.status === 403 ? 'Réservé à l’administrateur.' : (e.message || 'Erreur.') }
  } finally {
    busy.value = null
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.parametres.eyebrow') }}</div>
    <h1>{{ t('views.parametres.title') }}</h1>
    <p class="intro">Cataloguez et actualisez les référentiels locaux (ATT&CK, D3FEND, OWASP, CWE, CAPEC)
      utilisés dans les formulaires et l'analytique. Le socle est embarqué avec le produit ; l'import est idempotent.</p>

    <p v-if="msg" :class="['msg', msg.kind]">{{ msg.text }}</p>

    <!-- Synchroniser tout -->
    <div class="ref-sync panel">
      <div class="sync-txt">
        <b>Tout synchroniser</b> — ATT&CK, D3FEND, ATT&CK Groups et MISP Actors depuis les sources
        en ligne (repli sur le socle si hors-ligne), OWASP / CWE / CAPEC depuis le socle embarqué.
      </div>
      <button class="btn btn-primary" :disabled="!isAdmin || busy" @click="importAll">
        <span v-if="busy === 'all'" class="spin"></span>
        {{ busy === 'all' ? 'Actualisation…' : 'Tout synchroniser' }}
      </button>
    </div>
    <p v-if="!isAdmin" class="ro">Consultation seule — l'import des référentiels est réservé à l'administrateur.</p>

    <p v-if="loading" class="muted">Chargement…</p>

    <template v-else>
      <div v-for="g in GROUPS" :key="g.id" class="ref-group">
        <div v-if="byGroup(g.id).length" class="eyebrow group-title">{{ groupLabel(g.id) }}</div>
        <div v-for="c in byGroup(g.id)" :key="c.id" class="ref-card">
          <span :class="['ref-badge', 'pill-' + c.tone]">{{ c.badge }}</span>
          <div class="ref-main">
            <div class="ref-name">{{ name(c.id) }}</div>
            <div class="ref-desc">{{ desc(c.id) }}</div>
            <div class="ref-meta">
              <span class="ref-dot" :class="{ on: c.imported }"></span>
              <span>{{ c.imported ? 'Importé' : 'Non importé' }}</span>
              <span class="sep">·</span>
              <span>Mis à jour : <b>{{ fmtDate(c.updated_at) }}</b></span>
              <span class="sep">·</span>
              <span>Source : {{ c.source }}</span>
              <span class="sep">·</span>
              <span class="data">{{ c.count }} / {{ c.available }} entrée(s)</span>
            </div>
          </div>
          <div class="card-actions">
            <button
              v-if="SYNCABLE.includes(c.id)" class="btn primary-ghost"
              :disabled="!isAdmin || busy || syncBusy" @click="syncOnline(c.id)"
              title="Récupérer le catalogue complet depuis MITRE"
            >
              <span v-if="syncBusy === c.id" class="spin"></span>
              {{ syncBusy === c.id ? 'Sync…' : 'Sync en ligne' }}
            </button>
            <button
              class="btn" :class="{ 'btn-primary': !c.imported }"
              :disabled="!isAdmin || busy || syncBusy" @click="importOne(c.id)"
            >
              <span v-if="busy === c.id" class="spin"></span>
              {{ busy === c.id ? 'Import…' : (c.imported ? 'Réimporter' : 'Importer') }}
            </button>
          </div>
        </div>
      </div>

      <div class="ref-note">
        Socle embarqué (fonctionne hors-ligne). OWASP Top 10 et CWE Top 25 sont complets ;
        le socle ATT&CK, D3FEND et CAPEC est un sous-ensemble courant. ATT&CK et D3FEND
        peuvent être synchronisés à leur catalogue MITRE complet via « Sync en ligne » (ou
        « Tout synchroniser »), avec repli automatique sur le socle si la source est injoignable.
      </div>
    </template>
  </div>
</template>

<style scoped>
.intro{color:var(--muted);font-size:13px;margin:6px 0 14px}
.msg{font-size:13px;margin:8px 0}
.msg.ok{color:var(--green)} .msg.ko{color:var(--red)} .msg.warn{color:var(--amber)}
.ro{color:var(--faint);font-size:12px;margin:8px 0}
.ref-sync{display:flex;align-items:center;gap:14px;justify-content:space-between;margin:10px 0}
.sync-txt{font-size:13px;color:var(--text)}
.ref-group{margin-top:18px}
.group-title{margin-bottom:8px}
.ref-card{display:flex;align-items:center;gap:14px;background:var(--surface);border:1px solid var(--border);
  border-radius:var(--r-card);padding:13px 15px;margin-bottom:10px}
.ref-badge{flex:0 0 auto;font-size:11px;font-weight:700;padding:3px 9px;border-radius:var(--r-pill);border:1px solid transparent}
.ref-main{flex:1 1 auto;min-width:0}
.ref-name{font-family:var(--font-display);font-weight:600;color:var(--heading);font-size:14px}
.ref-desc{color:var(--muted);font-size:12.5px;margin:2px 0 6px}
.ref-meta{display:flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:11.5px;color:var(--faint)}
.ref-meta .data{font-family:var(--font-data)}
.ref-dot{width:7px;height:7px;border-radius:50%;background:var(--faint)}
.ref-dot.on{background:var(--green)}
.sep{opacity:.5}
.spin{width:12px;height:12px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;
  display:inline-block;animation:spin .7s linear infinite;margin-right:6px;vertical-align:-1px}
@keyframes spin{to{transform:rotate(360deg)}}
.card-actions{display:flex;gap:6px;flex:0 0 auto}
.primary-ghost{border-color:var(--violet);color:var(--violet-accent)}
.ref-note{margin-top:16px;padding:11px 14px;background:var(--surface-2);border:1px solid var(--border-2);
  border-radius:var(--r-card);font-size:11.5px;color:var(--muted);line-height:1.5}
</style>
