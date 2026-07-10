<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import DetailDrawer from './DetailDrawer.vue'
const { t } = useI18n()

// Détail d'une application : identité technique, exposition/criticité, valeur métier.
const props = defineProps({ app: { type: Object, required: true } })
const emit = defineEmits(['close', 'edit'])

const CRIT_TONE = { critique: 'red', haute: 'amber', elevee: 'amber', moyenne: 'cyan', basse: 'green' }
const a = computed(() => props.app)
const tags = computed(() => (Array.isArray(a.value.tags) ? a.value.tags : []))
</script>

<template>
  <DetailDrawer :title="a.nom" :subtitle="a.code ? 'Application · ' + a.code : 'Application'" @close="emit('close')">
    <template #actions>
      <button class="btn slim" @click="emit('edit', a)">{{ t('common.edit') }}</button>
    </template>

    <div class="badges">
      <span v-if="a.criticite" :class="['pill', 'pill-' + (CRIT_TONE[String(a.criticite).toLowerCase()] || 'gray')]">Criticité {{ a.criticite }}</span>
      <span v-if="a.exposition" class="pill pill-amber">{{ a.exposition }}</span>
      <span v-if="a.statut" class="pill pill-gray">{{ a.statut }}</span>
      <span v-if="a.tlp" class="pill pill-gray">TLP:{{ a.tlp }}</span>
    </div>

    <section class="sec">
      <div class="sec-t">{{ t('sec.identite') }}</div>
      <dl class="dl">
        <dt>Type</dt><dd>{{ a.type || '—' }}</dd>
        <dt>Version</dt><dd>{{ a.version || '—' }}</dd>
        <dt>URL</dt><dd><a v-if="a.url" :href="a.url" target="_blank" rel="noopener" class="a">{{ a.url }}</a><span v-else>—</span></dd>
        <dt>Stack</dt><dd>{{ a.stack || '—' }}</dd>
        <dt>Contact métier</dt><dd>{{ a.contact_metier || '—' }}</dd>
      </dl>
    </section>

    <section class="sec">
      <div class="sec-t">{{ t('sec.enjeux') }}</div>
      <dl class="dl">
        <dt>Exposition</dt><dd>{{ a.exposition || '—' }}</dd>
        <dt>Valeur métier</dt><dd>{{ a.valeur_metier || '—' }}</dd>
      </dl>
    </section>

    <section v-if="tags.length" class="sec">
      <div class="sec-t">{{ t('sec.tags') }}</div>
      <div><span v-for="t in tags" :key="t" class="chip">{{ t }}</span></div>
    </section>
  </DetailDrawer>
</template>

<style scoped>
.slim{padding:3px 9px;font-size:11.5px}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}
.sec{margin-bottom:18px}
.sec-t{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight);margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--border-2)}
.dl{display:grid;grid-template-columns:130px 1fr;gap:7px 12px;margin:0;font-size:13px}
.dl dt{color:var(--muted)} .dl dd{margin:0;color:var(--text)}
.a{color:var(--violet-accent);text-decoration:none} .a:hover{text-decoration:underline}
.chip{display:inline-block;background:var(--surface-3);border:1px solid var(--border-2);border-radius:var(--r-pill);padding:1px 8px;font-size:11.5px;margin:0 4px 4px 0}
</style>
