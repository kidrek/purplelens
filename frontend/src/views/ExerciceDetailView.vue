<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, ApiError } from '../api/client'
import EntityForm from '../components/EntityForm.vue'
import DetailDrawer from '../components/DetailDrawer.vue'
import { fieldsFor } from '../fields'

// Détail d'un exercice Purple : la chaîne d'attaque (étapes ordonnées) confrontée à
// la défense (verdict par étape + observations défensives). C'est la vue qui donne
// le sens « Purple » : ce que la Red Team a fait vs ce que la Blue Team a vu/bloqué.
const route = useRoute()
const id = route.params.id

// Verdicts (spec §2) : prévenu / alerté / journalisé / sans télémétrie / non testé.
const VERDICTS = {
  prevented: { label: 'Prévenu', pill: 'green' },
  alerted: { label: 'Alerté', pill: 'cyan' },
  logged: { label: 'Journalisé', pill: 'amber' },
  no_telemetry: { label: 'Sans télémétrie', pill: 'red' },
  not_tested: { label: 'Non testé', pill: 'gray' },
}

const exercise = ref(null)
const steps = ref([])
const obsByStep = ref({}) // attack_step_id -> [observations]
const loading = ref(true)
const error = ref(null)
const form = ref(null)
const scenarios = ref([])
const showLoad = ref(false)
const chosenScenario = ref('')
const busy = ref(false)

async function loadAll() {
  loading.value = true; error.value = null
  const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))
  try {
    exercise.value = await api.get(`/exercices/${id}`)
    steps.value = unwrap(await api.list('attack_steps', `?exercise_id=${id}`))
      .sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0))
    const entries = await Promise.all(
      steps.value.map((s) =>
        api.list('observations', `?attack_step_id=${s.id}`).then((d) => [s.id, unwrap(d)])
      )
    )
    obsByStep.value = Object.fromEntries(entries)
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? 'Accès refusé' : (e.message || 'Erreur')
  } finally {
    loading.value = false
  }
}

// Synthèse de couverture : répartition des verdicts sur la chaîne.
const coverage = computed(() => {
  const c = {}
  for (const k of Object.keys(VERDICTS)) c[k] = 0
  for (const s of steps.value) c[s.verdict] = (c[s.verdict] || 0) + 1
  return c
})
const total = computed(() => steps.value.length)
// Taux de détection = étapes prévenues/alertées/journalisées sur total testé.
const detectionRate = computed(() => {
  const tested = steps.value.filter((s) => s.verdict !== 'not_tested')
  if (!tested.length) return null
  const seen = tested.filter((s) => ['prevented', 'alerted', 'logged'].includes(s.verdict))
  return Math.round((seen.length / tested.length) * 100)
})

function mttd(step) {
  if (!step.horodatage || !step.horodatage_detection) return null
  const d = (new Date(step.horodatage_detection) - new Date(step.horodatage)) / 1000
  if (isNaN(d) || d < 0) return null
  if (d < 60) return `${Math.round(d)} s`
  if (d < 3600) return `${Math.round(d / 60)} min`
  return `${(d / 3600).toFixed(1)} h`
}

const prefill = computed(() => ({ client_id: exercise.value?.client_id, exercise_id: id }))
function newStep() { form.value = { entity: 'attack_steps', record: { ordre: steps.value.length + 1 }, hidden: ['client_id', 'exercise_id'], title: "étape d'attaque" } }
function editStep(s) { form.value = { entity: 'attack_steps', record: s, hidden: ['client_id', 'exercise_id'], title: "étape d'attaque" } }
function newObs(stepId) { form.value = { entity: 'observations', record: { attack_step_id: stepId }, hidden: ['client_id', 'attack_step_id'], obsPrefill: { client_id: exercise.value?.client_id, attack_step_id: stepId }, title: 'observation défensive' } }
function editObs(o) { form.value = { entity: 'observations', record: o, hidden: ['client_id', 'attack_step_id'], obsPrefill: { client_id: exercise.value?.client_id, attack_step_id: o.attack_step_id }, title: 'observation défensive' } }

async function onSaved() { form.value = null; await loadAll() }
async function del(entity, row) {
  if (!window.confirm('Supprimer ? Action journalisée.')) return
  try { await api.remove(entity, row.id); await loadAll() }
  catch (e) { error.value = e instanceof ApiError && e.status === 403 ? 'Refusé' : e.message }
}
async function openLoad() {
  showLoad.value = true
  if (!scenarios.value.length) {
    try {
      const d = await api.list('scenarios')
      scenarios.value = Array.isArray(d) ? d : (d?.items ?? [])
    } catch { scenarios.value = [] }
  }
}
async function loadFromScenario() {
  if (!chosenScenario.value) return
  busy.value = true
  try {
    await api.post(`/exercices/${id}/load-scenario`, { scenario_id: chosenScenario.value })
    showLoad.value = false; chosenScenario.value = ''
    await loadAll()
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? 'Refusé (droit de création requis).' : (e.message || 'Erreur.')
  } finally { busy.value = false }
}
async function move(index, dir) {
  const arr = [...steps.value]
  const j = index + dir
  if (j < 0 || j >= arr.length) return
  ;[arr[index], arr[j]] = [arr[j], arr[index]]
  steps.value = arr // optimiste
  try {
    await api.post(`/exercices/${id}/reorder`, { step_ids: arr.map((s) => s.id) })
    await loadAll()
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? 'Refusé.' : (e.message || 'Erreur.')
    await loadAll()
  }
}
onMounted(loadAll)
</script>

<template>
  <div>
    <RouterLink to="/exercices" class="back">← Exercices Purple</RouterLink>
    <p v-if="loading" class="muted">Chargement…</p>
    <p v-else-if="error" class="err">{{ error }}</p>

    <template v-else-if="exercise">
      <div class="eyebrow">Exercice Purple</div>
      <h1>{{ exercise.nom }}</h1>
      <div class="meta panel">
        <div><span class="k">Équipe</span>{{ exercise.equipe || '—' }}</div>
        <div><span class="k">Date</span>{{ exercise.date || '—' }}</div>
        <div><span class="k">Run</span>{{ exercise.run_number ?? '—' }}</div>
        <div><span class="k">Statut</span><span class="pill pill-cyan">{{ exercise.statut }}</span></div>
        <div><span class="k">TLP</span><span v-if="exercise.tlp" :class="['tlp','tlp-'+exercise.tlp]">{{ exercise.tlp }}</span></div>
      </div>

      <!-- Synthèse de couverture défensive -->
      <div class="panel coverage">
        <div class="cov-head">
          <span class="eyebrow">Couverture défensive</span>
          <span v-if="detectionRate !== null" class="rate">{{ detectionRate }}% détecté
            <small>({{ total }} étape{{ total > 1 ? 's' : '' }})</small></span>
        </div>
        <div class="bar">
          <div v-for="(v, k) in VERDICTS" :key="k" v-show="coverage[k]"
               :class="['seg','seg-'+v.pill]" :style="{ flex: coverage[k] }" :title="v.label + ': ' + coverage[k]"></div>
        </div>
        <div class="legend">
          <span v-for="(v, k) in VERDICTS" :key="k" class="lg">
            <span :class="['dot','dot-'+v.pill]"></span>{{ v.label }} <b>{{ coverage[k] }}</b>
          </span>
        </div>
      </div>

      <!-- Chaîne d'attaque -->
      <div class="section-head">
        <h2>Chaîne d'attaque</h2>
        <div class="head-actions">
          <button class="btn" @click="openLoad">Charger depuis un scénario</button>
          <button class="btn btn-primary" @click="newStep">+ Étape</button>
        </div>
      </div>
      <p v-if="!steps.length" class="muted">Aucune étape. Ajoutez la première technique de la chaîne.</p>

      <div v-for="(s, i) in steps" :key="s.id" class="step card">
        <div class="step-top">
          <span class="ordre">{{ s.ordre }}</span>
          <div class="step-id">
            <span class="tech">{{ s.technique || '—' }}</span>
            <span class="titre">{{ s.titre }}</span>
          </div>
          <span :class="['pill','pill-'+(VERDICTS[s.verdict]?.pill||'gray')]">{{ VERDICTS[s.verdict]?.label || s.verdict }}</span>
          <span v-if="mttd(s)" class="mttd" title="Délai de détection">⏱ {{ mttd(s) }}</span>
          <div class="step-actions">
            <button class="btn slim" :disabled="i === 0" @click="move(i, -1)" title="Monter">↑</button>
            <button class="btn slim" :disabled="i === steps.length - 1" @click="move(i, 1)" title="Descendre">↓</button>
            <button class="btn slim" @click="editStep(s)">Éditer</button>
            <button class="btn slim danger" @click="del('attack_steps', s)">Suppr.</button>
          </div>
        </div>

        <!-- Observations défensives de l'étape -->
        <div class="obs">
          <div class="obs-head">
            <span class="obs-title">Observations défensives</span>
            <button class="btn slim" @click="newObs(s.id)">+ Observation</button>
          </div>
          <div v-if="(obsByStep[s.id] || []).length" class="obs-list">
            <div v-for="o in obsByStep[s.id]" :key="o.id" class="obs-item">
              <div class="obs-main">
                <span class="src">{{ o.source || 'source ?' }}</span>
                <span v-if="o.resultat" :class="['pill','pill-'+(VERDICTS[o.resultat]?.pill||'gray')]">{{ VERDICTS[o.resultat]?.label || o.resultat }}</span>
                <span class="desc">{{ o.description }}</span>
              </div>
              <div class="obs-act">
                <button class="btn slim" @click="editObs(o)">Éditer</button>
                <button class="btn slim danger" @click="del('observations', o)">Suppr.</button>
              </div>
            </div>
          </div>
          <div v-else class="obs-empty">Aucune observation — la Blue Team n'a rien remonté sur cette étape.</div>
        </div>
      </div>
    </template>

    <EntityForm
      v-if="form"
      :entity="form.entity"
      :fields="fieldsFor(form.entity)"
      :record="form.record"
      :prefill="form.obsPrefill || prefill"
      :hidden="form.hidden"
      :title="(form.record && form.record.id ? 'Modifier ' : 'Nouvelle ') + form.title"
      @saved="onSaved"
      @close="form = null"
    />
    <!-- Charger depuis un scénario -->
    <DetailDrawer v-if="showLoad" title="Charger la chaîne depuis un scénario"
                  subtitle="Exercice" @close="showLoad = false">
      <p class="hint">Chaque technique du scénario devient une étape (verdict « non testé »), ajoutée à la suite.</p>
      <select class="field" v-model="chosenScenario">
        <option value="">— choisir un scénario —</option>
        <option v-for="sc in scenarios" :key="sc.id" :value="sc.id">
          {{ sc.nom }} ({{ (sc.techniques || []).length }} techniques)
        </option>
      </select>
      <template #footer>
        <button class="btn" @click="showLoad = false">Annuler</button>
        <button class="btn btn-primary" :disabled="!chosenScenario || busy" @click="loadFromScenario">
          {{ busy ? 'Chargement…' : 'Charger' }}
        </button>
      </template>
    </DetailDrawer>
  </div>
</template>

<style scoped>
.back{color:var(--muted);font-size:13px;text-decoration:none}
.back:hover{color:var(--violet)}
.meta{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:10px 0}
.meta .k{display:block;font-size:10px;text-transform:uppercase;color:var(--faint);margin-bottom:3px}
.coverage{margin:12px 0}
.cov-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}
.rate{font-family:var(--font-display);font-size:18px;color:var(--heading)}
.rate small{color:var(--muted);font-size:11px}
.bar{display:flex;height:12px;border-radius:99px;overflow:hidden;background:var(--surface-3);border:1px solid var(--border-2)}
.seg{min-width:3px}
.seg-green{background:var(--green)} .seg-cyan{background:var(--cyan)} .seg-amber{background:var(--amber)}
.seg-red{background:var(--red)} .seg-gray{background:var(--faint)}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin-top:8px;font-size:11px;color:var(--muted)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle}
.dot-green{background:var(--green)} .dot-cyan{background:var(--cyan)} .dot-amber{background:var(--amber)}
.dot-red{background:var(--red)} .dot-gray{background:var(--faint)}
.section-head{display:flex;justify-content:space-between;align-items:center;margin:22px 0 8px;border-top:1px solid var(--border);padding-top:16px}
.step{margin-bottom:12px}
.step-top{display:flex;align-items:center;gap:12px}
.head-actions{display:flex;gap:8px}
.hint{font-size:12px;color:var(--faint);margin-bottom:12px}
.ordre{width:26px;height:26px;flex-shrink:0;display:grid;place-items:center;border-radius:50%;background:var(--violet-soft);color:var(--violet-accent);font-family:var(--font-data);font-size:12px;font-weight:700}
.step-id{flex:1;display:flex;flex-direction:column}
.tech{font-family:var(--font-data);font-size:11px;color:var(--cyan)}
.titre{font-weight:600;color:var(--heading)}
.mttd{font-family:var(--font-data);font-size:11px;color:var(--amber)}
.step-actions{display:flex;gap:6px}
.obs{margin-top:10px;padding-top:10px;border-top:1px dashed var(--border-2)}
.obs-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.obs-title{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--faint)}
.obs-item{display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px solid var(--border-2)}
.obs-main{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.src{font-family:var(--font-data);font-size:12px;color:var(--muted)}
.desc{font-size:13px}
.obs-act{display:flex;gap:6px;white-space:nowrap}
.obs-empty{font-size:12px;color:var(--faint)}
.slim{padding:4px 9px;font-size:12px}
.danger{color:var(--red);border-color:var(--c-red-bd)}
</style>
