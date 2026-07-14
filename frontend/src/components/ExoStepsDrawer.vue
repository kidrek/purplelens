<script setup>
import { onMounted, ref } from 'vue'
import { api, ApiError } from '../api/client'
import DetailDrawer from './DetailDrawer.vue'
import EntityForm from './EntityForm.vue'
import { fieldsFor } from '../fields'

// Éditeur des étapes d'un exercice Purple, en drawer (miroir de l'exoStepEd de la maquette) :
// chaîne d'attaque (édition/réordonnancement/suppression par étape), observations défensives,
// et chargement depuis un scénario. L'édition fine passe par EntityForm (drawers empilés).
const props = defineProps({ exercise: { type: Object, required: true } })
const emit = defineEmits(['close', 'changed'])

// Verdicts (spec §2) : prévenu / alerté / journalisé / sans télémétrie / non testé.
const VERDICTS = {
  prevented: { label: 'Prévenu', pill: 'green' },
  alerted: { label: 'Alerté', pill: 'cyan' },
  logged: { label: 'Journalisé', pill: 'amber' },
  no_telemetry: { label: 'Sans télémétrie', pill: 'red' },
  not_tested: { label: 'Non testé', pill: 'gray' },
}

const id = props.exercise.id
const steps = ref([])
const obsByStep = ref({})
const loading = ref(true)
const error = ref(null)
const form = ref(null)
const scenarios = ref([])
const showLoad = ref(false)
const chosenScenario = ref('')
const busy = ref(false)

const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))

async function loadAll() {
  loading.value = true; error.value = null
  try {
    steps.value = unwrap(await api.list('attack_steps', `?exercise_id=${id}`))
      .sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0))
    const entries = await Promise.all(
      steps.value.map((s) => api.list('observations', `?attack_step_id=${s.id}`).then((d) => [s.id, unwrap(d)]))
    )
    obsByStep.value = Object.fromEntries(entries)
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? 'Accès refusé' : (e.message || 'Erreur')
  } finally {
    loading.value = false
  }
}

const prefill = { client_id: props.exercise.client_id, exercise_id: id }
function newStep() { form.value = { entity: 'attack_steps', record: {}, hidden: ['client_id', 'exercise_id'], p: { ...prefill, ordre: steps.value.length + 1 }, title: "étape d'attaque" } }
function editStep(s) { form.value = { entity: 'attack_steps', record: s, hidden: ['client_id', 'exercise_id'], p: prefill, title: "étape d'attaque" } }
function newObs(stepId) { form.value = { entity: 'observations', record: { attack_step_id: stepId }, hidden: ['client_id', 'attack_step_id'], p: { client_id: props.exercise.client_id, attack_step_id: stepId }, title: 'observation défensive' } }
function editObs(o) { form.value = { entity: 'observations', record: o, hidden: ['client_id', 'attack_step_id'], p: { client_id: props.exercise.client_id, attack_step_id: o.attack_step_id }, title: 'observation défensive' } }

async function onSaved() { form.value = null; await loadAll(); emit('changed') }

async function del(entity, row) {
  if (!window.confirm('Supprimer ? Action journalisée.')) return
  try { await api.remove(entity, row.id); await loadAll(); emit('changed') }
  catch (e) { error.value = e instanceof ApiError && e.status === 403 ? 'Refusé' : e.message }
}

async function move(index, dir) {
  const arr = [...steps.value]
  const j = index + dir
  if (j < 0 || j >= arr.length) return
  ;[arr[index], arr[j]] = [arr[j], arr[index]]
  steps.value = arr // optimiste
  try {
    await api.post(`/exercices/${id}/reorder`, { step_ids: arr.map((s) => s.id) })
    await loadAll(); emit('changed')
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? 'Refusé.' : (e.message || 'Erreur.')
    await loadAll()
  }
}

async function openLoad() {
  showLoad.value = true
  if (!scenarios.value.length) {
    try { scenarios.value = unwrap(await api.list('scenarios')) } catch { scenarios.value = [] }
  }
}
async function loadFromScenario() {
  if (!chosenScenario.value) return
  busy.value = true
  try {
    await api.post(`/exercices/${id}/load-scenario`, { scenario_id: chosenScenario.value })
    showLoad.value = false; chosenScenario.value = ''
    await loadAll(); emit('changed')
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? 'Refusé (droit de création requis).' : (e.message || 'Erreur.')
  } finally { busy.value = false }
}

onMounted(loadAll)
</script>

<template>
  <DetailDrawer wide subtitle="Étapes de l'exercice" :title="exercise.nom || 'Exercice'" @close="emit('close')">
    <template #actions>
      <button class="btn" @click="openLoad">Charger depuis un scénario</button>
      <button class="btn btn-primary" @click="newStep">+ Étape</button>
    </template>

    <p v-if="loading" class="muted">Chargement…</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <p v-else-if="!steps.length" class="muted">Aucune étape. Ajoutez la première technique de la chaîne.</p>

    <div v-for="(s, i) in steps" :key="s.id" class="step card">
      <div class="step-top">
        <span class="ordre">{{ s.ordre }}</span>
        <div class="step-id">
          <span class="tech">{{ s.technique || '—' }}</span>
          <span class="titre">{{ s.titre }}</span>
        </div>
        <span :class="['pill', 'pill-' + (VERDICTS[s.verdict]?.pill || 'gray')]">{{ VERDICTS[s.verdict]?.label || s.verdict }}</span>
        <div class="step-actions">
          <button class="btn slim" :disabled="i === 0" @click="move(i, -1)" title="Monter">↑</button>
          <button class="btn slim" :disabled="i === steps.length - 1" @click="move(i, 1)" title="Descendre">↓</button>
          <button class="btn slim" @click="editStep(s)">Éditer</button>
          <button class="btn slim danger" @click="del('attack_steps', s)">Suppr.</button>
        </div>
      </div>

      <div class="obs">
        <div class="obs-head">
          <span class="obs-title">Observations défensives</span>
          <button class="btn slim" @click="newObs(s.id)">+ Observation</button>
        </div>
        <div v-if="(obsByStep[s.id] || []).length" class="obs-list">
          <div v-for="o in obsByStep[s.id]" :key="o.id" class="obs-item">
            <div class="obs-main">
              <span class="src">{{ o.source || 'source ?' }}</span>
              <span v-if="o.resultat" :class="['pill', 'pill-' + (VERDICTS[o.resultat]?.pill || 'gray')]">{{ VERDICTS[o.resultat]?.label || o.resultat }}</span>
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

    <!-- Édition fine d'une étape / observation (drawer empilé) -->
    <EntityForm
      v-if="form"
      :entity="form.entity"
      :fields="fieldsFor(form.entity)"
      :record="form.record && form.record.id ? form.record : null"
      :prefill="form.p"
      :hidden="form.hidden"
      :title="(form.record && form.record.id ? 'Modifier ' : 'Nouvelle ') + form.title"
      @saved="onSaved"
      @close="form = null"
    />

    <!-- Charger depuis un scénario (drawer empilé) -->
    <DetailDrawer v-if="showLoad" title="Charger la chaîne depuis un scénario" subtitle="Exercice" @close="showLoad = false">
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
  </DetailDrawer>
</template>

<style scoped>
.muted{color:var(--muted)}
.err{color:var(--red);font-size:13px}
.hint{font-size:12px;color:var(--faint);margin-bottom:12px}
.step{margin-bottom:12px}
.step-top{display:flex;align-items:center;gap:12px}
.ordre{width:26px;height:26px;flex-shrink:0;display:grid;place-items:center;border-radius:50%;background:var(--violet-soft);color:var(--violet-accent);font-family:var(--font-data);font-size:12px;font-weight:700}
.step-id{flex:1;display:flex;flex-direction:column;min-width:0}
.tech{font-family:var(--font-data);font-size:11px;color:var(--cyan)}
.titre{font-weight:600;color:var(--heading)}
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
.field{width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--r-mini);font-size:13px;background:var(--surface);color:var(--text)}
</style>
