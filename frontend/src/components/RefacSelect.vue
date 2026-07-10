<script setup>
import { computed, ref } from 'vue'

// Sélecteur de clé étrangère avec autocomplétion (« refac » de la maquette) : recherche
// filtrée sur des options {id,label} déjà chargées et cloisonnées RLS par l'API.
// Meilleur qu'un menu déroulant quand la liste est longue (audits, scénarios, ressources).
const props = defineProps({
  modelValue: { type: [String, Array, null], default: '' },
  options: { type: Array, default: () => [] }, // [{ id, label }]
  placeholder: { type: String, default: 'Rechercher…' },
  // Multi-sélection (chips) : modelValue devient un tableau d'ids.
  multiple: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const q = ref('')
const open = ref(false)
const hi = ref(0)

const selectedLabel = computed(() => {
  const o = props.options.find((x) => x.id === props.modelValue)
  return o ? o.label : ''
})
const selectedIds = computed(() => (Array.isArray(props.modelValue) ? props.modelValue : []))
const selectedItems = computed(() =>
  selectedIds.value.map((id) => props.options.find((x) => x.id === id) || { id, label: id }))
const filtered = computed(() => {
  const n = q.value.trim().toLowerCase()
  return props.options
    .filter((o) => !(props.multiple && selectedIds.value.includes(o.id))) // déjà choisis exclus
    .filter((o) => !n || String(o.label).toLowerCase().includes(n))
    .slice(0, 40)
})

function pick(o) {
  if (props.multiple) {
    emit('update:modelValue', [...selectedIds.value, o.id])
    q.value = ''
    hi.value = 0
    return // reste ouvert : saisie de plusieurs valeurs à la suite
  }
  emit('update:modelValue', o.id); q.value = ''; open.value = false
}
function unpick(id) { emit('update:modelValue', selectedIds.value.filter((x) => x !== id)) }
function clear() { emit('update:modelValue', ''); q.value = ''; open.value = true }
function onKey(e) {
  if (!open.value && (e.key === 'ArrowDown' || e.key === 'Enter')) { open.value = true; return }
  const n = filtered.value.length
  if (e.key === 'ArrowDown') { e.preventDefault(); hi.value = (hi.value + 1) % Math.max(1, n) }
  else if (e.key === 'ArrowUp') { e.preventDefault(); hi.value = (hi.value - 1 + n) % Math.max(1, n) }
  else if (e.key === 'Enter') { e.preventDefault(); if (filtered.value[hi.value]) pick(filtered.value[hi.value]) }
  else if (e.key === 'Escape') { open.value = false }
}
</script>

<template>
  <div class="refac" @focusout="open = false" tabindex="-1">
    <!-- Multi-sélection : chips + champ de recherche toujours visible -->
    <div v-if="multiple">
      <div v-if="selectedItems.length" class="chips">
        <span v-for="it in selectedItems" :key="it.id" class="chip">
          {{ it.label }}
          <button type="button" class="x" @click="unpick(it.id)" aria-label="Retirer">✕</button>
        </span>
      </div>
      <div class="box">
        <input
          class="field" v-model="q" :placeholder="placeholder" autocomplete="off"
          @focus="open = true" @keydown="onKey"
        />
        <div v-if="open && filtered.length" class="menu">
          <button
            v-for="(o, i) in filtered" :key="o.id" type="button"
            :class="['opt', { hi: i === hi }]"
            @mousedown.prevent="pick(o)" @mouseenter="hi = i"
          >{{ o.label }}</button>
        </div>
        <div v-else-if="open && q" class="menu empty">Aucun résultat.</div>
      </div>
    </div>
    <!-- Valeur sélectionnée (mode compact) -->
    <div v-else-if="modelValue && selectedLabel" class="chosen">
      <span class="lbl">{{ selectedLabel }}</span>
      <button type="button" class="x" @click="clear" aria-label="Changer">✕</button>
    </div>
    <!-- Saisie/recherche -->
    <div v-else class="box">
      <input
        class="field" v-model="q" :placeholder="placeholder" autocomplete="off"
        @focus="open = true" @keydown="onKey"
      />
      <div v-if="open && filtered.length" class="menu">
        <button
          v-for="(o, i) in filtered" :key="o.id" type="button"
          :class="['opt', { hi: i === hi }]"
          @mousedown.prevent="pick(o)" @mouseenter="hi = i"
        >{{ o.label }}</button>
      </div>
      <div v-else-if="open && q" class="menu empty">Aucun résultat.</div>
    </div>
  </div>
</template>

<style scoped>
.refac{position:relative}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border);
  background:var(--surface-2);border-radius:999px;padding:3px 10px;font-size:12.5px;color:var(--heading)}
.chip .x{border:0;background:transparent;color:var(--muted);cursor:pointer;font-size:12px;padding:0}
.chosen{display:flex;align-items:center;justify-content:space-between;gap:8px;border:1px solid var(--border);
  background:var(--surface);border-radius:var(--r-mini);padding:7px 10px}
.chosen .lbl{font-size:13px;color:var(--heading)}
.chosen .x{border:0;background:transparent;color:var(--muted);cursor:pointer;font-size:13px}
.box{position:relative}
.menu{position:absolute;left:0;right:0;top:calc(100% + 4px);z-index:20;background:var(--surface);
  border:1px solid var(--border);border-radius:var(--r-mini);box-shadow:var(--shadow);max-height:230px;overflow-y:auto;padding:4px}
.opt{display:block;width:100%;text-align:left;border:0;background:transparent;border-radius:var(--r-mini);
  padding:6px 9px;cursor:pointer;color:var(--text);font:inherit;font-size:12.5px}
.opt.hi{background:var(--surface-2)}
.menu.empty{padding:10px;color:var(--faint);font-size:12px}
</style>
