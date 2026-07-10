<script setup>
import EvidenceProgress from './EvidenceProgress.vue'
import { api, ApiError } from '../api/client'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

// Carte de preuve. Le téléchargement demande au serveur une URL présignée courte ;
// le binaire ne transite jamais par l'API. Un refus (403) est affiché tel quel —
// il est déjà tracé côté serveur dans evidence_access.
const props = defineProps({ item: { type: Object, required: true } })
const { t } = useI18n()
const busy = ref(false)
const msg = ref(null)

async function download() {
  busy.value = true; msg.value = null
  try {
    const r = await api.get(`/evidence/${props.item.id}/download`)
    if (r?.url) window.open(r.url, '_blank')
  } catch (e) {
    msg.value = e instanceof ApiError && e.status === 403
      ? t('common.forbidden')
      : (e instanceof ApiError && e.status === 401 ? t('common.step_up') : e.message)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="evi-card card">
    <div class="head">
      <span class="name">{{ item.filename || item.id }}</span>
      <span v-if="item.tlp" :class="['tlp', 'tlp-' + item.tlp]">{{ item.tlp }}</span>
    </div>
    <div class="meta">
      <span class="pill" :class="item.ingest_status === 'stored' ? 'pill-green' : 'pill-amber'">
        {{ item.ingest_status === 'stored' ? t('evidence.stored') : t('evidence.quarantine') }}
      </span>
      <span v-if="item.sha256_plaintext" class="hash">sha256:{{ String(item.sha256_plaintext).slice(0, 12) }}…</span>
    </div>
    <EvidenceProgress :status="item.ingest_status" />
    <div class="actions">
      <button class="btn btn-primary" :disabled="busy || item.ingest_status !== 'stored'" @click="download">
        {{ t('evidence.download') }}
      </button>
    </div>
    <p v-if="msg" class="msg">{{ msg }}</p>
  </div>
</template>

<style scoped>
.evi-card{height:100%;display:flex;flex-direction:column}
.head{display:flex;justify-content:space-between;align-items:center}
.name{font-family:var(--font-data);font-weight:600;color:var(--heading)}
.meta{display:flex;gap:10px;align-items:center;margin:6px 0;font-size:11px;color:var(--muted)}
.hash{font-family:var(--font-data)}
.actions{margin-top:8px}
.msg{margin-top:8px;color:var(--amber);font-size:12px}
</style>
