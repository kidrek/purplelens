<script setup>
import { onMounted, ref } from 'vue'
import { api, ApiError } from '../api/client'
import EvidenceCard from '../components/EvidenceCard.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const items = ref([])
const loading = ref(true)
const error = ref(null)

async function load() {
  loading.value = true; error.value = null
  try {
    const d = await api.list('evidence')
    items.value = Array.isArray(d) ? d : (d?.items ?? [])
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? t('common.forbidden') : e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <div>
    <div class="eyebrow">Coffre-fort</div>
    <h1>{{ t('evidence.title') }}</h1>
    <div class="panel note">{{ t('evidence.note') }}</div>

    <p v-if="loading" class="muted">{{ t('common.loading') }}</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <p v-else-if="items.length === 0" class="muted">{{ t('common.empty') }}</p>
    <div v-else class="gallery">
      <EvidenceCard v-for="e in items" :key="e.id" :item="e" />
    </div>
  </div>
</template>

<style scoped>
.note{margin:12px 0 18px;color:var(--muted);font-size:12px;border-left:3px solid var(--violet)}
/* Galerie responsive (DA §5.1) : grille de cartes, min 180px, plutôt qu'une liste verticale */
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:var(--gap-lg)}
</style>
