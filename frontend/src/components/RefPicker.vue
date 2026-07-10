<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api/client'

// Champ d'autocomplétion adossé à un catalogue de référence (ATT&CK, D3FEND, OWASP,
// CWE, CAPEC). Les entrées viennent de la BASE (ce qui a été importé via Paramètres),
// donc le formulaire valide contre le référentiel réellement en place.
//   - multiple=false : la valeur est un ext_id (chaîne), ex. "CWE-79".
//   - multiple=true  : la valeur est un tableau d'ext_id, ex. ["T1566","T1059"].
const props = defineProps({
  modelValue: { type: [String, Array, null], default: null },
  catalog: { type: String, required: true },
  multiple: { type: Boolean, default: false },
  placeholder: { type: String, default: 'Rechercher…' },
})
const emit = defineEmits(['update:modelValue'])

const entries = ref([])
const loaded = ref(false)
const q = ref('')
const openList = ref(false)
const hi = ref(0) // index surligné

onMounted(async () => {
  try {
    const d = await api.get(`/reference/${props.catalog}/entries`)
    entries.value = d.entries || []
  } catch { entries.value = [] }
  finally { loaded.value = true }
})

const byId = computed(() => Object.fromEntries(entries.value.map((e) => [e.ext_id, e])))
const selected = computed(() => {
  if (props.multiple) return Array.isArray(props.modelValue) ? props.modelValue : []
  return props.modelValue ? [props.modelValue] : []
})
const label = (id) => { const e = byId.value[id]; return e ? `${id} — ${e.name}` : id }

// Suggestions filtrées (exclut les déjà sélectionnés en mode multiple).
const suggestions = computed(() => {
  const needle = q.value.trim().toLowerCase()
  const sel = new Set(selected.value)
  return entries.value
    .filter((e) => !(props.multiple && sel.has(e.ext_id)))
    .filter((e) => !needle || e.ext_id.toLowerCase().includes(needle) || (e.name || '').toLowerCase().includes(needle))
    .slice(0, 30)
})
watch(q, () => { hi.value = 0; openList.value = true })

function pick(e) {
  if (props.multiple) {
    emit('update:modelValue', [...selected.value, e.ext_id])
    q.value = ''
  } else {
    emit('update:modelValue', e.ext_id)
    q.value = ''
    openList.value = false
  }
}
function removeAt(id) {
  if (props.multiple) emit('update:modelValue', selected.value.filter((x) => x !== id))
  else emit('update:modelValue', null)
}
function onKey(e) {
  if (!openList.value && (e.key === 'ArrowDown' || e.key === 'Enter')) { openList.value = true; return }
  const n = suggestions.value.length
  if (e.key === 'ArrowDown') { e.preventDefault(); hi.value = (hi.value + 1) % Math.max(1, n) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); hi.value = (hi.value - 1 + n) % Math.max(1, n) }
  else if (e.key === 'Enter') { e.preventDefault(); if (suggestions.value[hi.value]) pick(suggestions.value[hi.value]) }
  else if (e.key === 'Escape') { openList.value = false }
}
</script>

<template>
  <div class="refpick" @focusout="openList = false" tabindex="-1">
    <!-- valeurs sélectionnées -->
    <div v-if="selected.length" class="chips">
      <span v-for="id in selected" :key="id" class="chip">
        {{ label(id) }}
        <button type="button" class="x" @click="removeAt(id)" aria-label="Retirer">×</button>
      </span>
    </div>

    <!-- saisie (masquée en mode simple une fois une valeur choisie) -->
    <div v-if="multiple || !selected.length" class="box">
      <input
        class="field" v-model="q" :placeholder="loaded ? placeholder : 'Chargement du référentiel…'"
        @focus="openList = true" @keydown="onKey" autocomplete="off"
      />
      <div v-if="openList && suggestions.length" class="menu">
        <button
          v-for="(e, i) in suggestions" :key="e.ext_id" type="button"
          class="opt" :class="{ hi: i === hi }"
          @mousedown.prevent="pick(e)" @mouseenter="hi = i"
        >
          <span class="code">{{ e.ext_id }}</span>
          <span class="nm">{{ e.name }}</span>
          <span v-if="e.tactic" class="tac">{{ e.tactic }}</span>
        </button>
      </div>
      <div v-else-if="openList && loaded && q" class="menu empty">
        Aucune entrée. Importez ce référentiel dans Paramètres si besoin.
      </div>
    </div>
  </div>
</template>

<style scoped>
.refpick{display:flex;flex-direction:column;gap:6px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{display:inline-flex;align-items:center;gap:6px;background:var(--c-violet-bg);border:1px solid var(--c-violet-bd);
  color:var(--c-violet-tx);border-radius:var(--r-pill);padding:2px 8px;font-size:12px;font-family:var(--font-data)}
.chip .x{border:0;background:transparent;color:inherit;cursor:pointer;font-size:14px;line-height:1;padding:0}
.box{position:relative}
.menu{position:absolute;left:0;right:0;top:calc(100% + 4px);z-index:20;background:var(--surface);
  border:1px solid var(--border);border-radius:var(--r-mini);box-shadow:var(--shadow);max-height:240px;overflow-y:auto;padding:4px}
.opt{display:flex;align-items:center;gap:9px;width:100%;text-align:left;border:0;background:transparent;
  border-radius:var(--r-mini);padding:6px 9px;cursor:pointer;color:var(--text);font:inherit}
.opt.hi{background:var(--surface-2)}
.opt .code{font-family:var(--font-data);font-size:12px;font-weight:600;color:var(--heading);min-width:74px}
.opt .nm{flex:1;font-size:12.5px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.opt .tac{font-size:10px;color:var(--faint);font-family:var(--font-eyebrow);text-transform:uppercase}
.menu.empty{padding:10px;color:var(--faint);font-size:12px}
</style>
