<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, ApiError } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useI18n } from 'vue-i18n'
import RefacSelect from '../components/RefacSelect.vue'

// Administration des comptes. Toutes les actions ici sont à HAUT RISQUE : le
// serveur exige une réauthentification récente (step-up TOTP). Le schéma est
// uniforme : on tente l'action ; si le serveur répond 401 step_up_required, on
// demande un code TOTP, on rejoue /auth/step-up puis l'action en attente.
const { t } = useI18n()
const auth = useAuthStore()

const ROLES = ['admin', 'manager', 'ciso', 'auditeur', 'voc', 'cert', 'operateur']
// Miroir front de matrix.GLOBAL_SCOPE_ROLES — À DES FINS D'AFFICHAGE UNIQUEMENT
// (aucune décision d'autorisation côté client) : sert à expliquer à l'admin ce
// qu'implique un périmètre vide selon le rôle (tous les clients vs aucun accès).
const GLOBAL_SCOPE_ROLES = ['admin', 'manager']

// ── Organisations clientes (pour l'autocomplétion du périmètre) ──────────────
const orgs = ref([])
// Options {id,label} filtrées sur les organisations de rôle « client » (le
// périmètre = les clients servis). Label = « CODE Nom » comme dans EntityForm.
const orgOptions = computed(() =>
  orgs.value
    .filter((o) => o.role === 'client')
    .map((o) => ({ id: o.id, label: `${o.code || ''} ${o.nom}`.trim() })),
)

async function loadOrgs() {
  try {
    const rows = await api.list('organisations')
    orgs.value = Array.isArray(rows) ? rows : (rows.items ?? [])
  } catch (e) {
    orgs.value = []
  }
}

// ── Création ────────────────────────────────────────────────────────────────
const form = ref({ email: '', display_name: '', role: 'auditeur', client_scope: [], password: '' })
const msg = ref(null)

// Message contextuel réactif au rôle choisi : explicite ce qu'implique un
// périmètre VIDE (durcissement fail-closed serveur).
const scopeHint = computed(() =>
  GLOBAL_SCOPE_ROLES.includes(form.value.role)
    ? 'Périmètre vide = accès à tous les clients (rôle multi-clients par nature). Renseignez des clients pour restreindre.'
    : 'Périmètre vide = aucun accès (sécurité « fail-closed »). Sélectionnez les organisations clientes que ce compte doit pouvoir gérer.',
)

// ── Step-up générique ───────────────────────────────────────────────────────
const otp = ref('')
const pendingAction = ref(null) // () => Promise, rejouée après step-up

async function withStepUp(action) {
  msg.value = null
  try {
    await action()
    pendingAction.value = null
    return true
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      pendingAction.value = action
      msg.value = { kind: 'warn', text: t('common.step_up') }
      return false
    }
    msg.value = { kind: 'ko', text: e instanceof ApiError && e.status === 403 ? t('common.forbidden') : e.message }
    return false
  }
}

async function confirmStepUp() {
  try {
    await api.stepUp(otp.value)
    otp.value = ''
    const action = pendingAction.value
    if (action) await withStepUp(action)
  } catch (e) {
    msg.value = { kind: 'ko', text: 'Code TOTP refusé.' }
  }
}

// ── Actions ─────────────────────────────────────────────────────────────────
const users = ref([])
const loading = ref(false)

async function loadUsers() {
  loading.value = true
  try {
    const rows = await api.get('/admin/users')
    // Périmètre éditable par ligne (tableau d'UUID), copié depuis client_scope
    // pour que le RefacSelect puisse le modifier sans muter la valeur d'origine.
    users.value = (rows || []).map((u) => ({ ...u, _scope: [...(u.client_scope || [])] }))
  } catch (e) { users.value = [] }
  finally { loading.value = false }
}

async function createUser() {
  const payload = {
    email: form.value.email,
    display_name: form.value.display_name || null,
    role: form.value.role,
    client_scope: form.value.client_scope, // déjà un tableau d'UUID (RefacSelect)
    password: form.value.password || null,
  }
  const ok = await withStepUp(async () => {
    await api.post('/admin/users', payload)
    msg.value = { kind: 'ok', text: 'Compte créé.' }
    form.value = { email: '', display_name: '', role: 'auditeur', client_scope: [], password: '' }
    await loadUsers()
  })
  return ok
}

async function saveRole(u) {
  await withStepUp(async () => {
    await api.put(`/admin/users/${u.id}/role`, {
      role: u.role,
      client_scope: u._scope, // tableau d'UUID courant (RefacSelect)
    })
    msg.value = { kind: 'ok', text: `Rôle/périmètre de ${u.email} mis à jour (sessions révoquées).` }
    await loadUsers()
  })
}

async function deactivate(u) {
  if (!window.confirm(`Désactiver le compte ${u.email} ? Ses sessions seront révoquées.`)) return
  await withStepUp(async () => {
    await api.post(`/admin/users/${u.id}/deactivate`)
    msg.value = { kind: 'ok', text: `Compte ${u.email} désactivé.` }
    await loadUsers()
  })
}

onMounted(() => { loadUsers(); loadOrgs() })
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.admin.eyebrow') }}</div>
    <h1>{{ t('views.admin.title') }}</h1>

    <div v-if="auth.role !== 'admin'" class="panel warn">
      Réservé au rôle <b>admin</b>. Le serveur refusera toute action ici pour les autres rôles.
    </div>

    <!-- Step-up : demandé par le serveur pour toute action de gestion de comptes -->
    <div v-if="pendingAction" class="panel stepup">
      <b>Réauthentification requise</b> — cette action est à haut risque.
      <div class="row">
        <input class="field otpf" v-model="otp" inputmode="numeric" placeholder="Code TOTP" @keyup.enter="confirmStepUp" />
        <button class="btn btn-primary" @click="confirmStepUp">Confirmer</button>
        <button class="btn" @click="pendingAction = null">Annuler</button>
      </div>
      <p class="hint" v-if="!auth.user?.mfa">
        Votre compte n'a pas encore de TOTP : enrôlez-le d'abord dans « Mon compte ».
      </p>
    </div>

    <p v-if="msg" :class="['msg', msg.kind]">{{ msg.text }}</p>

    <!-- ── Comptes existants ─────────────────────────────────────────────── -->
    <div class="panel">
      <div class="head-row">
        <h3>Comptes</h3>
        <button class="btn" @click="loadUsers">{{ t('common.refresh') }}</button>
      </div>
      <p class="legend">
        <b>Périmètre</b> = organisations clientes visibles par le compte. Vide :
        <b>tous les clients</b> pour admin/manager, <b>aucun accès</b> pour les autres rôles
        (sécurité « fail-closed »).
      </p>
      <p v-if="loading" class="muted">{{ t('common.loading') }}</p>
      <table v-else>
        <thead>
          <tr><th>E-mail</th><th>Rôle</th><th>Périmètre (clients)</th><th>MFA</th><th>SSO</th><th>Statut</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.email }}<div class="sub">{{ u.display_name }}</div></td>
            <td>
              <select class="field slim" v-model="u.role">
                <option v-for="r in ROLES" :key="r" :value="r">{{ r }}</option>
              </select>
            </td>
            <td class="scope-cell">
              <RefacSelect :options="orgOptions" :multiple="true" v-model="u._scope"
                           placeholder="Rechercher un client…" />
              <span v-if="!u._scope.length && !GLOBAL_SCOPE_ROLES.includes(u.role)"
                    class="pill pill-amber warn-scope" title="Périmètre vide : ce rôle ne verra aucun client (fail-closed).">⚠ aucun accès</span>
              <span v-else-if="!u._scope.length" class="muted small">tous (multi-clients)</span>
            </td>
            <td><span :class="['pill', u.mfa_enrolled ? 'pill-green' : 'pill-amber']">{{ u.mfa_enrolled ? 'oui' : 'non' }}</span></td>
            <td><span :class="['pill', u.sso_linked ? 'pill-cyan' : 'pill-gray']">{{ u.sso_linked ? 'lié' : '—' }}</span></td>
            <td><span :class="['pill', u.status === 'active' ? 'pill-green' : 'pill-red']">{{ u.status }}</span></td>
            <td class="actions">
              <button class="btn slim" @click="saveRole(u)">Enregistrer</button>
              <button class="btn slim danger" :disabled="u.status !== 'active'" @click="deactivate(u)">Désactiver</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── Création ──────────────────────────────────────────────────────── -->
    <div class="panel form">
      <h3>Créer un compte</h3>
      <label class="lbl">E-mail</label>
      <input class="field" v-model="form.email" type="email" />
      <label class="lbl">Nom affiché</label>
      <input class="field" v-model="form.display_name" />
      <label class="lbl">{{ t('common.role') }}</label>
      <select class="field" v-model="form.role">
        <option v-for="r in ROLES" :key="r" :value="r">{{ r }}</option>
      </select>
      <label class="lbl">Périmètre client</label>
      <RefacSelect :options="orgOptions" :multiple="true" v-model="form.client_scope"
                   placeholder="Rechercher une organisation cliente…" />
      <p class="hint" :class="{ 'hint-warn': !GLOBAL_SCOPE_ROLES.includes(form.role) }">{{ scopeHint }}</p>
      <label class="lbl">Mot de passe initial (optionnel)</label>
      <input class="field" v-model="form.password" type="password" autocomplete="new-password" />
      <p class="hint">
        Avec mot de passe : connexion locale possible (l'utilisateur enrôle son TOTP au premier
        accès via « Mon compte »). Sans mot de passe : le compte n'est accessible que par SSO —
        créez l'identité dans Keycloak avec le <b>même e-mail</b> ; la liaison se fait
        automatiquement à la première connexion.
      </p>
      <button class="btn btn-primary" style="margin-top:14px" @click="createUser">Créer</button>
    </div>
  </div>
</template>

<style scoped>
.panel{margin-top:14px}
.form{max-width:480px}
.warn{border-left:3px solid var(--amber);color:var(--muted);margin:12px 0}
.stepup{border-left:3px solid var(--violet)}
.stepup .row{display:flex;gap:10px;margin-top:10px}
.otpf{max-width:160px}
.lbl{display:block;margin:12px 0 5px;font-size:12px;color:var(--muted)}
.hint{margin-top:8px;font-size:11px;color:var(--faint)}
.hint-warn{color:var(--amber)}
.legend{margin:8px 0 4px;font-size:11.5px;color:var(--muted)}
.scope-cell{min-width:240px}
.scope-cell .warn-scope{margin-top:6px;display:inline-block}
.small{font-size:11px}
.head-row{display:flex;justify-content:space-between;align-items:center}
.sub{font-size:11px;color:var(--faint)}
.slim{padding:5px 8px;font-size:12px}
.actions{white-space:nowrap;display:flex;gap:6px}
.danger{color:var(--red);border-color:var(--c-red-bd)}
.msg{margin-top:12px;font-size:13px}
.msg.ok{color:var(--green)} .msg.ko{color:var(--red)} .msg.warn{color:var(--amber)}
</style>
