<script setup>
import { reactive, ref } from 'vue'
import { api, ApiError } from '../api/client'
import DetailDrawer from './DetailDrawer.vue'
import { ENTITY_FIELDS } from '../fields'

// Éditeur du bloc engagement (lettre d'engagement / NDA), calqué sur editEngagement
// de la maquette : les 18 champs sont lus depuis audit.engagement, édités, puis
// réécrits en un seul PUT sur l'audit (engagement = JSONB). Le serveur revalide
// (can('update','audits') + cloisonnement) ; un refus s'affiche sans fermer.
const props = defineProps({
  audit: { type: Object, required: true },
  // Valeurs par défaut dérivées de l'audit (périmètre, fenêtres, clauses NDA type…).
  // Priorité à la valeur déjà saisie ; le défaut ne remplit que les champs vides.
  defaults: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['close', 'saved'])

const fields = ENTITY_FIELDS.engagement
const eng = props.audit.engagement || {}
const model = reactive({})

function isEmpty(v) {
  if (Array.isArray(v)) return v.length === 0
  return v === null || v === undefined || v === ''
}

for (const f of fields) {
  // Valeur effective : saisie existante si présente, sinon repli sur le défaut d'audit.
  let v = eng[f.key]
  if (isEmpty(v) && f.key in props.defaults) v = props.defaults[f.key]
  if (f.type === 'lines') model[f.key] = Array.isArray(v) ? v.join('\n') : (v || '')
  else if (f.type === 'bool') model[f.key] = !!v
  else model[f.key] = v ?? ''
}

const busy = ref(false)
const error = ref(null)

function build() {
  const out = {}
  for (const f of fields) {
    const v = model[f.key]
    if (f.type === 'lines') out[f.key] = String(v || '').split('\n').map((s) => s.trim()).filter(Boolean)
    else if (f.type === 'bool') out[f.key] = v === true
    else out[f.key] = v === '' ? null : v
  }
  return out
}

async function submit() {
  busy.value = true
  error.value = null
  try {
    // Fusion : on ne perd aucune clé existante non éditée (ex. champs futurs).
    const merged = { ...(props.audit.engagement || {}), ...build() }
    await api.update('audits', props.audit.id, { engagement: merged })
    emit('saved')
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) error.value = 'Modification refusée (droits ou cloisonnement).'
    else error.value = e.message || 'Erreur.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <DetailDrawer title="Lettre d'engagement" subtitle="édition" wide @close="emit('close')">
    <div class="grid">
      <div v-for="f in fields" :key="f.key" class="field-row"
           :class="{ wide: f.type === 'textarea' || f.type === 'lines' }">
        <label class="lbl">{{ f.label }}</label>
        <textarea v-if="f.type === 'textarea'" class="field" rows="3" v-model="model[f.key]"></textarea>
        <textarea v-else-if="f.type === 'lines'" class="field" rows="4" v-model="model[f.key]"
                  placeholder="une valeur par ligne"></textarea>
        <label v-else-if="f.type === 'bool'" class="chk">
          <input type="checkbox" v-model="model[f.key]" /> {{ f.checkboxLabel || 'Oui' }}</label>
        <input v-else class="field" type="text" v-model="model[f.key]" />
      </div>
    </div>
    <p v-if="error" class="err">{{ error }}</p>
    <template #footer>
      <button class="btn" @click="emit('close')">Annuler</button>
      <button class="btn btn-primary" :disabled="busy" @click="submit">{{ busy ? '…' : 'Enregistrer' }}</button>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px 16px}
.field-row{display:flex;flex-direction:column;gap:5px}
.field-row.wide{grid-column:1 / -1}
.lbl{font-size:12px;color:var(--muted)}
.field{width:100%;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-mini);
  padding:7px 9px;color:var(--text);font:inherit}
.field:focus{outline:none;border-color:var(--violet, var(--border-2))}
.chk{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--text)}
.err{color:var(--c-red-tx);font-size:13px;margin-top:10px}
</style>
