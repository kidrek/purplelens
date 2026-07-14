<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import EntityTable from '../components/EntityTable.vue'
import ScenarioDrawer from '../components/ScenarioDrawer.vue'
import { api, ApiError } from '../api/client'
const { t } = useI18n()

const cols = [
  { key: 'reference', label: 'Référence' },
  { key: 'nom', label: 'Nom' },
  { key: 'acteur_emule', label: 'Acteur émulé' },
  { key: 'type_engagement', label: 'Engagement' },
  { key: 'sophistication', label: 'Sophistication' },
  { key: 'credibilite', label: 'Crédibilité' },
  { key: 'tlp', label: 'TLP', tlp: true },
]
const msg = ref(null)

// Déclenche un téléchargement de fichier à partir d'un objet JSON (bundle STIX).
function downloadJson(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

async function exportOne(row) {
  msg.value = null
  try {
    const bundle = await api.get(`/stix/scenarios/${row.id}`)
    downloadJson(bundle, `scenario-${row.id}.stix.json`)
  } catch (e) {
    msg.value = e instanceof ApiError && e.status === 403 ? 'Export refusé.' : (e.message || 'Erreur.')
  }
}

async function exportAll() {
  msg.value = null
  try {
    const bundle = await api.get('/stix/scenarios')
    downloadJson(bundle, 'scenarios.stix.json')
  } catch (e) {
    msg.value = e instanceof ApiError && e.status === 403 ? 'Export refusé.' : (e.message || 'Erreur.')
  }
}

const importBusy = ref(false)
const reloadKey = ref(0)

// Import d'un bundle STIX 2.1 -> crée un/des scénario(s) dans la bibliothèque.
async function onStixImport(ev) {
  const file = ev.target.files?.[0]
  if (!file) return
  importBusy.value = true; msg.value = null
  try {
    const bundle = JSON.parse(await file.text())
    const r = await api.post('/stix/import', { bundle })
    msg.value = { ok: true, text: `${r.imported} scénario(s) importé(s) depuis STIX.` }
    reloadKey.value++ // force le rechargement de la table
  } catch (e) {
    const txt = e instanceof ApiError
      ? (e.status === 403 ? 'Import refusé (droit de création requis).'
        : e.status === 400 ? 'Bundle STIX invalide.' : (e.message || 'Erreur.'))
      : 'Fichier JSON invalide.'
    msg.value = { ok: false, text: txt }
  } finally {
    importBusy.value = false; ev.target.value = ''
  }
}

const stixAction = [
  { label: 'STIX', fn: exportOne },
]
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.scenarios.eyebrow') }}</div>
    <h1>{{ t('views.scenarios.title') }}</h1>
    <div class="head">
      <p class="muted">Bibliothèque transverse (hors cloisonnement client). Export au format STIX 2.1.</p>
      <div class="actions">
        <label class="btn" :class="{ disabled: importBusy }">
          {{ importBusy ? 'Import…' : 'Importer (STIX)' }}
          <input type="file" accept="application/json,.json" @change="onStixImport" hidden :disabled="importBusy" />
        </label>
        <button class="btn" @click="exportAll">Exporter tout (STIX)</button>
      </div>
    </div>
    <p v-if="msg" :class="typeof msg === 'object' ? (msg.ok ? 'ok' : 'err') : 'err'">
      {{ typeof msg === 'object' ? msg.text : msg }}
    </p>
    <EntityTable :key="reloadKey" entity="scenarios" :columns="cols" title="scénario"
                 :extra-actions="stixAction" :drawer="ScenarioDrawer" />
  </div>
</template>

<style scoped>
.head{display:flex;justify-content:space-between;align-items:center;gap:12px}
.err{color:var(--red);font-size:13px}
.ok{color:var(--green);font-size:13px}
.actions{display:flex;gap:8px;align-items:center}
.btn.disabled{opacity:.6;pointer-events:none}
</style>
