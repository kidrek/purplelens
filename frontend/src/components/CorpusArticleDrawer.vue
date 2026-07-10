<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import DetailDrawer from './DetailDrawer.vue'
import { useCorpus } from '../composables/useCorpus'
import { icons } from '../icons'

const props = defineProps({
  slug: { type: String, default: '' },
  articleId: { type: String, default: '' },
})
const emit = defineEmits(['close'])

const { t, locale } = useI18n()
const { preloadCorpus, corpusById, corpusBySlug, natureTone, corpusType, tr } = useCorpus()

onMounted(preloadCorpus)

// Slug affiché : initialisé depuis la prop, puis modifiable en interne par les
// « articles liés » (DA §4.5) — on navigue dans le même drawer, sans le refermer.
const currentSlug = ref(props.slug)
watch(() => props.slug, (v) => { currentSlug.value = v })

const article = computed(() =>
  (currentSlug.value && corpusBySlug(currentSlug.value)) || (props.articleId && corpusById(props.articleId)) || null
)
const titre = computed(() => {
  const a = article.value
  if (!a) return ''
  return locale.value === 'en' && a.titre_en ? a.titre_en : a.titre_fr
})
const type = computed(() => corpusType(article.value))
const contenu = computed(() => article.value?.contenu || {})
const etapes = computed(() => contenu.value.etapes || [])
// Rendu par nature (DA §4.3) : procédure = liste d'étapes numérotées (steps
// {texte, role, sortie}), processus = flux vertical de phases (stages
// {texte, description, decision}), article métier = prose (+ tableau optionnel).
const isProcedure = computed(() => article.value?.nature === 'procedure' && etapes.value.length > 0)
const isProcessus = computed(() => article.value?.nature === 'processus' && etapes.value.length > 0)

function etapeTexte(e) { return tr(e?.texte ?? e?.t ?? e, locale.value) }
function etapeSortie(e) { return e && typeof e === 'object' ? tr(e.sortie ?? e.out, locale.value) : '' }
function etapeRole(e) { return e && typeof e === 'object' ? (e.role ?? e.r ?? '') : '' }
function etapeDecision(e) { return e && typeof e === 'object' ? tr(e.decision ?? e.dec, locale.value) : '' }

// Articles liés (DA §4.5) : slugs -> articles résolus, avec pastille de nature.
const related = computed(() =>
  (contenu.value.lies || []).map((s) => corpusBySlug(s)).filter(Boolean)
)
function relatedTitle(r) { return locale.value === 'en' && r.titre_en ? r.titre_en : r.titre_fr }
function openRelated(r) {
  currentSlug.value = r.slug
  // remonte le corps du drawer en haut pour lire le nouvel article
  document.querySelector('.d-body')?.scrollTo({ top: 0 })
}

// Contrôles ISO : pas d'URL par contrôle en base (contrairement à la maquette) —
// on relie vers la norme générique (réemploi §4.2 "pills cliquables").
const ISO_URL = 'https://www.iso.org/standard/27001'

// Export .md (reprend fidèlement corpusExport() de la maquette, purement client).
function exportStartingPoint() {
  const a = article.value
  if (!a || !a.gabarit) return
  const L = []
  L.push('> ' + t('corpus.disclaimer')); L.push('')
  L.push('# ' + titre.value); L.push('')
  if (tr(contenu.value.resume, locale.value)) { L.push(tr(contenu.value.resume, locale.value)); L.push('') }
  if (tr(contenu.value.objectif, locale.value)) { L.push('**' + t('corpus.objLabel') + '** ' + tr(contenu.value.objectif, locale.value)); L.push('') }
  if (tr(contenu.value.quand, locale.value)) { L.push('**' + t('corpus.when') + '** ' + tr(contenu.value.quand, locale.value)); L.push('') }
  if (etapes.value.length) {
    L.push('## ' + t(isProcessus.value ? 'corpus.flow' : 'corpus.steps')); L.push('')
    etapes.value.forEach((e, i) => {
      const role = etapeRole(e)
      L.push((i + 1) + '. ' + etapeTexte(e) + (role ? '  _[' + role + ']_' : ''))
      const desc = e && typeof e === 'object' ? tr(e.description, locale.value) : ''
      if (desc) L.push('   ' + desc)
      const out = etapeSortie(e)
      if (out) L.push('   → ' + out)
      const dec = etapeDecision(e)
      if (dec) L.push('   ⚖ ' + dec)
    })
    if (tr(contenu.value.loop, locale.value)) L.push('   ' + tr(contenu.value.loop, locale.value))
    L.push('')
  }
  const prose = contenu.value.prose || []
  if (prose.length) { prose.forEach((p) => { L.push(tr(p, locale.value)); L.push('') }) }
  const kp = contenu.value.keypoints || []
  if (kp.length) { L.push('## ' + t('corpus.keypoints')); L.push(''); kp.forEach((k) => L.push('- ' + tr(k, locale.value))); L.push('') }
  const pg = contenu.value.pieges || []
  if (pg.length) { L.push('## ' + t('corpus.pieges')); L.push(''); pg.forEach((p) => L.push('- ' + tr(p, locale.value))); L.push('') }
  L.push('---')
  if (contenu.value.source?.label) {
    L.push(t('corpus.source') + ' : ' + contenu.value.source.label + (contenu.value.source.url ? ' — ' + contenu.value.source.url : ''))
  }
  if ((a.controles_iso || []).length) L.push(t('corpus.normes') + ' : ' + a.controles_iso.join(', '))
  L.push(t('corpus.statut') + ' : ' + t('corpus.generic'))

  const blob = new Blob([L.join('\n')], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const el = document.createElement('a')
  el.href = url
  el.download = a.slug + (locale.value === 'en' ? '_starting_point.md' : '_point_de_depart.md')
  el.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <DetailDrawer v-if="article" wide :title="titre" @close="emit('close')">
    <div class="corp-body-sec">
      <!-- Bandeau de chips (DA §4.2) -->
      <div class="chip-set">
        <span class="chip" :class="natureTone(article.nature)">
          <span class="dot"></span>{{ t('corpus.n.' + article.nature) }}
        </span>
        <span class="chip gray">{{ t('corpus.t.' + type) }}</span>
        <span v-for="p in article.profils" :key="p" class="chip violet">{{ t('corpus.p.' + p) }}</span>
        <a v-for="c in article.controles_iso" :key="c" class="corp-norme" :href="ISO_URL" target="_blank" rel="noopener">{{ c }} ↗</a>
        <span v-if="contenu.hds" class="corp-norme">{{ t('corpus.hds') }} : {{ contenu.hds }}</span>
      </div>

      <p v-if="tr(contenu.resume, locale)" class="resume">{{ tr(contenu.resume, locale) }}</p>

      <!-- Objectif -->
      <div v-if="tr(contenu.objectif, locale)" class="corp-obj">
        <span v-html="icons.target"></span>
        <p>{{ tr(contenu.objectif, locale) }}</p>
      </div>

      <!-- Quand -->
      <div v-if="tr(contenu.quand, locale)" class="corp-when">
        <span v-html="icons.clock"></span>
        <span><b>{{ t('corpus.when') }}</b> {{ tr(contenu.quand, locale) }}</span>
      </div>

      <!-- (a) Procédure — étapes numérotées -->
      <section v-if="isProcedure" class="panel">
        <h3 class="corp-sec-h"><span class="lbl">{{ t('corpus.steps') }}</span></h3>
        <ol class="corp-steps">
          <li v-for="(e, i) in etapes" :key="i">
            <span class="corp-step-n"></span>
            <span class="corp-step-t">
              {{ etapeTexte(e) }}
              <span v-if="etapeSortie(e)" class="corp-step-out">{{ etapeSortie(e) }}</span>
            </span>
            <span v-if="etapeRole(e)" class="corp-step-r">{{ etapeRole(e) }}</span>
          </li>
        </ol>
      </section>

      <!-- (b) Processus — flux vertical -->
      <section v-if="isProcessus" class="panel">
        <h3 class="corp-sec-h"><span class="lbl">{{ t('corpus.flow') }}</span></h3>
        <div class="corp-flow">
          <div v-for="(e, i) in etapes" :key="i" class="corp-stage">
            <div class="corp-stage-dot"></div>
            <div class="corp-stage-body">
              <p class="corp-stage-t">{{ i + 1 }} · {{ etapeTexte(e) }}</p>
              <p v-if="e?.description || e?.d" class="corp-stage-d">{{ tr(e.description ?? e.d, locale) }}</p>
              <span v-if="etapeDecision(e)" class="corp-dec">{{ etapeDecision(e) }}</span>
            </div>
          </div>
        </div>
        <p v-if="tr(contenu.loop, locale)" class="corp-loop">{{ tr(contenu.loop, locale) }}</p>
      </section>

      <!-- (c) Article métier — prose (+ tableau optionnel) -->
      <div v-if="(contenu.prose || []).length" class="corp-prose">
        <p v-for="(p, i) in contenu.prose" :key="i">{{ tr(p, locale) }}</p>
      </div>
      <table v-if="contenu.table" class="corp-table">
        <thead>
          <tr><th v-for="(h, i) in contenu.table.head" :key="i">{{ tr(h, locale) }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in contenu.table.rows" :key="i">
            <td>
              <span class="chip" :class="r.tone" style="height:20px">
                <span class="dot"></span><span class="data">{{ tr(r.label, locale) }}</span>
              </span>
            </td>
            <td>{{ tr(r.texte, locale) }}</td>
          </tr>
        </tbody>
      </table>

      <!-- À retenir -->
      <section v-if="(contenu.keypoints || []).length" class="panel">
        <div class="corp-sec-h">
          <span class="ic" v-html="icons.check"></span>
          <span class="lbl">{{ t('corpus.keypoints') }}</span>
        </div>
        <ul class="corp-key">
          <li v-for="(k, i) in contenu.keypoints" :key="i">{{ tr(k, locale) }}</li>
        </ul>
      </section>

      <!-- Pièges fréquents -->
      <section v-if="(contenu.pieges || []).length" class="panel">
        <div class="corp-sec-h">
          <span class="ic" v-html="icons.warning"></span>
          <span class="lbl">{{ t('corpus.pieges') }}</span>
        </div>
        <ul class="corp-piege">
          <li v-for="(p, i) in contenu.pieges" :key="i">
            <span v-html="icons.warning"></span><span>{{ tr(p, locale) }}</span>
          </li>
        </ul>
      </section>

      <!-- Gabarit : disclaimer + export -->
      <div v-if="article.gabarit">
        <div class="corp-callout">
          <b>{{ t('corpus.generic') }}</b>
          <span>{{ t('corpus.disclaimer') }}</span>
        </div>
        <button class="btn btn-primary" @click="exportStartingPoint">{{ t('corpus.export') }}</button>
      </div>

      <!-- Pour aller plus loin (liens externes) -->
      <section v-if="(contenu.aller || []).length" class="panel">
        <div class="corp-sec-h"><span class="lbl">{{ t('corpus.aller') }}</span></div>
        <div class="corp-aller">
          <a v-for="(l, i) in contenu.aller" :key="i" :href="l.url" target="_blank" rel="noopener">
            {{ tr(l.label, locale) }} ↗
          </a>
        </div>
      </section>

      <!-- Articles liés (navigation interne) -->
      <section v-if="related.length" class="panel">
        <div class="corp-sec-h"><span class="lbl">{{ t('corpus.lies') }}</span></div>
        <div class="corp-lies">
          <button v-for="r in related" :key="r.slug" class="corp-lie" @click="openRelated(r)">
            <span class="cd" :class="r.nature"></span>{{ relatedTitle(r) }}
          </button>
        </div>
      </section>

      <!-- Méta de pied -->
      <div class="corp-meta">
        <span v-if="contenu.source?.label">
          <b>{{ t('corpus.source') }}</b> :
          <a v-if="contenu.source.url" class="corp-src" :href="contenu.source.url" target="_blank" rel="noopener">{{ contenu.source.label }} ↗</a>
          <span v-else>{{ contenu.source.label }}</span>
        </span>
        <span v-if="tr(contenu.outil, locale)"><b>{{ t('corpus.outil') }}</b> : {{ tr(contenu.outil, locale) }}</span>
        <span><b>{{ t('corpus.statut') }}</b> : {{ t('corpus.generic') }}</span>
      </div>
    </div>
  </DetailDrawer>
</template>

<style scoped>
.chip-set{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.resume{color:var(--muted);font-size:13px;font-style:italic;margin:0}
h3.corp-sec-h{margin:0 0 9px;font-size:inherit;font-weight:inherit}
</style>
