<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, ApiError } from '../api/client'
const { t } = useI18n()

// Le journal est consultable (lecture seule pour tous les rôles, y compris admin).
// Le bouton « Vérifier » demande au serveur de recalculer la chaîne de hachage.
const entries = ref([])
const loading = ref(true)
const error = ref(null)
const verify = ref(null)

async function load() {
  loading.value = true; error.value = null
  try {
    const d = await api.journal()
    entries.value = Array.isArray(d) ? d : (d?.items ?? [])
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? 'Refusé' : e.message
  } finally { loading.value = false }
}
async function runVerify() {
  try { verify.value = await api.journalVerify() }
  catch (e) { verify.value = { intact: false, error: e.message } }
}
onMounted(load)
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.journal.eyebrow') }}</div>
    <h1>{{ t('views.journal.title') }}</h1>
    <div class="bar">
      <button class="btn" @click="load">Rafraîchir</button>
      <button class="btn btn-primary" @click="runVerify">Vérifier l'intégrité de la chaîne</button>
      <span v-if="verify" :class="verify.intact ? 'ok' : 'ko'">
        {{ verify.intact ? '✔ Chaîne intacte' : '✘ Rupture détectée' }}
        <template v-if="verify.break_seq"> (séq. {{ verify.break_seq }})</template>
      </span>
    </div>

    <p v-if="loading" class="muted">Chargement…</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <table v-else>
      <thead><tr><th>Séq.</th><th>Événement</th><th>Acteur</th><th>Empreinte</th><th>Date</th></tr></thead>
      <tbody>
        <tr v-for="e in entries" :key="e.seq || e.id">
          <td>{{ e.seq }}</td>
          <td><span class="pill pill-violet">{{ e.event_type }}</span></td>
          <td>{{ e.actor_label || '—' }}</td>
          <td class="mono">{{ String(e.curr_hash || '').slice(0, 14) }}…</td>
          <td>{{ e.created_at }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.bar{display:flex;gap:10px;align-items:center;margin:12px 0}
.ok{color:var(--green)} .ko{color:var(--red)}
.mono{font-family:var(--font-data)}
</style>
