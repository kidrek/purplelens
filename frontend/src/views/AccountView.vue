<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, ApiError } from '../api/client'
import { useAuthStore } from '../stores/auth'
const { t } = useI18n()

// « Mon compte » — enrôlement TOTP (D5 : MFA pour les rôles opérationnels).
// Parcours : démarrer → scanner/saisir le secret dans une app d'authentification
// (otpauth://) → confirmer avec un premier code. Le serveur n'active le MFA
// qu'après un code valide : un enrôlement interrompu ne verrouille jamais le compte.
const auth = useAuthStore()
const enroll = ref(null) // { secret, otpauth_uri }
const code = ref('')
const msg = ref(null)
const busy = ref(false)

async function start() {
  busy.value = true; msg.value = null
  try {
    enroll.value = await api.post('/auth/mfa/enroll')
  } catch (e) {
    msg.value = { kind: 'ko', text: e.message }
  } finally { busy.value = false }
}

async function confirm() {
  busy.value = true; msg.value = null
  try {
    await api.post('/auth/mfa/confirm', { totp: code.value })
    await auth.fetchMe()
    enroll.value = null
    code.value = ''
    msg.value = { kind: 'ok', text: 'TOTP activé. Les actions sensibles vous demanderont désormais un code.' }
  } catch (e) {
    msg.value = {
      kind: 'ko',
      text: e instanceof ApiError && e.status === 401 ? 'Code refusé — vérifiez l’heure de votre appareil.' : e.message,
    }
  } finally { busy.value = false }
}
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.account.eyebrow') }}</div>
    <h1>{{ t('views.account.title') }}</h1>

    <div class="panel id">
      <div><b>{{ auth.user?.display_name || auth.user?.email }}</b></div>
      <div class="line">{{ auth.user?.email }} · <span class="pill pill-violet">{{ auth.role }}</span>
        <span :class="['pill', auth.user?.mfa ? 'pill-green' : 'pill-amber']">
          MFA {{ auth.user?.mfa ? 'actif' : 'non enrôlé' }}
        </span>
      </div>
    </div>

    <div class="panel" v-if="!auth.user?.mfa">
      <h3>Activer la double authentification (TOTP)</h3>
      <p class="muted">
        Obligatoire pour les rôles opérationnels et pour les actions sensibles (step-up).
        Utilisez une application d'authentification (FreeOTP, Aegis, Google Authenticator…).
      </p>

      <button v-if="!enroll" class="btn btn-primary" :disabled="busy" @click="start">Démarrer l'enrôlement</button>

      <div v-else class="steps">
        <p><b>1.</b> Ajoutez ce compte dans votre application, par lien ou saisie manuelle :</p>
        <div class="card mono">
          <div class="lbl">Lien (otpauth)</div>
          <div class="wrap">{{ enroll.otpauth_uri }}</div>
          <div class="lbl" style="margin-top:10px">Secret (saisie manuelle)</div>
          <div class="secret">{{ enroll.secret }}</div>
        </div>
        <p class="hint">Ce secret n'est affiché qu'une seule fois — il n'est jamais réaffiché ni journalisé.</p>
        <p><b>2.</b> Saisissez le code affiché par l'application :</p>
        <div class="row">
          <input class="field otpf" v-model="code" inputmode="numeric" placeholder="######" @keyup.enter="confirm" />
          <button class="btn btn-primary" :disabled="busy || code.length < 6" @click="confirm">Confirmer</button>
        </div>
      </div>
    </div>

    <div class="panel" v-else>
      <h3>Double authentification</h3>
      <p class="muted">TOTP actif sur ce compte. En cas de perte de l'appareil, contactez un administrateur.</p>
    </div>

    <p v-if="msg" :class="['msg', msg.kind]">{{ msg.text }}</p>
  </div>
</template>

<style scoped>
.panel{margin-top:14px;max-width:640px}
.id .line{margin-top:4px;color:var(--muted);display:flex;gap:8px;align-items:center}
.mono{font-family:var(--font-data);font-size:12px;margin:10px 0}
.wrap{word-break:break-all}
.secret{font-size:16px;letter-spacing:.12em;color:var(--violet-accent)}
.lbl{font-size:10px;text-transform:uppercase;color:var(--faint)}
.hint{font-size:11px;color:var(--faint)}
.row{display:flex;gap:10px}
.otpf{max-width:140px}
.msg{margin-top:12px;font-size:13px}
.msg.ok{color:var(--green)} .msg.ko{color:var(--red)}
</style>
