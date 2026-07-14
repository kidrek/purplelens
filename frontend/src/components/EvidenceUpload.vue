<script setup>
// Composant d'upload de preuve (cahier §6quater).
//
// Flux en 3 étapes :
//   1. L'utilisateur sélectionne un fichier.
//   2. Le frontend appelle POST /api/evidence → obtient une URL présignée MinIO.
//   3. Le frontend fait un PUT direct vers MinIO (le binaire ne touche JAMAIS l'API),
//      puis appelle POST /api/evidence/{id}/ingest pour déclencher le sas (Celery).
//
// Le composant émet :
//   @uploaded(evidenceId)  — preuve traitée avec succès
//   @error(message)        — erreur (taille, réseau, refus serveur)
//   @progress(pct)         — progression de l'upload (0–100)

import { ref } from 'vue'
import { api, ApiError } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useI18n } from 'vue-i18n'

const MAX_BYTES = 209_715_200 // 200 Mo — cohérent avec MAX_EVIDENCE_BYTES

const props = defineProps({
  // Identifiants requis pour l'initialisation.
  auditId: { type: String, required: true },
  clientId: { type: String, required: true },
  // ID de la vulnérabilité (finding_id) — optionnel, permet de lier une preuve
  // à une vulnérabilité sans FK en base.
  findingId: { type: String, default: null },
  // Valeurs par défaut TLP/PAP.
  defaultTlp: { type: String, default: 'RED' },
  defaultPap: { type: String, default: 'RED' },
})

const emit = defineEmits(['uploaded', 'error', 'progress'])
const { t } = useI18n()
const auth = useAuthStore()

const busy = ref(false)
const msg = ref(null)
const fileName = ref('')
const fileSize = ref(0)
const fileMime = ref('')
const fileInputRef = ref(null)
const selectedFile = ref(null)

async function selectFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (file.size > MAX_BYTES) {
    event.target.value = ''
    emit('error', t('upload.too_large'))
    return
  }
  fileName.value = file.name
  fileSize.value = file.size
  fileMime.value = file.type || ''
  selectedFile.value = file
  msg.value = null
}

async function upload() {
  const file = selectedFile.value
  if (!file) return
  busy.value = true
  msg.value = null

  try {
    // Étape 1 : initialiser la preuve (création DB + DEK + URL présignée).
    const init = await api.initEvidence({
      audit_id: props.auditId,
      client_id: props.clientId,
      finding_id: props.findingId,
      original_filename: fileName.value,
      declared_mime: fileMime.value || undefined,
      size_bytes: fileSize.value,
      tlp: props.defaultTlp,
      pap: props.defaultPap,
    })

    // Étape 2 : PUT direct vers MinIO (le binaire ne touche pas l'API).
    const uploadResp = await fetch(init.upload_url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': fileMime.value || 'application/octet-stream' },
    })
    if (!uploadResp.ok) {
      throw new ApiError(uploadResp.status, 'upload_failed', 'Échec du dépôt MinIO.')
    }

    // Étape 3 : signaler la fin de l'upload → déclencher le sas.
    await api.post(`/evidence/${init.evidence_id}/ingest`)

    emit('uploaded', init.evidence_id)
  } catch (e) {
    // Dépôt d'une preuve TLP:RED/AMBER refusé faute de session MFA (porte 2, côté API) :
    // message actionnable plutôt que « forbidden » opaque. On s'appuie sur l'état MFA
    // connu du client (le serveur ne divulgue pas le motif précis du 403).
    let detail = e instanceof ApiError ? e.message : e.message
    if (e instanceof ApiError && e.status === 403 && !auth.user?.mfa) {
      detail = t('upload.mfa_required')
    }
    emit('error', detail)
  } finally {
    busy.value = false
    fileName.value = ''
    fileSize.value = 0
    fileMime.value = ''
    selectedFile.value = null
  }
}
</script>

<template>
  <div class="evi-upload card">
    <div class="head">
      <span class="title">{{ t('upload.title') }}</span>
      <span v-if="busy" class="spinner"></span>
    </div>

    <!-- Avertissement proactif : sans session MFA, une preuve TLP:RED/AMBER (le défaut)
         sera refusée au dépôt comme au téléchargement → on oriente vers l'enrôlement. -->
    <p v-if="!auth.user?.mfa" class="mfa-notice">
      {{ t('upload.mfa_notice') }}
      <RouterLink to="/account" class="mfa-link">{{ t('evidence.mfa_account_link') }}</RouterLink>
    </p>

    <!-- Zone de sélection de fichier -->
    <label v-if="!busy && !fileName" class="drop-zone">
      <input
        ref="fileInputRef"
        type="file"
        class="hidden"
        :accept="fileMime || undefined"
        @change="selectFile"
      />
      <span class="drop-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 16V4" />
          <path d="m7 9 5-5 5 5" />
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
        </svg>
      </span>
      <span class="drop-text">{{ t('upload.drop') }}</span>
      <span class="drop-hint">{{ t('upload.hint') }}</span>
    </label>

    <!-- Fichier sélectionné : carte + bouton d'upload affirmé -->
    <div v-else-if="!busy" class="selected">
      <div class="file-card">
        <span class="file-thumb" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <path d="M14 2v6h6" />
          </svg>
        </span>
        <span class="file-meta">
          <span class="file-name">{{ fileName }}</span>
          <span class="file-size">{{ (fileSize / 1024 / 1024).toFixed(1) }} Mo</span>
        </span>
        <button
          class="clear-btn"
          :title="t('common.cancel')"
          :aria-label="t('common.cancel')"
          @click="() => { fileName = ''; fileSize = 0; fileMime = ''; selectedFile = null; if (fileInputRef) fileInputRef.value = ''; msg = null; }"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
            <path d="M18 6 6 18" /><path d="m6 6 12 12" />
          </svg>
        </button>
      </div>

      <button class="btn btn-primary upload-btn" @click="upload">
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M12 16V4" /><path d="m7 9 5-5 5 5" />
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
        </svg>
        {{ t('upload.upload') }}
      </button>
    </div>

    <!-- Messages -->
    <p v-if="msg" class="msg">{{ msg }}</p>
  </div>
</template>

<style scoped>
.evi-upload{padding:16px}
.head{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.title{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.spinner{width:12px;height:12px;border:2px solid var(--violet);border-right-color:transparent;border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

.drop-zone{display:flex;flex-direction:column;align-items:center;gap:2px;border:2px dashed var(--border-2);border-radius:var(--r-card);padding:22px 24px;text-align:center;cursor:pointer;transition:border-color var(--t) var(--ease),background var(--t) var(--ease)}
.drop-zone:hover{border-color:var(--violet);background:var(--violet-soft)}
.hidden{display:none}
.drop-icon{display:inline-flex;align-items:center;justify-content:center;width:42px;height:42px;margin-bottom:6px;border-radius:50%;background:var(--violet-soft);color:var(--violet);transition:transform var(--t) var(--ease),background var(--t) var(--ease)}
.drop-zone:hover .drop-icon{transform:translateY(-2px);background:var(--c-violet-bg)}
.drop-text{display:block;font-size:13px;font-weight:600;color:var(--text)}
.drop-hint{font-size:11px;color:var(--faint)}

/* Fichier sélectionné */
.selected{display:flex;flex-direction:column;gap:12px}
.file-card{display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--c-violet-bd);border-radius:var(--r-card);background:var(--violet-soft)}
.file-thumb{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;flex:0 0 auto;border-radius:8px;background:var(--c-violet-bg);color:var(--violet)}
.file-meta{display:flex;flex-direction:column;gap:1px;min-width:0;flex:1 1 auto}
.file-name{font-family:var(--font-data);font-size:13px;color:var(--heading);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.file-size{font-size:11px;color:var(--faint)}
.clear-btn{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;flex:0 0 auto;border:0;border-radius:50%;background:transparent;color:var(--faint);cursor:pointer;transition:background var(--t) var(--ease),color var(--t) var(--ease)}
.clear-btn:hover{background:var(--c-red-bg);color:var(--red)}

.upload-btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;width:100%}

.msg{margin-top:8px;font-size:12px;color:var(--red)}
/* Avertissement MFA (dépôt de preuve sensible sans session forte) */
.mfa-notice{margin:0 0 12px;padding:8px 10px;font-size:11.5px;color:var(--c-amber-tx);background:var(--c-amber-bg);border:1px solid var(--c-amber-bd);border-radius:var(--r-mini)}
.mfa-link{color:var(--violet);font-weight:600;text-decoration:none;margin-left:4px}
.mfa-link:hover{text-decoration:underline}
</style>
