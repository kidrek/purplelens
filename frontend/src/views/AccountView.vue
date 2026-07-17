<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, ApiError } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { fieldsFor } from '../fields'
import EntityForm from '../components/EntityForm.vue'
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

// ── « Ma fiche » ────────────────────────────────────────────────────────────
// Fiche ressource (type humaine) liée au compte : sans elle, un compte autonome
// (operateur/auditeur) ne peut se sélectionner comme auditeur d'un audit (le picker
// liste des ressources). On réutilise le formulaire ressource générique, avec une
// soumission redirigée vers /profile/resource (pose type='humaine' + app_user_id).
const ressourceFields = fieldsFor('ressources')
const fiches = ref([])       // mes fiches liées [{ id, organisation_id, nom, ... }]
const orgs = ref([])         // organisations de mon périmètre [{ id, code, nom }]
const pickedOrg = ref('')    // organisation choisie pour une nouvelle fiche
const formOpen = ref(false)
const editing = ref(null)    // fiche en édition, ou null (création)

async function loadFiches() {
  try {
    fiches.value = (await api.myResources()).resources || []
    const rows = await api.list('organisations')
    orgs.value = Array.isArray(rows) ? rows : (rows.items ?? [])
  } catch { /* périmètre vide ou hors-ligne : panneau simplement vide */ }
}
onMounted(loadFiches)

function orgLabel(id) {
  const o = orgs.value.find((x) => x.id === id)
  return o ? `${o.code || ''} ${o.nom}`.trim() : id
}
// Organisations de mon périmètre sans fiche liée (candidates à la création).
const orgsSansFiche = computed(() => {
  const done = new Set(fiches.value.map((f) => f.organisation_id))
  return orgs.value.filter((o) => !done.has(o.id))
})
// Valeurs imposées / pré-remplies selon création vs édition.
const fichePrefill = computed(() => editing.value
  ? { organisation_id: editing.value.organisation_id, type: 'humaine' }
  : { organisation_id: pickedOrg.value, type: 'humaine',
      nom: auth.user?.display_name || '', role: 'auditeur' })

function openCreate() {
  if (!pickedOrg.value) return
  editing.value = null
  formOpen.value = true
}
function openEdit(f) {
  editing.value = f
  formOpen.value = true
}
function saveFiche(payload) { return api.saveMyResource(payload) }
function onFicheSaved() {
  formOpen.value = false
  pickedOrg.value = ''
  loadFiches()
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

    <div class="panel">
      <h3>Ma fiche auditeur</h3>
      <p class="muted">
        Déclarez-vous comme ressource d'une organisation de votre périmètre pour pouvoir
        vous sélectionner comme auditeur de ses audits. Vos compétences alimentent la
        lettre d'engagement.
      </p>

      <ul v-if="fiches.length" class="fiches">
        <li v-for="f in fiches" :key="f.id">
          <div class="f-main">
            <b>{{ f.nom }}</b>
            <span v-if="f.role" class="pill pill-violet">{{ f.role }}</span>
            <span class="org">{{ orgLabel(f.organisation_id) }}</span>
          </div>
          <div v-if="(f.competences || []).length" class="f-comp">{{ (f.competences || []).join(' · ') }}</div>
          <button class="btn" @click="openEdit(f)">Modifier</button>
        </li>
      </ul>
      <p v-else class="muted small">Aucune fiche pour l'instant.</p>

      <div v-if="orgsSansFiche.length" class="row create">
        <select class="field" v-model="pickedOrg">
          <option value="">Choisir une organisation…</option>
          <option v-for="o in orgsSansFiche" :key="o.id" :value="o.id">{{ `${o.code || ''} ${o.nom}`.trim() }}</option>
        </select>
        <button class="btn btn-primary" :disabled="!pickedOrg" @click="openCreate">Créer ma fiche</button>
      </div>
    </div>

    <EntityForm
      v-if="formOpen"
      entity="ressources"
      :fields="ressourceFields"
      :record="editing"
      :title="editing ? 'Modifier ma fiche' : 'Créer ma fiche'"
      :prefill="fichePrefill"
      :hidden="['organisation_id', 'type']"
      :submit-override="saveFiche"
      @saved="onFicheSaved"
      @close="formOpen = false"
    />
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
.small{font-size:12px}
.fiches{list-style:none;padding:0;margin:12px 0;display:flex;flex-direction:column;gap:8px}
.fiches li{border:1px solid var(--border);border-radius:var(--r-mini);padding:8px 10px;
  display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.f-main{display:flex;align-items:center;gap:8px;flex:1;min-width:0}
.f-main .org{color:var(--muted);font-size:12px}
.f-comp{flex-basis:100%;color:var(--faint);font-size:11px}
.row.create{display:flex;gap:10px;margin-top:10px}
.row.create .field{max-width:320px}
</style>
