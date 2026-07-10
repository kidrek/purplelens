<script setup>
import { computed, ref, onMounted } from 'vue'
import { api } from '../api/client'
import RefPicker from './RefPicker.vue'
import AttckTtpMatrix from './AttckTtpMatrix.vue'

// Éditeur de la chaîne d'étapes offensives d'un scénario (cahier §A00.1) : chaque étape
// porte { technique, tactique, commande, description }. `techniques` et `d3fend` du
// scénario sont dérivés serveur de cette liste à l'enregistrement — non éditables ici.
const props = defineProps({ modelValue: { type: Array, default: () => [] } })
const emit = defineEmits(['update:modelValue'])

// Catalogue ATT&CK local (pour afficher la tactique de la technique choisie sans
// aller-retour serveur à chaque sélection).
const attackEntries = ref([])
onMounted(async () => {
  try { attackEntries.value = (await api.get('/reference/attack/entries')).entries || [] }
  catch { attackEntries.value = [] }
})
function tacticOf(extId) {
  return attackEntries.value.find((e) => e.ext_id === extId)?.tactic || ''
}

// Techniques uniques des étapes, dans l'ordre — alimente l'aperçu TTPs ATT&CK en
// lecture seule ci-dessous (même dérivation que côté serveur à l'enregistrement).
const previewTechniques = computed(() => {
  const seen = []
  for (const s of props.modelValue) {
    if (s.technique && !seen.includes(s.technique)) seen.push(s.technique)
  }
  return seen
})

function update(list) { emit('update:modelValue', list) }
function addStep() {
  update([...(props.modelValue || []), {
    id: `tmp-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    technique: '', tactique: '', commande: '', description: '',
  }])
}
function removeStep(i) {
  const list = [...props.modelValue]
  list.splice(i, 1)
  update(list)
}
function moveStep(i, dir) {
  const list = [...props.modelValue]
  const j = i + dir
  if (j < 0 || j >= list.length) return
  ;[list[i], list[j]] = [list[j], list[i]]
  update(list)
}
function setField(i, key, val) {
  const list = props.modelValue.map((s, idx) => (idx === i ? { ...s, [key]: val } : s))
  // La tactique suit automatiquement la technique choisie (référentiel ATT&CK).
  if (key === 'technique') list[i].tactique = tacticOf(val)
  update(list)
}
</script>

<template>
  <div class="steps">
    <div v-if="!modelValue.length" class="empty">Aucune étape pour l'instant — ajoutez la première technique offensive.</div>
    <div v-for="(s, i) in modelValue" :key="s.id || i" class="step-row">
      <div class="step-n">{{ i + 1 }}</div>
      <div class="step-body">
        <div class="step-line">
          <div class="step-tech">
            <RefPicker catalog="attack" :model-value="s.technique"
                       @update:model-value="(v) => setField(i, 'technique', v)"
                       placeholder="Rechercher une technique ATT&CK…" />
          </div>
          <span v-if="s.tactique" class="tactic-tag">{{ s.tactique }}</span>
        </div>
        <input class="field" :value="s.commande" @input="(e) => setField(i, 'commande', e.target.value)"
               placeholder="Outil / commande (optionnel)" />
        <textarea class="field" rows="2" :value="s.description"
                  @input="(e) => setField(i, 'description', e.target.value)"
                  placeholder="Description de l'étape (optionnel)"></textarea>
      </div>
      <div class="step-actions">
        <button type="button" class="icon-sm" title="Monter" :disabled="i === 0" @click="moveStep(i, -1)">↑</button>
        <button type="button" class="icon-sm" title="Descendre" :disabled="i === modelValue.length - 1" @click="moveStep(i, 1)">↓</button>
        <button type="button" class="icon-sm danger" title="Retirer" @click="removeStep(i)">✕</button>
      </div>
    </div>
    <button type="button" class="btn slim" @click="addStep">+ Ajouter une étape</button>

    <div v-if="previewTechniques.length" class="preview">
      <div class="preview-lbl">Aperçu — généré automatiquement depuis les techniques ci-dessus</div>
      <AttckTtpMatrix :techniques="previewTechniques" />
    </div>
  </div>
</template>

<style scoped>
.preview{margin-top:14px}
.preview-lbl{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10px;color:var(--faint);margin-bottom:8px}
.steps{display:flex;flex-direction:column;gap:10px}
.empty{font-size:12px;color:var(--faint);background:var(--surface-2);border:1px solid var(--border-2);
  border-radius:var(--r-mini);padding:10px 12px}
.step-row{display:flex;gap:8px;align-items:flex-start;background:var(--surface-2);border:1px solid var(--border-2);
  border-radius:var(--r-mini);padding:10px}
.step-n{flex:0 0 auto;width:22px;height:22px;border-radius:50%;background:var(--c-violet-bg);color:var(--c-violet-tx);
  display:flex;align-items:center;justify-content:center;font-family:var(--font-data);font-size:11px;font-weight:700;margin-top:2px}
.step-body{flex:1;display:flex;flex-direction:column;gap:6px;min-width:0}
.step-line{display:flex;align-items:center;gap:8px}
.step-tech{flex:1;min-width:0}
.tactic-tag{flex:0 0 auto;font-size:10px;color:var(--faint);font-family:var(--font-eyebrow);
  text-transform:uppercase;letter-spacing:.03em;background:var(--surface-3);border-radius:var(--r-mini);padding:3px 7px}
.step-actions{flex:0 0 auto;display:flex;flex-direction:column;gap:4px}
.icon-sm{width:24px;height:24px;border:1px solid var(--border);background:var(--surface);color:var(--muted);
  border-radius:var(--r-mini);cursor:pointer;font-size:11px;display:flex;align-items:center;justify-content:center}
.icon-sm:hover:not(:disabled){border-color:var(--violet-accent);color:var(--violet-accent)}
.icon-sm.danger:hover{border-color:var(--red);color:var(--red)}
.icon-sm:disabled{opacity:.4;cursor:not-allowed}
.slim{padding:6px 12px;font-size:12.5px}
</style>
