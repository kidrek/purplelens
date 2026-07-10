<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import CorpusArticleDrawer from '../components/CorpusArticleDrawer.vue'
import { useCorpus } from '../composables/useCorpus'

// Bibliothèque méthodologique (corpus de la maquette, embarqué au seed) — DA v2.7 §4.
// Page liste + filtres (§4.1) ; la lecture d'un article se fait dans un drawer dédié
// (§4.2, motif liste + drawer §0.4) plutôt que dans un panneau de lecture inline.
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { corpusRows, corpusLoaded, corpusError, preloadCorpus, tr } = useCorpus()

const NATURES = ['procedure', 'processus', 'metier']
const PROFILS = ['aud', 'voc', 'cti', 'mgr'] // ordre et liste = filtre de la maquette

const fNature = ref('all')
const fProfil = ref('all')
const q = ref('')
const openSlug = ref(route.query.open || null) // article ouvert dans le drawer (par slug)

// Ancrage contextuel (⌘K, bouton "Corpus" d'un autre drawer) : ?open=<slug> ouvre
// directement l'article visé, y compris en arrivant déjà sur cette page.
watch(() => route.query.open, (v) => { if (v) openSlug.value = v })
function closeArticle() {
  openSlug.value = null
  if (route.query.open) router.replace({ path: '/bibliotheque' })
}

const titre = (r) => (locale.value === 'en' && r.titre_en ? r.titre_en : r.titre_fr)

const filtered = computed(() => corpusRows.value.filter((r) => {
  if (fNature.value !== 'all' && r.nature !== fNature.value) return false
  if (fProfil.value !== 'all' && !(r.profils || []).includes(fProfil.value)) return false
  if (q.value) {
    const hay = `${titre(r)} ${tr(r.contenu?.resume, locale.value)}`.toLowerCase()
    if (!hay.includes(q.value.toLowerCase())) return false
  }
  return true
}))

onMounted(preloadCorpus)
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.bibliotheque.eyebrow') }}</div>
    <h1>{{ t('views.bibliotheque.title') }}</h1>
    <p class="page-intro">{{ t('corpus.intro') }}</p>

    <p v-if="!corpusLoaded && !corpusError" class="muted">{{ t('common.loading') }}</p>
    <p v-else-if="corpusError" class="err">{{ corpusError }}</p>

    <template v-else>
      <!-- Filtres (DA §4.1) -->
      <div class="corp-filters">
        <button class="corp-fchip" :class="{ on: fProfil === 'all' }" @click="fProfil = 'all'">{{ t('corpus.allProfils') }}</button>
        <button v-for="p in PROFILS" :key="p" class="corp-fchip" :class="{ on: fProfil === p }" @click="fProfil = p">
          {{ t('corpus.p.' + p) }}
        </button>
        <span class="corp-fsep"></span>
        <button class="corp-fchip" :class="{ on: fNature === 'all' }" @click="fNature = 'all'">{{ t('corpus.allNatures') }}</button>
        <button v-for="n in NATURES" :key="n" class="corp-fchip" :class="{ on: fNature === n }" @click="fNature = n">
          <span class="corp-dot" :class="n" style="width:7px;height:7px"></span>{{ t('corpus.n.' + n) }}
        </button>
        <label class="corp-search">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" />
          </svg>
          <input type="text" v-model="q" :placeholder="t('corpus.search')" />
        </label>
      </div>
      <p class="count muted"><span class="data">{{ filtered.length }}</span> {{ t('corpus.count') }}</p>

      <!-- Liste dense (DA §4.1) -->
      <div class="corp-list" v-if="filtered.length">
        <button v-for="r in filtered" :key="r.id" class="corp-row" @click="openSlug = r.slug">
          <span class="corp-dot" :class="r.nature"></span>
          <span class="corp-row-main">
            <span class="corp-row-title">{{ titre(r) }}</span>
            <span class="corp-row-sub">{{ t('corpus.n.' + r.nature) }} · {{ (r.profils || []).map((p) => t('corpus.p.' + p)).join(', ') }}</span>
          </span>
          <span class="corp-badges">
            <span v-if="r.gabarit" class="chip gray sm">{{ t('corpus.t.gabarit') }}</span>
            <span v-for="c in (r.controles_iso || []).slice(0, 2)" :key="c" class="corp-norme">{{ c }}</span>
          </span>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="opacity:.5;flex:0 0 auto">
            <path d="m9 6 6 6-6 6" />
          </svg>
        </button>
      </div>
      <p v-else class="muted">{{ t('corpus.empty') }}</p>
    </template>

    <CorpusArticleDrawer v-if="openSlug" :slug="openSlug" @close="closeArticle" />
  </div>
</template>

<style scoped>
.page-intro{color:var(--muted);font-size:12.5px;margin:2px 0 16px;max-width:72ch}
.count{font-size:11px;margin:10px 0}
</style>
