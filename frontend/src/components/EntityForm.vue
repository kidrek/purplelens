<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api, ApiError } from '../api/client'
import RefPicker from './RefPicker.vue'
import DetailDrawer from './DetailDrawer.vue'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'
import TlpSelect from './TlpSelect.vue'
import RefacSelect from './RefacSelect.vue'
import StepsEditor from './StepsEditor.vue'
import ActorTtpPicker from './ActorTtpPicker.vue'
import EvidenceUpload from './EvidenceUpload.vue'

// Formulaire modal générique. Piloté par un schéma de champs (fields.js).
// Aucune décision d'autorisation ici : on soumet, et on affiche ce que le serveur
// répond (403 refus, 422 validation). Les listes de choix (client, ref) sont
// chargées depuis l'API — donc déjà filtrées par la RLS pour le rôle courant.
const props = defineProps({
  entity: { type: String, required: true },
  fields: { type: Array, required: true },
  record: { type: Object, default: null }, // présent => édition
  title: { type: String, default: '' },
  // Valeurs imposées par le contexte (ex. audit_id/client_id dans une vue de détail).
  prefill: { type: Object, default: () => ({}) },
  // Clés à ne pas afficher (typiquement celles fournies par prefill).
  hidden: { type: Array, default: () => [] },
  // Active une étape « joindre une preuve » APRÈS création (le finding_id = l'id de
  // l'enregistrement créé n'existe qu'à ce moment). Réservé aux entités « constat »
  // (vulnérabilités) portant un audit_id/client_id.
  evidenceUpload: { type: Boolean, default: false },
})
const emit = defineEmits(['saved', 'close'])
const { t } = useI18n()
const { fieldLabel, enumLabel } = useLabels()

const isEdit = !!props.record
const model = reactive({})
const options = reactive({}) // key -> [{ id, label }] pour client/ref
const busy = ref(false)
const error = ref(null)
const inlineBusy = ref(null) // clé du champ dont l'action en ligne est en cours

// Étape « preuve » optionnelle après création (evidenceUpload).
const phase = ref('form')          // 'form' | 'evidence'
const createdRecord = ref(null)    // enregistrement créé (porte l'id = finding_id)
const evidenceMsg = ref(null)
const evidenceCount = ref(0)

// Champs affichés = schéma moins les champs masqués (mais toujours soumis).
const visibleFields = props.fields.filter((f) => !props.hidden.includes(f.key))

function initialValue(f) {
  const v = props.record ? props.record[f.key] : undefined
  if (f.type === 'ref' && f.multiple) return Array.isArray(v) ? [...v] : []
  if (f.type === 'steps') return Array.isArray(v) ? [...v] : []
  if (f.type === 'tags') return Array.isArray(v) ? v.join(', ') : (v || '')
  if (f.type === 'lines') return Array.isArray(v) ? v.join('\n') : (v || '')
  if (f.type === 'bool') return v === true
  if (v === null || v === undefined) {
    // Valeur par défaut à la création uniquement (jamais imposée en édition).
    if (!isEdit && f.default !== undefined) return f.default
    return ''
  }
  return v
}

async function loadOptions() {
  for (const f of props.fields) {
    if (f.type === 'client') {
      try {
        const rows = await api.list('organisations')
        const list = Array.isArray(rows) ? rows : (rows.items ?? [])
        options[f.key] = list
          .filter((o) => f.role === null ? true : (o.role === (f.role || 'client')))
          .map((o) => ({ id: o.id, label: `${o.code || ''} ${o.nom}`.trim() }))
      } catch { options[f.key] = [] }
    } else if (f.type === 'ref') {
      try {
        const rows = await api.list(f.refEntity)
        let list = Array.isArray(rows) ? rows : (rows.items ?? [])
        // Filtre déclaratif (ex. { type: 'humaine' } pour les auditeurs, ou
        // { role: ['auditeur', 'voc'] } pour accepter plusieurs valeurs).
        if (f.refFilter) {
          list = list.filter((o) => Object.entries(f.refFilter).every(([k, v]) =>
            (Array.isArray(v) ? v.includes(o[k]) : o[k] === v)))
        }
        options[f.key] = list.map((o) => ({
          id: o.id,
          label: o[f.refLabel] || o.nom || o.titre || o.id,
          // clé de dépendance (règle d'intégrité : applications ∈ client de l'audit)
          dep: f.dependsOn ? (o.client_id ?? o.organisation_id ?? null) : null,
        }))
      } catch { options[f.key] = [] }
    } else if (f.type === 'refac' && f.options) {
      // Liste statique locale (aucun appel API) — ex. rôles prédéfinis d'une ressource.
      // Chaque entrée peut être une chaîne ou { value, label, dep } ; dep sert au
      // filtrage dépendant (ex. compétences suggérées selon le rôle choisi).
      options[f.key] = f.options.map((o) => (typeof o === 'object'
        ? { id: o.value, label: o.label, dep: o.dep ?? null }
        : { id: o, label: enumLabel(o), dep: null }))
    }
    // Suggestions issues d'une entité liée pour un champ texte libre (ex. Contact métier
    // d'une Application <- Ressources de l'organisation sélectionnée). Indépendant du
    // type du champ : n'alimente que des chips de suggestion, la valeur reste du texte.
    if (f.suggestFrom) {
      try {
        const rows = await api.list(f.suggestFrom.refEntity)
        const list = Array.isArray(rows) ? rows : (rows.items ?? [])
        options[f.key] = list.map((o) => ({
          id: o.id,
          label: o[f.suggestFrom.refLabel] || o.nom || o.titre || o.id,
          dep: f.suggestFrom.depKey ? (o[f.suggestFrom.depKey] ?? null) : null,
        }))
      } catch { options[f.key] = [] }
    }
  }
}

function optsFor(f) {
  const all = options[f.key] || []
  if (!f.dependsOn) return all
  const dep = model[f.dependsOn]
  if (!dep) return all // pas encore de client choisi : liste complète (le serveur revalide)
  return all.filter((o) => !o.dep || o.dep === dep)
}

// Suggestions cliquables pour un champ dont le contenu dépend d'un autre champ :
// - f.suggestionsByDep : liste statique par valeur de dépendance (ex. compétences par rôle) ;
// - f.suggestFrom      : liste chargée depuis une entité liée (ex. contact métier <- ressources).
// Dans tous les cas la saisie libre reste possible : ce ne sont que des raccourcis.
function suggestionsFor(f) {
  const dep = f.dependsOn ? model[f.dependsOn] : null
  let list = []
  if (f.suggestionsByDep) list = (dep && f.suggestionsByDep[dep]) || []
  else if (f.suggestFrom) list = (options[f.key] || []).filter((o) => !dep || o.dep === dep).map((o) => o.label)
  else return []

  if (f.type === 'tags') {
    const current = String(model[f.key] || '').split(',').map((s) => s.trim().toLowerCase()).filter(Boolean)
    return list.filter((s) => !current.includes(s.toLowerCase()))
  }
  return list.filter((s) => s !== model[f.key]).slice(0, 10)
}
function addSuggestion(f, value) {
  if (f.type === 'tags') {
    const current = String(model[f.key] || '').split(',').map((s) => s.trim()).filter(Boolean)
    current.push(value)
    model[f.key] = current.join(', ')
    return
  }
  model[f.key] = value
}

onMounted(() => {
  for (const f of props.fields) model[f.key] = initialValue(f)
  // Le contexte impose certaines valeurs (audit_id, client_id…) : priorité au prefill.
  for (const [k, v] of Object.entries(props.prefill)) model[k] = v
  loadOptions()
  loadStepFields()
})

// Un champ "steps" vit dans une table à part (ex. scenario_steps), pas embarqué dans
// l'enregistrement principal : on le recharge explicitement en édition.
async function loadStepFields() {
  if (!isEdit) return
  for (const f of props.fields) {
    if (f.type !== 'steps' || !f.loadFrom) continue
    try {
      const rows = await api.list(f.loadFrom, `?${f.loadKey}=${props.record.id}`)
      const list = (Array.isArray(rows) ? rows : (rows.items ?? []))
        .slice().sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0))
      model[f.key] = list.map((s) => ({
        id: s.id, technique: s.technique, tactique: s.tactique,
        commande: s.commande, description: s.description,
      }))
    } catch { /* laisse le tableau tel qu'initialisé */ }
    // Repli : certaines origines (import STIX) remplissent la colonne JSON de
    // l'enregistrement sans créer de lignes détaillées — on synthétise alors les
    // étapes depuis cette liste ; l'enregistrement les persistera (auto-guérison).
    const fb = f.fallbackFrom && props.record?.[f.fallbackFrom]
    if (!(model[f.key] || []).length && Array.isArray(fb) && fb.length) {
      model[f.key] = fb.map((t) => ({ technique: t, tactique: '', commande: '', description: '' }))
    }
  }
}

function buildPayload() {
  const out = {}
  for (const f of props.fields) {
    // Champs transitoires (ex. sélecteur d'acteur) : pilotent l'UI, jamais envoyés à l'API.
    if (f.transient) continue
    let v = model[f.key]
    if (f.type === 'tags') {
      v = String(v || '').split(',').map((s) => s.trim()).filter(Boolean)
      if (v.length || isEdit) out[f.key] = v
      continue
    }
    if (f.type === 'lines') {
      v = String(v || '').split('\n').map((s) => s.trim()).filter(Boolean)
      if (v.length || isEdit) out[f.key] = v
      continue
    }
    if (f.type === 'bool') {
      out[f.key] = v === true
      continue
    }
    if (f.type === 'ref' && f.multiple) {
      if ((Array.isArray(v) && v.length) || isEdit) out[f.key] = Array.isArray(v) ? v : []
      continue
    }
    if (v === '' || v === null || v === undefined) {
      if (isEdit) out[f.key] = null // permet d'effacer un champ en édition
      continue
    }
    if (f.type === 'number') v = Number(v)
    out[f.key] = v
  }
  return out
}

// Exécute l'action en ligne d'un champ (ex. bouton CIRCL à côté du CVE). f.inlineAction.run
// reçoit { model, record, isEdit } et peut renvoyer un objet de champs à pré-remplir —
// jamais appliqué par-dessus une valeur déjà saisie (cohérent avec le comportement serveur).
async function runInlineAction(f) {
  if (!f.inlineAction || inlineBusy.value) return
  inlineBusy.value = f.key
  error.value = null
  try {
    const patch = await f.inlineAction.run({ model, record: props.record, isEdit })
    if (patch && typeof patch === 'object') {
      for (const [k, val] of Object.entries(patch)) {
        if (val !== undefined && val !== null && val !== '' &&
            (model[k] === '' || model[k] === null || model[k] === undefined)) {
          model[k] = val
        }
      }
    }
  } catch (e) {
    error.value = e.message || 'Action impossible.'
  } finally {
    inlineBusy.value = null
  }
}

// Import des TTPs d'un threat actor (ActorTtpPicker) : ajoute les techniques cochées comme
// étapes (dédup par technique) dans le champ `steps` cible. Le nom de l'acteur est déjà écrit
// par le v-model du champ (acteur_emule) — ici on ne gère que la chaîne d'étapes.
function onActorImport(f, { steps }) {
  const key = f.targetSteps || 'etapes'
  const current = Array.isArray(model[key]) ? model[key] : []
  const have = new Set(current.map((s) => s.technique))
  const added = (steps || []).filter((s) => !have.has(s.technique))
  model[key] = [...current, ...added]
}

async function submit() {
  busy.value = true
  error.value = null
  // Validation cliente minimale (le serveur revalide) : champs requis non vides.
  const missing = props.fields.filter((f) => f.required && f.type !== 'bool' && !String(model[f.key] ?? '').trim())
  if (missing.length) {
    error.value = 'Champs requis manquants : ' + missing.map((f) => f.label).join(', ')
    busy.value = false
    return
  }
  try {
    const payload = buildPayload()
    if (isEdit) {
      await api.update(props.entity, props.record.id, payload)
      emit('saved')
      return
    }
    const created = await api.create(props.entity, payload)
    // Étape preuve optionnelle : on garde le tiroir ouvert avec le finding_id = id créé,
    // au lieu de fermer immédiatement. Sinon, comportement inchangé.
    if (props.evidenceUpload && created?.id) {
      createdRecord.value = created
      phase.value = 'evidence'
      return
    }
    emit('saved')
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) error.value = 'Action refusée par le serveur (droits ou cloisonnement).'
    else if (e instanceof ApiError && e.status === 401) error.value = 'Ré-authentification requise pour cette action.'
    else if (e instanceof ApiError && e.status === 422) error.value = 'Données invalides : ' + (e.detail || 'vérifiez les champs.')
    else error.value = e.message || 'Erreur'
  } finally {
    busy.value = false
  }
}

function onEvidenceUploaded() {
  evidenceCount.value += 1
  evidenceMsg.value = null
}

// Fermeture du tiroir : si un enregistrement a déjà été créé (phase preuve), le parent
// doit rafraîchir sa liste même sans clic sur « Terminer » → on émet 'saved'.
function onDrawerClose() {
  if (createdRecord.value) emit('saved')
  else emit('close')
}
</script>

<template>
  <DetailDrawer :title="title || (isEdit ? 'Modifier' : 'Nouveau')"
                :subtitle="phase === 'evidence' ? 'Preuves' : (isEdit ? 'Édition' : 'Création')" wide @close="onDrawerClose">
    <!-- Étape preuve (après création) : joindre des preuves à l'enregistrement créé. -->
    <div v-if="phase === 'evidence'" class="evi-phase">
      <p class="evi-ok">✓ Enregistrement créé. Vous pouvez y joindre des preuves (optionnel).</p>
      <EvidenceUpload
        v-if="createdRecord && createdRecord.audit_id"
        :audit-id="createdRecord.audit_id"
        :client-id="createdRecord.client_id"
        :finding-id="createdRecord.id"
        @uploaded="onEvidenceUploaded"
        @error="evidenceMsg = $event"
      />
      <p v-else class="muted">Aucun audit lié : impossible de joindre une preuve.</p>
      <p v-if="evidenceCount" class="evi-count">{{ evidenceCount }} preuve(s) ajoutée(s).</p>
      <p v-if="evidenceMsg" class="err">{{ evidenceMsg }}</p>
    </div>

    <div v-else class="grid">
      <div v-for="f in visibleFields" :key="f.key" class="field-row" :class="{ wide: f.type === 'textarea' || f.type === 'lines' || f.type === 'steps' || f.type === 'actor' }">
        <label class="lbl">{{ fieldLabel(f) }}<span v-if="f.required" class="req">*</span></label>

        <div v-if="f.inlineAction" class="input-action">
          <input class="field" type="text" v-model="model[f.key]" :placeholder="f.placeholder || ''" />
          <button type="button" class="icon-btn"
                  :disabled="inlineBusy === f.key || (f.inlineAction.enabled && !f.inlineAction.enabled(model, isEdit))"
                  :title="f.inlineAction.title" @click="runInlineAction(f)">
            <span v-if="inlineBusy === f.key" class="spin"></span><span v-else>{{ f.inlineAction.icon }}</span>
          </button>
        </div>
        <RefacSelect
          v-else-if="f.type === 'client' || f.type === 'ref' || f.type === 'refac'"
          :options="optsFor(f)" :multiple="!!f.multiple"
          :placeholder="f.placeholder || 'Rechercher…'" v-model="model[f.key]"
        />

        <select v-else-if="f.type === 'select'" class="field" v-model="model[f.key]">
          <option value="">—</option>
          <option v-for="o in f.options" :key="typeof o === 'object' ? o.value : o"
                  :value="typeof o === 'object' ? o.value : o">
            {{ typeof o === 'object' ? o.label : enumLabel(o) }}</option>
        </select>

        <textarea v-else-if="f.type === 'textarea'" class="field" rows="3" v-model="model[f.key]"></textarea>

        <input v-else-if="f.type === 'number'" class="field" type="number" :step="f.step || '1'" v-model="model[f.key]" />
        <input v-else-if="f.type === 'date'" class="field" type="date" v-model="model[f.key]" />
        <input v-else-if="f.type === 'datetime'" class="field" type="datetime-local" v-model="model[f.key]" />
        <input v-else-if="f.type === 'tags'" class="field" v-model="model[f.key]" placeholder="valeurs séparées par des virgules" />
        <TlpSelect v-else-if="f.type === 'tlp'" :variant="f.variant || 'tlp'" v-model="model[f.key]" />
        <label v-else-if="f.type === 'bool'" class="chk"><input type="checkbox" v-model="model[f.key]" /> {{ f.checkboxLabel || 'Oui' }}</label>
        <textarea v-else-if="f.type === 'lines'" class="field" rows="4" v-model="model[f.key]" placeholder="une valeur par ligne"></textarea>
        <RefPicker v-else-if="f.type === 'refpick'" :catalog="f.catalog" :multiple="!!f.multiple" v-model="model[f.key]" />
        <ActorTtpPicker v-else-if="f.type === 'actor'" v-model="model[f.key]" @import="onActorImport(f, $event)" />
        <StepsEditor v-else-if="f.type === 'steps'" v-model="model[f.key]" />
        <input v-else class="field" type="text" v-model="model[f.key]" :placeholder="f.placeholder || ''" />

        <!-- Suggestions cliquables (compétences par rôle, contact métier <- ressources…) :
             hors de la chaîne v-else-if ci-dessus pour ne pas la casser, s'applique à tout
             champ tags ou texte simple qui déclare suggestionsByDep / suggestFrom. -->
        <div v-if="(f.type === 'tags' || f.suggestFrom) && suggestionsFor(f).length" class="sugg">
          <span class="sugg-lbl">Suggestions :</span>
          <button v-for="s in suggestionsFor(f)" :key="s" type="button" class="sugg-chip" @click="addSuggestion(f, s)">+ {{ s }}</button>
        </div>
      </div>
    </div>

    <p v-if="error" class="err">{{ error }}</p>

    <template #footer>
      <template v-if="phase === 'evidence'">
        <button class="btn btn-primary" @click="emit('saved')">{{ t('common.close') }}</button>
      </template>
      <template v-else>
        <button class="btn" @click="emit('close')">{{ t('common.cancel') }}</button>
        <button class="btn btn-primary" :disabled="busy" @click="submit">
          {{ busy ? '…' : (isEdit ? t('common.save') : t('common.create')) }}
        </button>
      </template>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.field-row{display:flex;flex-direction:column}
.field-row.wide{grid-column:1 / -1}
.lbl{font-size:12px;color:var(--muted);margin-bottom:5px}
.req{color:var(--red);margin-left:3px}
.err{color:var(--red);margin-top:12px;font-size:13px}
.chk{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--text);padding:6px 0}
.sugg{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-top:6px}
.sugg-lbl{font-size:11px;color:var(--faint)}
.sugg-chip{border:1px dashed var(--border-2);background:transparent;color:var(--muted);border-radius:999px;
  padding:2px 9px;font-size:11.5px;cursor:pointer}
.sugg-chip:hover{border-color:var(--violet-accent);color:var(--violet-accent)}
.input-action{display:flex;gap:6px;align-items:stretch}
.input-action .field{flex:1}
.icon-btn{flex:0 0 auto;width:34px;border:1px solid var(--border);background:var(--surface-2);color:var(--muted);
  border-radius:var(--r-mini);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:14px}
.icon-btn:hover:not(:disabled){border-color:var(--violet-accent);color:var(--violet-accent)}
.icon-btn:disabled{opacity:.5;cursor:not-allowed}
.icon-btn .spin{width:11px;height:11px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;display:inline-block;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@media (max-width:560px){ .grid{grid-template-columns:1fr} }
.evi-phase{display:flex;flex-direction:column;gap:12px}
.evi-ok{color:var(--c-green-tx);font-size:13px;margin:0}
.evi-count{color:var(--muted);font-size:12.5px;margin:0}
.muted{color:var(--muted);font-size:13px}
</style>
