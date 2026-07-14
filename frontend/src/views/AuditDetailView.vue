<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, ApiError } from '../api/client'
import EntityForm from '../components/EntityForm.vue'
import { fieldsFor } from '../fields'

// Vue de détail d'un audit : en-tête + actions PTES (groupées par phase) + jalons.
// Actions et jalons sont scopés à l'audit (client_id/audit_id imposés via prefill).
// Le serveur reste l'autorité : chaque écriture repasse par can() + RLS.
const route = useRoute()
const id = route.params.id

const PTES_ORDER = [
  'pre-engagement', 'reconnaissance', 'threat-modeling', 'vulnerability-analysis',
  'exploitation', 'post-exploitation', 'reporting',
]

const audit = ref(null)
const actions = ref([])
const milestones = ref([])
const exercices = ref([])
const deliverables = ref([])
const loading = ref(true)
const error = ref(null)

// Générateur de livrables ancré sur l'audit (cahier §5 ; flux §6.5 : la lettre ouvre
// la mission, le rapport la clôt). Client/audit/TLP pré-remplis depuis l'audit courant.
const DELIVERABLE_TYPES = [
  { v: 'engagement', label: "Lettre d'engagement" },
  { v: 'nda', label: 'NDA' },
  { v: 'rapport', label: 'Rapport PTES' },
]
const genBusy = ref(null) // type en cours de génération
const genMsg = ref(null)

async function generateDeliverable(type) {
  genMsg.value = null
  genBusy.value = type
  try {
    await api.post('/deliverables/generate', {
      client_id: audit.value.client_id,
      audit_id: id,
      type,
      langue: 'fr',
      tlp: audit.value.tlp || 'AMBER',
    })
    genMsg.value = { kind: 'ok', text: `Livrable généré (${typeLabel(type)}).` }
    await loadDeliverables()
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) genMsg.value = { kind: 'ko', text: 'Génération refusée (droits ou cloisonnement).' }
    else genMsg.value = { kind: 'ko', text: e.message || 'Erreur de génération.' }
  } finally {
    genBusy.value = null
  }
}

async function downloadDeliverable(d) {
  genMsg.value = null
  try {
    const res = await api.get(`/deliverables/${d.id}/download`)
    // URL présignée courte → ouverture directe (le binaire ne transite pas par l'API).
    window.open(res.url, '_blank', 'noopener')
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) genMsg.value = { kind: 'ko', text: 'Livrable pas encore prêt.' }
    else if (e instanceof ApiError && e.status === 403) genMsg.value = { kind: 'ko', text: 'Téléchargement refusé.' }
    else genMsg.value = { kind: 'ko', text: e.message || 'Erreur.' }
  }
}

async function loadDeliverables() {
  const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))
  try { deliverables.value = await api.list('deliverables', `?audit_id=${id}`).then(unwrap) }
  catch { deliverables.value = [] }
}

const typeLabel = (v) => DELIVERABLE_TYPES.find((t) => t.v === v)?.label || v
const fmtDate = (iso) => (iso ? String(iso).slice(0, 10) : '—')

// Formulaire modal partagé (actions / jalons)
const form = ref(null) // { entity, record, title }

async function loadAll() {
  loading.value = true; error.value = null
  try {
    audit.value = await api.get(`/audits/${id}`)
    const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))
    ;[actions.value, milestones.value, exercices.value, deliverables.value] = await Promise.all([
      api.list('audit_actions', `?audit_id=${id}`).then(unwrap),
      api.list('audit_milestones', `?audit_id=${id}`).then(unwrap),
      api.list('exercices', `?audit_id=${id}`).then(unwrap),
      api.list('deliverables', `?audit_id=${id}`).then(unwrap).catch(() => []),
    ])
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? 'Accès refusé' : (e.message || 'Erreur')
  } finally {
    loading.value = false
  }
}

const actionsByPhase = computed(() => {
  const map = {}
  for (const p of PTES_ORDER) map[p] = []
  for (const a of actions.value) (map[a.ptes_phase] || (map[a.ptes_phase] = [])).push(a)
  return map
})

const prefill = computed(() => ({ client_id: audit.value?.client_id, audit_id: id }))

function newAction(phase) {
  form.value = { entity: 'audit_actions', record: phase ? { ptes_phase: phase } : null, title: 'action PTES' }
}
function editAction(a) { form.value = { entity: 'audit_actions', record: a, title: 'action PTES' } }
function newMilestone() { form.value = { entity: 'audit_milestones', record: null, title: 'jalon' } }
function editMilestone(m) { form.value = { entity: 'audit_milestones', record: m, title: 'jalon' } }

async function onSaved() { form.value = null; await loadAll() }

async function del(entity, row) {
  if (!window.confirm('Supprimer cet élément ? Action journalisée.')) return
  try { await api.remove(entity, row.id); await loadAll() }
  catch (e) { error.value = e instanceof ApiError && e.status === 403 ? 'Refusé' : e.message }
}

const statutPill = (s) => ({ termine: 'green', atteint: 'green', en_cours: 'cyan', traite: 'green',
  a_venir: 'gray', ouvert: 'amber', manque: 'red', clos: 'green', genere: 'green', valide: 'green', diffuse: 'cyan' }[s] || 'gray')

onMounted(loadAll)
</script>

<template>
  <div>
    <RouterLink to="/audits" class="back">← Audits</RouterLink>

    <p v-if="loading" class="muted">Chargement…</p>
    <p v-else-if="error" class="err">{{ error }}</p>

    <template v-else-if="audit">
      <!-- En-tête -->
      <div class="eyebrow">Engagement</div>
      <h1>{{ audit.nom }}</h1>
      <div class="meta panel">
        <div><span class="k">Catégorie</span>{{ audit.categorie || '—' }}</div>
        <div><span class="k">Type</span>{{ audit.type_test || '—' }}</div>
        <div><span class="k">Statut</span><span :class="['pill','pill-'+statutPill(audit.statut)]">{{ audit.statut }}</span></div>
        <div><span class="k">Priorité</span>{{ audit.priorite || '—' }}</div>
        <div><span class="k">Début</span>{{ audit.date_debut || '—' }}</div>
        <div><span class="k">Fin</span>{{ audit.date_fin || '—' }}</div>
        <div><span class="k">TLP</span><span v-if="audit.tlp" :class="['tlp','tlp-'+audit.tlp]">{{ audit.tlp }}</span></div>
        <div><span class="k">Budget</span>{{ audit.budget ?? '—' }}</div>
      </div>
      <p v-if="audit.notes" class="notes">{{ audit.notes }}</p>

      <!-- Actions PTES groupées par phase -->
      <div class="section-head">
        <h2>Actions PTES</h2>
        <button class="btn btn-primary" @click="newAction(null)">+ Action</button>
      </div>
      <div v-for="phase in PTES_ORDER" :key="phase" class="phase">
        <div class="phase-head">
          <span class="phase-name">{{ phase }}</span>
          <span class="count">{{ actionsByPhase[phase].length }}</span>
          <button class="btn slim" @click="newAction(phase)">+</button>
        </div>
        <table v-if="actionsByPhase[phase].length">
          <tbody>
            <tr v-for="a in actionsByPhase[phase]" :key="a.id">
              <td class="titre">{{ a.titre }}</td>
              <td>{{ a.technique_attack || '' }}</td>
              <td><span :class="['pill','pill-'+statutPill(a.statut)]">{{ a.statut }}</span></td>
              <td class="ta"><button class="btn slim" @click="editAction(a)">Éditer</button>
                <button class="btn slim danger" @click="del('audit_actions', a)">Suppr.</button></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-phase">—</div>
      </div>

      <!-- Jalons -->
      <div class="section-head">
        <h2>Jalons</h2>
        <button class="btn btn-primary" @click="newMilestone">+ Jalon</button>
      </div>
      <table v-if="milestones.length">
        <thead><tr><th>Phase</th><th>Livrable</th><th>Prévu</th><th>Réel</th><th>Statut</th><th></th></tr></thead>
        <tbody>
          <tr v-for="m in milestones" :key="m.id">
            <td>{{ m.ptes_phase }}</td>
            <td>{{ m.livrable || '—' }}</td>
            <td>{{ m.date_prevue || '—' }}</td>
            <td>{{ m.date_reelle || '—' }}</td>
            <td><span :class="['pill','pill-'+statutPill(m.statut)]">{{ m.statut }}</span></td>
            <td class="ta"><button class="btn slim" @click="editMilestone(m)">Éditer</button>
              <button class="btn slim danger" @click="del('audit_milestones', m)">Suppr.</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">Aucun jalon.</p>

      <!-- Exercices rattachés -->
      <div class="section-head"><h2>Exercices Purple rattachés</h2></div>
      <table v-if="exercices.length">
        <tbody>
          <tr v-for="ex in exercices" :key="ex.id">
            <td>{{ ex.nom }}</td><td>{{ ex.equipe || '' }}</td>
            <td><span :class="['pill','pill-'+statutPill(ex.statut)]">{{ ex.statut }}</span></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">Aucun exercice rattaché.</p>

      <!-- Livrables de l'audit -->
      <div class="section-head">
        <h2>Livrables</h2>
        <div class="gen-btns">
          <button v-for="ty in DELIVERABLE_TYPES" :key="ty.v" class="btn"
                  :disabled="genBusy !== null" @click="generateDeliverable(ty.v)">
            {{ genBusy === ty.v ? 'Génération…' : '+ ' + ty.label }}
          </button>
        </div>
      </div>
      <p v-if="genMsg" :class="['msg', genMsg.kind]">{{ genMsg.text }}</p>
      <table v-if="deliverables.length">
        <thead><tr><th>Type</th><th>Titre</th><th>Généré le</th><th>TLP</th><th>Statut</th><th></th></tr></thead>
        <tbody>
          <tr v-for="d in deliverables" :key="d.id">
            <td>{{ typeLabel(d.type) }}</td>
            <td>{{ d.titre || '—' }}</td>
            <td>{{ fmtDate(d.created_at) }}</td>
            <td><span :class="['pill', 'tlp-' + String(d.tlp || '').toLowerCase()]">TLP:{{ d.tlp }}</span></td>
            <td><span :class="['pill','pill-'+statutPill(d.statut)]">{{ d.statut }}</span></td>
            <td class="ta"><button class="btn slim" @click="downloadDeliverable(d)">Télécharger</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">Aucun livrable généré pour cet audit.</p>
    </template>

    <EntityForm
      v-if="form"
      :entity="form.entity"
      :fields="fieldsFor(form.entity)"
      :record="form.record"
      :prefill="prefill"
      :hidden="['client_id', 'audit_id']"
      :title="(form.record && form.record.id ? 'Modifier ' : 'Nouveau ') + form.title"
      @saved="onSaved"
      @close="form = null"
    />
  </div>
</template>

<style scoped>
.gen-btns{display:flex;gap:8px;flex-wrap:wrap}
.msg{padding:8px 12px;border-radius:var(--r-mini);font-size:13px}
.msg.ok{background:var(--c-green-bg);color:var(--c-green-tx)}
.msg.ko{background:var(--c-red-bg);color:var(--c-red-tx)}
.back{color:var(--muted);font-size:13px;text-decoration:none}
.back:hover{color:var(--violet)}
.meta{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:10px 0}
.meta .k{display:block;font-size:10px;text-transform:uppercase;color:var(--faint);margin-bottom:3px}
.notes{color:var(--muted);font-size:13px;margin:4px 0 8px}
.section-head{display:flex;justify-content:space-between;align-items:center;margin:22px 0 8px;border-top:1px solid var(--border);padding-top:16px}
.phase{margin-bottom:10px}
.phase-head{display:flex;align-items:center;gap:10px;margin:8px 0 4px}
.phase-name{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:11px;color:var(--violet-accent)}
.count{font-size:11px;color:var(--faint);background:var(--surface-3);border-radius:99px;padding:0 7px}
.titre{font-weight:600;color:var(--heading)}
.empty-phase{color:var(--faint);font-size:12px;padding:2px 0 6px}
.ta{white-space:nowrap;text-align:right;display:flex;gap:6px;justify-content:flex-end}
.slim{padding:4px 9px;font-size:12px}
.danger{color:var(--red);border-color:var(--c-red-bd)}
</style>
