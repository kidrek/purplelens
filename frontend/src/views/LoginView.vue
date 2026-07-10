<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api, ApiError } from '../api/client'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const otp = ref('')
const error = ref(null)
const busy = ref(false)

async function submit() {
  busy.value = true; error.value = null
  try {
    await auth.login(email.value, password.value, otp.value || undefined)
    router.replace(route.query.r || '/')
  } catch (e) {
    error.value = e instanceof ApiError ? t('login.failed') : e.message
  } finally {
    busy.value = false
  }
}

async function sso() {
  const r = await api.oidcStart()
  if (r?.authorization_url) window.location.assign(r.authorization_url)
}
</script>

<template>
  <div class="wrap">
    <div class="panel card-login">
      <div class="brand"><span class="dot"></span> {{ t('app.title') }}</div>
      <h2>{{ t('login.heading') }}</h2>

      <label class="lbl">{{ t('login.email') }}</label>
      <input class="field" v-model="email" type="email" autocomplete="username" />

      <label class="lbl">{{ t('login.password') }}</label>
      <input class="field" v-model="password" type="password" autocomplete="current-password" @keyup.enter="submit" />

      <label class="lbl">{{ t('login.otp') }}</label>
      <input class="field" v-model="otp" inputmode="numeric" placeholder="######" @keyup.enter="submit" />

      <p v-if="error" class="err">{{ error }}</p>

      <button class="btn btn-primary full" :disabled="busy" @click="submit">{{ t('login.submit') }}</button>
      <div class="sep"></div>
      <button class="btn full" @click="sso">{{ t('login.sso') }}</button>
    </div>
  </div>
</template>

<style scoped>
.wrap{height:100%;display:grid;place-items:center;background:var(--bg)}
.card-login{width:340px}
.brand{display:flex;align-items:center;gap:9px;color:var(--muted);font-family:var(--font-display);margin-bottom:6px}
.brand .dot{width:10px;height:10px;border-radius:50%;background:var(--violet);box-shadow:0 0 12px var(--violet)}
.lbl{display:block;margin:12px 0 5px;font-size:12px;color:var(--muted)}
.full{width:100%;margin-top:14px}
.sep{height:1px;background:var(--border);margin:16px 0 2px}
.err{color:var(--red);margin-top:10px;font-size:13px}
</style>
