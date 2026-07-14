<script setup>
import EvidenceProgress from './EvidenceProgress.vue'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useI18n } from 'vue-i18n'

// Carte de preuve. Le téléchargement renvoie le CONTENU DÉCHIFFRÉ par l'API (le binaire
// est chiffré au repos ; le clair ne vit qu'en mémoire, jamais écrit ni présigné).
// Servir le clair d'une preuve TLP:RED exige une session MFA (porte 2) ET un step-up
// récent : sur 401 step_up_required on demande un code TOTP en ligne puis on rejoue ;
// sur 403 (motif jamais divulgué) on oriente vers l'enrôlement MFA si la session n'en a pas.
const props = defineProps({
  item: { type: Object, required: true },
  // 'card' : vignette en grille (défaut) ; 'row' : ligne de tableau (<tr>).
  layout: { type: String, default: 'card' },
})
const { t } = useI18n()
const auth = useAuthStore()
const busy = ref(false)
const msg = ref(null)
const needStepUp = ref(false)   // 401 : formulaire TOTP inline affiché
const mfaHint = ref(false)      // 403 sans session MFA : invite à enrôler
const otp = ref('')

// Pastille d'état à 3 valeurs (backend : quarantined | stored | rejected). L'état
// quarantined est « vivant » (traitement en cours) → classe .processing qui pulse
// pour signaler que le statut va se mettre à jour tout seul.
const statusPill = computed(() => {
  switch (props.item.ingest_status) {
    case 'stored':
      return { cls: 'pill-green', label: t('evidence.stored') }
    case 'rejected':
      return { cls: 'pill-red', label: t('evidence.rejected') }
    default:
      return { cls: 'pill-amber processing', label: t('evidence.quarantine') }
  }
})

async function download() {
  busy.value = true; msg.value = null; mfaHint.value = false
  try {
    const resp = await fetch(`/api/evidence/${props.item.id}/content`, { credentials: 'include' })
    if (!resp.ok) {
      if (resp.status === 401) {
        // Réauth récente exigée pour le clair d'une preuve TLP:RED → step-up inline
        // (le formulaire porte son propre libellé, pas de message redondant).
        needStepUp.value = true
      } else if (resp.status === 403) {
        // 403 générique : cause la plus fréquente ici = session sans MFA face à une
        // preuve sensible. On oriente vers l'enrôlement plutôt qu'un « interdit » opaque.
        if (!auth.user?.mfa) mfaHint.value = true
        else msg.value = t('common.forbidden')
      } else {
        msg.value = t('evidence.download_failed')
      }
      return
    }
    needStepUp.value = false
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = props.item.original_filename || 'evidence'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch {
    msg.value = t('evidence.download_failed')
  } finally {
    busy.value = false
  }
}

async function confirmStepUp() {
  if (!otp.value) return
  msg.value = null
  try {
    await api.stepUp(otp.value)   // /auth/step-up : réémet la session, auth_time frais
    otp.value = ''
    needStepUp.value = false
    await auth.fetchMe()          // rafraîchit le flag mfa affiché (pastille, hints)
    await download()              // rejoue le téléchargement, désormais autorisé
  } catch {
    msg.value = t('evidence.totp_refused')
  }
}
</script>

<template>
  <!-- Vue TABLEAU : la preuve est une ligne <tr>, plus une ligne secondaire pour les
       messages / step-up / hint MFA (colspan pleine largeur). Le composant a alors
       plusieurs racines <tr> (fragment) pour s'insérer dans un <tbody>. -->
  <template v-if="layout === 'row'">
    <tr class="evi-tr">
      <td class="c-text">{{ item.organisation_nom || '—' }}</td>
      <td class="c-text">{{ item.application_nom || '—' }}</td>
      <td class="c-text" :title="item.audit_nom || ''">{{ item.audit_nom || '—' }}</td>
      <td class="c-text">{{ item.uploader_nom || '—' }}</td>
      <td class="c-file" :title="item.original_filename || ''">{{ item.original_filename || item.id }}</td>
      <td class="c-date">{{ item.uploaded_at ? new Date(item.uploaded_at).toLocaleDateString() : '—' }}</td>
      <td class="c-hash">
        <span v-if="item.sha256_plaintext" class="hash">sha256:{{ String(item.sha256_plaintext).slice(0, 12) }}…</span>
        <template v-else>—</template>
      </td>
      <td class="c-tlp">
        <span v-if="item.tlp" :class="['tlp', 'tlp-' + item.tlp]">{{ item.tlp }}</span>
        <template v-else>—</template>
      </td>
      <td class="c-action">
        <button class="btn btn-primary slim"
                :disabled="busy || item.ingest_status !== 'stored' || item.contains_secrets"
                :title="item.contains_secrets ? t('evidence.secret_masked') : ''"
                @click="download">
          {{ item.contains_secrets ? t('evidence.secret_masked') : t('evidence.download') }}
        </button>
      </td>
    </tr>
    <tr v-if="msg || needStepUp || mfaHint" class="evi-tr-extra">
      <td colspan="9">
        <p v-if="msg" class="msg">{{ msg }}</p>
        <div v-if="needStepUp" class="stepup">
          <label class="stepup-lbl">{{ t('evidence.step_up_prompt') }}</label>
          <div class="stepup-row">
            <input class="field otpf" v-model="otp" inputmode="numeric" autocomplete="one-time-code"
                   placeholder="TOTP" @keyup.enter="confirmStepUp" />
            <button class="btn btn-primary slim" :disabled="!otp" @click="confirmStepUp">
              {{ t('evidence.step_up_confirm') }}
            </button>
          </div>
        </div>
        <p v-if="mfaHint" class="msg mfa-hint">
          {{ t('evidence.mfa_required') }}
          <RouterLink to="/account" class="mfa-link">{{ t('evidence.mfa_account_link') }}</RouterLink>
        </p>
      </td>
    </tr>
  </template>

  <!-- Vue GRILLE (carte) : disposition verticale d'origine. -->
  <div v-else class="evi-card card">
    <div class="head">
      <span class="name">{{ item.original_filename || item.id }}</span>
      <span v-if="item.tlp" :class="['tlp', 'tlp-' + item.tlp]">{{ item.tlp }}</span>
    </div>
    <div class="meta">
      <span class="pill" :class="statusPill.cls">{{ statusPill.label }}</span>
      <span v-if="item.sha256_plaintext" class="hash">sha256:{{ String(item.sha256_plaintext).slice(0, 12) }}…</span>
    </div>
    <EvidenceProgress :status="item.ingest_status" />
    <div class="actions">
      <button class="btn btn-primary"
              :disabled="busy || item.ingest_status !== 'stored' || item.contains_secrets"
              :title="item.contains_secrets ? t('evidence.secret_masked') : ''"
              @click="download">
        {{ item.contains_secrets ? t('evidence.secret_masked') : t('evidence.download') }}
      </button>
    </div>
    <p v-if="msg" class="msg">{{ msg }}</p>

    <!-- 401 : réauthentification récente (step-up) demandée pour le clair TLP:RED -->
    <div v-if="needStepUp" class="stepup">
      <label class="stepup-lbl">{{ t('evidence.step_up_prompt') }}</label>
      <div class="stepup-row">
        <input class="field otpf" v-model="otp" inputmode="numeric" autocomplete="one-time-code"
               placeholder="TOTP" @keyup.enter="confirmStepUp" />
        <button class="btn btn-primary slim" :disabled="!otp" @click="confirmStepUp">
          {{ t('evidence.step_up_confirm') }}
        </button>
      </div>
    </div>

    <!-- 403 sans session MFA : orienter vers l'enrôlement plutôt qu'un refus opaque -->
    <p v-if="mfaHint" class="msg mfa-hint">
      {{ t('evidence.mfa_required') }}
      <RouterLink to="/account" class="mfa-link">{{ t('evidence.mfa_account_link') }}</RouterLink>
    </p>
  </div>
</template>

<style scoped>
.evi-card{height:100%;display:flex;flex-direction:column}
.head{display:flex;justify-content:space-between;align-items:center}
.name{font-family:var(--font-data);font-weight:600;color:var(--heading)}
/* Vue tableau : cellules de la ligne <tr>. Le nom peut être long → ellipsis ;
   l'action reste calée à droite, la ligne secondaire (step-up/MFA) s'étend sur
   toute la largeur via colspan. */
.evi-tr .c-text{max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.evi-tr .c-file{max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500;color:var(--heading)}
.evi-tr .c-date{white-space:nowrap;color:var(--muted)}
.evi-tr .c-hash .hash{font-family:var(--font-data);color:var(--muted);font-size:11px}
.evi-tr .c-tlp{white-space:nowrap}
.evi-tr .c-action{text-align:right;white-space:nowrap}
.evi-tr-extra td{padding-top:0}
.evi-tr-extra .msg{margin-top:0}
.meta{display:flex;gap:10px;align-items:center;margin:6px 0;font-size:11px;color:var(--muted)}
.hash{font-family:var(--font-data)}
.actions{margin-top:8px}
.msg{margin-top:8px;color:var(--amber);font-size:12px}
/* Traitement en cours : la pastille « pulse » discrètement pour signaler que le
   statut se met à jour automatiquement (rafraîchissement de fond de la vue). */
.pill.processing{animation:pill-pulse 1.4s var(--ease) infinite}
@keyframes pill-pulse{0%,100%{opacity:1}50%{opacity:.45}}
@media (prefers-reduced-motion: reduce){.pill.processing{animation:none}}
/* Step-up inline (401) */
.stepup{margin-top:8px;padding-top:8px;border-top:1px solid var(--border-2)}
.stepup-lbl{display:block;font-size:11px;color:var(--muted);margin-bottom:5px}
.stepup-row{display:flex;gap:6px}
.otpf{flex:1 1 auto;min-width:0;padding:5px 8px;border:1px solid var(--border);border-radius:var(--r-mini);font-size:13px;background:var(--surface);color:var(--text)}
.btn.slim{padding:5px 10px;font-size:12px;flex:0 0 auto}
/* Hint MFA (403) */
.mfa-hint{color:var(--muted)}
.mfa-link{color:var(--violet);font-weight:600;text-decoration:none;margin-left:4px}
.mfa-link:hover{text-decoration:underline}
</style>
