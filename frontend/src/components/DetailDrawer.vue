<script setup>
import { onMounted, onUnmounted } from 'vue'

// Tiroir latéral générique : en-tête (titre + sous-titre + actions), corps défilant,
// pied optionnel. Fermeture par Échap, clic sur le voile, ou bouton ✕.
defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  wide: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

// Pile partagée des drawers ouverts : plusieurs instances peuvent maintenant
// s'empiler (ex. CorpusArticleDrawer ouvert par-dessus un drawer d'entité, DA §4.6).
// Chaque instance écoute Échap sur `document` indépendamment ; sans cette pile,
// une seule pression fermerait tous les drawers ouverts à la fois.
const id = Symbol('drawer')
function onKey(e) {
  if (e.key === 'Escape' && drawerStack[drawerStack.length - 1] === id) emit('close')
}
onMounted(() => { drawerStack.push(id); document.addEventListener('keydown', onKey) })
onUnmounted(() => {
  const i = drawerStack.indexOf(id)
  if (i !== -1) drawerStack.splice(i, 1)
  document.removeEventListener('keydown', onKey)
})
</script>

<script>
const drawerStack = []
</script>

<template>
  <teleport to="body">
    <div class="scrim" @click.self="emit('close')">
      <aside :class="['drawer', { wide }]" role="dialog" aria-modal="true">
        <header class="d-head">
          <div class="d-titles">
            <div v-if="subtitle" class="d-eyebrow">{{ subtitle }}</div>
            <h2 class="d-title">{{ title }}</h2>
          </div>
          <div class="d-actions">
            <slot name="actions" />
            <button class="d-x" @click="emit('close')" aria-label="Fermer">✕</button>
          </div>
        </header>
        <div class="d-body"><slot /></div>
        <footer v-if="$slots.footer" class="d-foot"><slot name="footer" /></footer>
      </aside>
    </div>
  </teleport>
</template>

<style scoped>
.scrim{position:fixed;inset:0;background:var(--scrim);z-index:60;display:flex;justify-content:flex-end}
.drawer{width:min(560px,96vw);max-width:96vw;height:100%;background:var(--surface);border-left:1px solid var(--border);
  display:flex;flex-direction:column;box-shadow:var(--shadow-lg,-8px 0 32px rgba(0,0,0,.3));animation:slidein var(--t,.18s) var(--ease,ease)}
.drawer.wide{width:min(60vw,1100px)}
@keyframes slidein{from{transform:translateX(24px);opacity:.6}to{transform:none;opacity:1}}
.d-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:16px 18px;border-bottom:1px solid var(--border-2)}
.d-eyebrow{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.d-title{font-family:var(--font-display);font-size:18px;color:var(--heading);margin:2px 0 0;line-height:1.25}
.d-actions{display:flex;align-items:center;gap:8px;flex:0 0 auto}
.d-x{border:0;background:transparent;color:var(--muted);cursor:pointer;font-size:16px;padding:2px 6px;border-radius:var(--r-mini)}
.d-x:hover{background:var(--surface-2);color:var(--heading)}
.d-body{flex:1;overflow-y:auto;padding:16px 18px}
.d-foot{padding:12px 18px;border-top:1px solid var(--border-2);display:flex;justify-content:flex-end;gap:8px}
</style>
