<script setup>
// Sélecteur TLP (ou PAP) visuel : pastilles colorées cliquables plutôt qu'un menu
// déroulant. TLP borne la diffusion ; PAP borne les actions permises (taxonomie MISP).
const props = defineProps({
  modelValue: { type: String, default: '' },
  // 'tlp' (RED/AMBER/GREEN/CLEAR) ou 'pap' (RED/AMBER/GREEN/WHITE).
  variant: { type: String, default: 'tlp' },
})
const emit = defineEmits(['update:modelValue'])

const LEVELS = {
  tlp: ['RED', 'AMBER', 'GREEN', 'CLEAR'],
  pap: ['RED', 'AMBER', 'GREEN', 'WHITE'],
}
function pick(l) { emit('update:modelValue', l) }
</script>

<template>
  <div class="tlp-select" role="radiogroup">
    <button
      v-for="l in LEVELS[variant] || LEVELS.tlp" :key="l" type="button"
      :class="['chip', 't-' + l, { on: modelValue === l }]"
      role="radio" :aria-checked="modelValue === l" @click="pick(l)"
    >
      <span class="dot"></span>{{ variant === 'pap' ? 'PAP' : 'TLP' }}:{{ l }}
    </button>
  </div>
</template>

<style scoped>
.tlp-select{display:flex;flex-wrap:wrap;gap:6px}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border);background:var(--surface);
  color:var(--muted);border-radius:var(--r-pill);padding:4px 11px;font-size:12px;font-family:var(--font-data);
  cursor:pointer;transition:all var(--t,.15s) var(--ease,ease)}
.chip .dot{width:8px;height:8px;border-radius:50%;background:currentColor}
.chip.on{border-width:2px;font-weight:600}
.t-RED{color:var(--red)} .t-RED.on{background:var(--c-red-bg);border-color:var(--c-red-bd);color:var(--c-red-tx)}
.t-AMBER{color:var(--amber)} .t-AMBER.on{background:var(--c-amber-bg);border-color:var(--c-amber-bd);color:var(--c-amber-tx)}
.t-GREEN{color:var(--green)} .t-GREEN.on{background:var(--c-green-bg);border-color:var(--c-green-bd);color:var(--c-green-tx)}
.t-CLEAR,.t-WHITE{color:var(--muted)} .t-CLEAR.on,.t-WHITE.on{background:var(--surface-3);border-color:var(--muted);color:var(--heading)}
</style>
