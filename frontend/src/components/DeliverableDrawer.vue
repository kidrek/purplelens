<script setup>
import { computed } from 'vue'
import DetailDrawer from './DetailDrawer.vue'

// Visionneuse de livrable : métadonnées + ouverture du document scellé. Le binaire ne
// transite jamais par l'API ; l'ouverture passe par une URL présignée courte (déléguée
// au parent). Le PDF s'affiche dans le navigateur (consultable et imprimable).
const props = defineProps({
  deliverable: { type: Object, required: true },
  clientName: { type: String, default: '—' },
  typeLabel: { type: String, default: '' },
})
const emit = defineEmits(['close', 'open'])

const d = computed(() => props.deliverable)
const meta = computed(() => d.value.meta || {})
</script>

<template>
  <DetailDrawer :title="d.titre" :subtitle="typeLabel || 'Livrable'" wide @close="emit('close')">
    <template #actions>
      <button class="btn btn-primary slim" @click="emit('open', d)">Ouvrir le document</button>
    </template>

    <div class="badges">
      <span v-if="d.statut" class="pill pill-green">{{ d.statut }}</span>
      <span v-if="d.langue" class="pill pill-gray">{{ d.langue === 'fr' ? 'Français' : d.langue }}</span>
      <span v-if="d.tlp" :class="['tlp', 'tlp-' + d.tlp]">TLP:{{ d.tlp }}</span>
    </div>

    <section class="sec">
      <div class="sec-t">Livrable</div>
      <dl class="dl">
        <dt>Type</dt><dd>{{ typeLabel || d.type }}</dd>
        <dt>Client</dt><dd>{{ clientName }}</dd>
        <dt>Statut</dt><dd>{{ d.statut }}</dd>
        <dt>Marquage</dt><dd>TLP:{{ d.tlp || '—' }}</dd>
      </dl>
    </section>

    <section v-if="meta.sections || meta.constats != null" class="sec">
      <div class="sec-t">Contenu</div>
      <dl class="dl">
        <dt v-if="meta.constats != null">Constats</dt><dd v-if="meta.constats != null">{{ meta.constats }}</dd>
        <dt v-if="meta.pages">Pages</dt><dd v-if="meta.pages">{{ meta.pages }}</dd>
      </dl>
      <ul v-if="Array.isArray(meta.sections)" class="sections">
        <li v-for="(sec, i) in meta.sections" :key="i">{{ sec.titre || sec }}</li>
      </ul>
    </section>

    <div class="viewer-note">
      Le document est scellé (Object Lock) et sa consultation est tracée au journal.
      Ouvrez-le pour le visualiser et l'imprimer depuis le navigateur.
    </div>

    <template #footer>
      <button class="btn" @click="emit('close')">Fermer</button>
      <button class="btn btn-primary" @click="emit('open', d)">Ouvrir le document</button>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.slim{padding:3px 9px;font-size:11.5px}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;align-items:center}
.sec{margin-bottom:18px}
.sec-t{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight);margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--border-2)}
.dl{display:grid;grid-template-columns:120px 1fr;gap:7px 12px;margin:0;font-size:13px}
.dl dt{color:var(--muted)} .dl dd{margin:0;color:var(--text)}
.sections{margin:8px 0 0;padding-left:18px;font-size:13px;color:var(--text)}
.sections li{margin-bottom:3px}
.viewer-note{margin-top:8px;padding:11px 14px;background:var(--surface-2);border:1px solid var(--border-2);border-radius:var(--r-card);font-size:11.5px;color:var(--muted);line-height:1.5}
</style>
