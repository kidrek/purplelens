<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, ApiError } from '../api/client'
import DeliverableDrawer from '../components/DeliverableDrawer.vue'
const { t } = useI18n()

// Générateur de livrables (cahier §5). Le rendu (lettre d'engagement, NDA, rapport
// PTES) est fait par le SERVEUR, qui masque les preuves secrètes (porte 5) et pose
// un Object Lock. Le PDF n'est jamais servi par l'API : on récupère une URL présignée
// courte. Le client ne décide rien — tout repasse par can() + RLS côté serveur.
const TYPES = [
  { v: 'engagement', label: "Lettre d'engagement" },
  { v: 'nda', label: 'Accord de confidentialité (NDA)' },
  { v: 'rapport', label: 'Rapport PTES' },
]
const TLP = ['RED', 'AMBER', 'GREEN', 'CLEAR']

const clients = ref([])
const audits = ref([])
const deliverables = ref([])
const form = ref({ type: 'rapport', client_id: '', audit_id: '', langue: 'fr', tlp: 'AMBER' })
const busy = ref(false)
const msg = ref(null)
const loading = ref(true)
const viewFor = ref(null)

const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))
// Le rapport PTES tire ses constats d'un audit → audit requis pour ce type.
const auditRequired = computed(() => form.value.type === 'rapport')
const auditsForClient = computed(() =>
  form.value.client_id ? audits.value.filter((a) => a.client_id === form.value.client_id) : audits.value
)

async function loadRefs() {
  loading.value = true
  try {
    ;[clients.value, audits.value, deliverables.value] = await Promise.all([
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
  if (!form.value.client_id) { msg.value = { kind: 'ko', text: 'Choisissez un client.' }; return }
  if (auditRequired.value && !form.value.audit_id) { msg.value = { kind: 'ko', text: 'Le rapport PTES exige un audit.' }; return }
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
    msg.value = { kind: 'ok', text: `Livrable généré (${res.type}).` }
    await loadRefs()
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) msg.value = { kind: 'ko', text: 'Génération refusée (droits ou cloisonnement).' }
    else if (e instanceof ApiError && e.status === 404) msg.value = { kind: 'ko', text: 'Client introuvable dans votre périmètre.' }
    else msg.value = { kind: 'ko', text: e.message || 'Erreur de génération.' }
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
    if (e instanceof ApiError && e.status === 409) msg.value = { kind: 'ko', text: 'Livrable pas encore prêt.' }
    else if (e instanceof ApiError && e.status === 403) msg.value = { kind: 'ko', text: 'Téléchargement refusé.' }
    else msg.value = { kind: 'ko', text: e.message || 'Erreur.' }
  }
}

const typeLabel = (v) => TYPES.find((t) => t.v === v)?.label || v
const clientName = (id) => { const c = clients.value.find((x) => x.id === id); return c ? c.nom : '—' }

onMounted(loadRefs)
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.deliverables.eyebrow') }}</div>
    <h1>{{ t('views.deliverables.title') }}</h1>

    <p v-if="msg" :class="['msg', msg.kind]">{{ msg.text }}</p>

    <!-- Formulaire de génération -->
    <div class="panel gen">
      <div class="grid">
        <div class="fr">
          <label class="lbl">Type de livrable</label>
          <select class="field" v-model="form.type">
            <option v-for="t in TYPES" :key="t.v" :value="t.v">{{ t.label }}</option>
          </select>
        </div>
        <div class="fr">
          <label class="lbl">Client</label>
          <select class="field" v-model="form.client_id">
            <option value="">— choisir —</option>
            <option v-for="c in clients" :key="c.id" :value="c.id">{{ c.code }} · {{ c.nom }}</option>
          </select>
        </div>
        <div class="fr">
          <label class="lbl">Audit <span v-if="auditRequired" class="req">*</span><span v-else class="opt">(optionnel)</span></label>
          <select class="field" v-model="form.audit_id" :disabled="!form.client_id">
            <option value="">— aucun —</option>
            <option v-for="a in auditsForClient" :key="a.id" :value="a.id">{{ a.nom }}</option>
          </select>
        </div>
        <div class="fr">
          <label class="lbl">Langue</label>
          <select class="field" v-model="form.langue"><option value="fr">Français</option><option value="en">English</option></select>
        </div>
        <div class="fr">
          <label class="lbl">Marquage TLP</label>
          <select class="field" v-model="form.tlp"><option v-for="t in TLP" :key="t" :value="t">{{ t }}</option></select>
        </div>
      </div>
      <p class="hint">
        Le rapport PTES intègre automatiquement les constats de l'audit et masque les
        preuves marquées « secret ». Le fichier est scellé (Object Lock) et sa
        consultation est tracée au journal.
      </p>
      <button class="btn btn-primary" :disabled="busy" @click="generate">
        {{ busy ? 'Génération…' : 'Générer le livrable' }}
      </button>
    </div>

    <!-- Livrables produits -->
    <div class="section-head"><h2>Livrables produits</h2>
      <button class="btn" @click="loadRefs">Rafraîchir</button></div>
    <p v-if="loading" class="muted">Chargement…</p>
    <p v-else-if="!deliverables.length" class="muted">Aucun livrable généré.</p>
    <table v-else>
      <thead><tr><th>Titre</th><th>Type</th><th>Client</th><th>Langue</th><th>TLP</th><th>Statut</th><th></th></tr></thead>
      <tbody>
        <tr v-for="d in deliverables" :key="d.id">
          <td class="titre link" @click="viewFor = d">{{ d.titre }}</td>
          <td>{{ typeLabel(d.type) }}</td>
          <td>{{ clientName(d.client_id) }}</td>
          <td>{{ d.langue }}</td>
          <td><span v-if="d.tlp" :class="['tlp','tlp-'+d.tlp]">{{ d.tlp }}</span></td>
          <td><span class="pill pill-green">{{ d.statut }}</span></td>
          <td class="ta"><button class="btn slim" @click="viewFor = d">Voir</button>
            <button class="btn slim" @click="download(d)">Télécharger</button></td>
        </tr>
      </tbody>
    </table>

    <DeliverableDrawer v-if="viewFor" :deliverable="viewFor"
      :client-name="clientName(viewFor.client_id)" :type-label="typeLabel(viewFor.type)"
      @close="viewFor = null" @open="(d) => { download(d) }" />
  </div>
</template>

<style scoped>
.msg{font-size:13px;margin:8px 0}
.msg.ok{color:var(--green)} .msg.ko{color:var(--red)}
.gen{margin:10px 0}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.lbl{display:block;font-size:12px;color:var(--muted);margin-bottom:5px}
.req{color:var(--red)} .opt{color:var(--faint);font-size:11px}
.hint{font-size:11px;color:var(--faint);margin:12px 0}
.section-head{display:flex;justify-content:space-between;align-items:center;margin:22px 0 8px;border-top:1px solid var(--border);padding-top:16px}
.titre{font-weight:600;color:var(--heading)}
.titre.link{cursor:pointer}
.titre.link:hover{color:var(--violet-accent);text-decoration:underline}
.ta{text-align:right}
.slim{padding:4px 9px;font-size:12px}
@media (max-width:640px){ .grid{grid-template-columns:1fr} }
</style>
