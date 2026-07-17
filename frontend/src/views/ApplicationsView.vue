<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'
import { api, ApiError } from '../api/client'
import { useUiStore } from '../stores/ui'
import { useOrgNames } from '../composables/useOrgNames'
import AppDrawer from '../components/AppDrawer.vue'
import EntityForm from '../components/EntityForm.vue'
import { fieldsFor } from '../fields'
const { t } = useI18n()
const { enumLabel } = useLabels()

// Applications du périmètre, avec leur posture : vulnérabilités liées (total / hautes /
// ouvertes) et présence dans un audit. Filtres opérationnels (responsable, stack,
// criticité, exposition, audité). Données agrégées et cloisonnées RLS côté serveur.
const ui = useUiStore()
const { preload: preloadOrgs, orgName } = useOrgNames()
const items = ref([])
const loading = ref(true)
const msg = ref(null)

const q = ref('')
const fCrit = ref('')
const fExpo = ref('')
const fOwner = ref('')
const fStack = ref('')
const fAudit = ref('')
const showAdvanced = ref(false)
const activeAdvancedCount = computed(() =>
  [fCrit.value, fExpo.value, fOwner.value, fStack.value, fAudit.value].filter(Boolean).length)

const detailFor = ref(null)
const showForm = ref(false)
const editRecord = ref(null)
const editBusy = ref(null)

const CRIT_TONE = { critique: 'red', haute: 'amber', elevee: 'amber', moyenne: 'cyan', basse: 'green' }

async function load() {
  loading.value = true
  try { items.value = (await api.get('/analytics/applications-coverage' + (ui.clientQuery ? '?' + ui.clientQuery : ''))).items }
  catch (e) { msg.value = e instanceof ApiError && e.status === 403 ? 'Accès refusé.' : (e.message || 'Erreur.') }
  finally { loading.value = false }
}

const owners = computed(() => [...new Set(items.value.map((a) => a.contact_metier).filter(Boolean))].sort())
const filtered = computed(() => items.value.filter((a) => {
  if (fCrit.value && String(a.criticite).toLowerCase() !== fCrit.value) return false
  if (fExpo.value && a.exposition !== fExpo.value) return false
  if (fOwner.value && a.contact_metier !== fOwner.value) return false
  if (fStack.value && !String(a.stack || '').toLowerCase().includes(fStack.value.toLowerCase())) return false
  if (fAudit.value === 'yes' && !a.audited) return false
  if (fAudit.value === 'no' && a.audited) return false
  if (q.value) {
    const h = `${a.nom} ${a.code || ''}`.toLowerCase()
    if (!h.includes(q.value.toLowerCase())) return false
  }
  return true
}))

const expositions = computed(() => [...new Set(items.value.map((a) => a.exposition).filter(Boolean))].sort())
const kpiAudited = computed(() => items.value.filter((a) => a.audited).length)
const kpiWithVulns = computed(() => items.value.filter((a) => a.vuln_open > 0).length)
const critTone = (c) => CRIT_TONE[String(c).toLowerCase()] || 'gray'

watch(() => ui.activeClient, load)
onMounted(() => { load(); preloadOrgs() }) // chargement initial (+ noms d'organisations)

async function remove(a) {
  if (!window.confirm(`Supprimer l’application « ${a.nom} » ? Cette action est journalisée.`)) return
  try {
    await api.remove('applications', a.id)
    if (detailFor.value?.id === a.id) detailFor.value = null
    await load()
  } catch (e) {
    // Le serveur décide (matrice RBAC) : un rôle sans droit S reçoit un 403.
    msg.value = e instanceof ApiError && e.status === 403 ? 'Accès refusé.' : (e.message || 'Erreur.')
  }
}
function openNew() { editRecord.value = null; showForm.value = true }
async function openEdit(a) {
  detailFor.value = null
  editBusy.value = a.id
  try {
    editRecord.value = await api.get(`/applications/${a.id}`)
  } catch (e) {
    msg.value = e instanceof ApiError && e.status === 403 ? 'Accès refusé.' : (e.message || 'Erreur.')
    editBusy.value = null
    return
  }
  editBusy.value = null
  showForm.value = true
}
function onSaved() { showForm.value = false; load() }
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.applications.eyebrow') }}</div>
    <h1>{{ t('views.applications.title') }}</h1>
    <p v-if="msg" class="err">{{ msg }}</p>

    <div class="mini-kpis">
      <div class="mk"><b>{{ items.length }}</b> {{ t('av.apps') }}</div>
      <div class="mk"><b>{{ kpiAudited }}</b> {{ t('av.audited') }}</div>
      <div class="mk amber"><b>{{ kpiWithVulns }}</b> {{ t('av.with_open_vulns') }}</div>
    </div>

    <div class="filters">
      <input class="field grow" v-model="q" :placeholder="t('av.search')" />
      <button class="btn slim" @click="showAdvanced = !showAdvanced">
        {{ showAdvanced ? 'Masquer les filtres avancés' : 'Filtres avancés' }}
        <span v-if="activeAdvancedCount" class="badge-count">{{ activeAdvancedCount }}</span>
      </button>
      <button class="btn btn-primary" @click="openNew">+ {{ t('av.new_f') }}</button>
    </div>
    <div v-if="showAdvanced" class="filters adv">
      <select class="field" v-model="fCrit"><option value="">{{ t('av.criticality') }}</option><option value="critique">{{ t('enum.critique') }}</option><option value="haute">{{ t('enum.haute') }}</option><option value="moyenne">{{ t('enum.moyenne') }}</option><option value="basse">{{ enumLabel('basse') }}</option></select>
      <select class="field" v-model="fExpo"><option value="">{{ t('av.exposure') }}</option><option v-for="e in expositions" :key="e" :value="e">{{ e }}</option></select>
      <select class="field" v-model="fOwner"><option value="">{{ t('av.owner') }}</option><option v-for="o in owners" :key="o" :value="o">{{ o }}</option></select>
      <input class="field slim" v-model="fStack" :placeholder="t('av.stack')" />
      <select class="field" v-model="fAudit"><option value="">{{ t('av.audit') }}</option><option value="yes">{{ t('av.audited_opt') }}</option><option value="no">{{ t('av.not_audited') }}</option></select>
    </div>

    <p v-if="loading" class="muted">{{ t('common.loading') }}</p>
    <p v-else-if="!filtered.length" class="muted">{{ t('av.none_match') }}</p>

    <table v-else class="atable">
      <thead><tr>
        <th>{{ t('fields.nom') }}</th><th>{{ t('fields.code') }}</th><th>{{ t('fields.client_id') }}</th><th>{{ t('fields.criticite') }}</th><th>{{ t('fields.exposition') }}</th><th>{{ t('fields.contact_metier') }}</th>
        <th>{{ t('av.col_vulns') }}</th><th>{{ t('av.audit') }}</th><th></th>
      </tr></thead>
      <tbody>
        <tr v-for="a in filtered" :key="a.id" class="row-clickable" @click="detailFor = a">
          <td class="nom link">{{ a.nom }}</td>
          <td class="mono">{{ a.code || '—' }}</td>
          <td class="sm">{{ orgName(a.client_id) || '—' }}</td>
          <td><span :class="['pill', 'pill-' + critTone(a.criticite)]">{{ a.criticite || '—' }}</span></td>
          <td class="sm">{{ a.exposition || '—' }}</td>
          <td class="sm">{{ a.contact_metier || '—' }}</td>
          <td>
            <span v-if="a.vuln_total" class="vulns">
              <span class="v-tot">{{ a.vuln_total }}</span>
              <span v-if="a.vuln_high" class="v-high" title="Hautes/critiques">{{ a.vuln_high }}⚠</span>
              <span v-if="a.vuln_open" class="v-open" title="Ouvertes">{{ a.vuln_open }} ouv.</span>
            </span>
            <span v-else class="faint">—</span>
          </td>
          <td><span v-if="a.audited" class="pill pill-green">{{ t('av.is_audited') }}</span><span v-else class="faint">{{ t('av.not') }}</span></td>
          <td class="ta" @click.stop>
            <button class="btn slim" @click="detailFor = a">{{ t('common.detail') }}</button>
            <button class="btn slim" :disabled="editBusy === a.id" @click="openEdit(a)">{{ editBusy === a.id ? '…' : t('common.edit') }}</button>
            <button class="btn slim danger" @click="remove(a)">{{ t('common.delete') }}</button>
          </td>
        </tr>
      </tbody>
    </table>

    <AppDrawer v-if="detailFor" :app="detailFor" @close="detailFor = null" @edit="openEdit" />
    <EntityForm v-if="showForm" entity="applications" :fields="fieldsFor('applications')"
      :record="editRecord" :title="editRecord ? 'Modifier l’application' : 'Nouvelle application'"
      @saved="onSaved" @close="showForm = false" />
  </div>
</template>

<style scoped>
.sm{font-size:12px} .mono{font-family:var(--font-data);font-size:12px}
.mini-kpis{display:flex;gap:16px;margin:10px 0;font-size:12.5px;color:var(--muted)}
.mk b{font-family:var(--font-data);font-size:16px;color:var(--heading);margin-right:4px}
.mk.amber b{color:var(--amber)}
.filters{display:flex;gap:8px;align-items:center;margin:10px 0 14px;flex-wrap:wrap}
.filters.adv{margin-top:-6px}
.grow{flex:1;min-width:160px} .slim{max-width:120px}
.badge-count{display:inline-flex;align-items:center;justify-content:center;min-width:16px;height:16px;
  border-radius:99px;background:var(--violet);color:#fff;font-size:10px;margin-left:5px;padding:0 4px}
.row-clickable{cursor:pointer}
.row-clickable:hover td{background:var(--surface-2)}
.atable{width:100%;border-collapse:collapse}
.atable th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--faint);padding:8px 8px;border-bottom:1px solid var(--border)}
.atable td{padding:8px 8px;border-bottom:1px solid var(--border-2);font-size:12.5px}
.atable .nom{font-weight:600;color:var(--heading)}
.atable .nom.link{cursor:pointer}
.atable .nom.link:hover{color:var(--violet-accent);text-decoration:underline}
.vulns{display:inline-flex;gap:6px;align-items:center;font-family:var(--font-data);font-size:11.5px}
.v-tot{color:var(--heading);font-weight:600}
.v-high{color:var(--red)} .v-open{color:var(--amber)}
.ta{text-align:right;white-space:nowrap} .ta .slim{margin-left:4px;padding:3px 8px;font-size:11.5px}
.ta .danger{color:var(--red);border-color:var(--c-red-bd)}
</style>
