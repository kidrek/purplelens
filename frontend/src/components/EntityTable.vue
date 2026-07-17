<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, ApiError } from '../api/client'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'
import { fieldsFor } from '../fields'
import EntityForm from './EntityForm.vue'
import EntityDrawer from './EntityDrawer.vue'
import { useUiStore } from '../stores/ui'
import { useAuthStore } from '../stores/auth'

// Table générique éditable : liste /{entity} et permet créer / éditer / supprimer
// via un formulaire piloté par le schéma (fields.js). Le serveur a déjà filtré les
// lignes (RLS + cloisonnement) ; toute action est revérifiée côté serveur.
const props = defineProps({
  entity: { type: String, required: true },
  columns: { type: Array, required: true },     // [{ key, label, pill?, tlp? }]
  editable: { type: Boolean, default: true },   // false => lecture seule (ex. hors droits)
  allowCreate: { type: Boolean, default: true }, // false => pas de bouton « + Nouveau » (édition/suppr. conservées)
  title: { type: String, default: '' },
  detailRoute: { type: Function, default: null }, // (row) => '/audits/<id>' pour ouvrir un détail
  // Actions personnalisées par ligne : [{ label, fn }] où fn(row) est appelé au clic.
  extraActions: { type: Array, default: () => [] },
  // Drawer sur mesure : composant recevant :record et émettant @close. À défaut,
  // le tiroir générique (EntityDrawer) rend les champs du schéma.
  drawer: { type: [Object, Function], default: null },
})

const { t } = useI18n()
const { fieldLabel, enumLabel } = useLabels()
const ui = useUiStore()
const auth = useAuthStore()
const rows = ref([])
const loading = ref(true)
// Filtre de périmètre client (multi-clients) : n'affiche que les lignes du client actif,
// uniquement pour les entités qui portent un client_id. Données déjà cloisonnées RLS.
const detailRow = ref(null) // enregistrement affiché dans le tiroir de détail

// Sous-titre du drawer : le titre de l'entité (ex. « audit »).
const drawerSubtitle = computed(() => props.title || props.entity)
// Titre : un champ humain de l'enregistrement s'il existe, sinon un libellé générique.
function drawerTitle(r) {
  return r?.nom || r?.titre || r?.code || r?.reference || `${props.title || 'Détail'}`
}

const visibleRows = computed(() => {
  if (!ui.activeClient) return rows.value
  if (!rows.value.length || !('client_id' in rows.value[0])) return rows.value
  return rows.value.filter((r) => r.client_id === ui.activeClient)
})
const error = ref(null)
const formOpen = ref(false)
const editing = ref(null) // record en cours d'édition, ou null pour création

const fields = computed(() => fieldsFor(props.entity))
const canEdit = computed(() => props.editable && fields.value.length > 0)

async function load() {
  loading.value = true
  error.value = null
  try {
    const data = await api.list(props.entity)
    rows.value = Array.isArray(data) ? data : (data?.items ?? [])
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403
      ? t('common.forbidden') : (e.message || 'Erreur')
    rows.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() { editing.value = null; formOpen.value = true }
function openEdit(row) { editing.value = row; formOpen.value = true }

async function onSaved() {
  const wasCreate = editing.value === null
  formOpen.value = false
  editing.value = null
  // Création d'une organisation par un rôle scopé : le serveur vient d'élargir le
  // client_scope du créateur (app_user.client_scope). On rafraîchit la session pour
  // émettre un nouveau token portant ce scope à jour — la nouvelle organisation
  // devient visible sans reconnexion. Non bloquant : à défaut, elle apparaîtra à la
  // prochaine connexion.
  if (wasCreate && props.entity === 'organisations') {
    try {
      await api.refresh()
      await auth.fetchMe()
      // La nouvelle org est désormais dans le scope : recharger la liste des clients
      // pour qu'elle apparaisse tout de suite dans le sélecteur et les autocomplétions.
      await ui.loadClients()
    } catch { /* silencieux : le scope se mettra à jour au prochain login */ }
  }
  await load()
}

async function remove(row) {
  const label = row.nom || row.titre || row.code || row.id
  if (!window.confirm(`Supprimer « ${label} » ? Cette action est journalisée.`)) return
  try {
    await api.remove(props.entity, row.id)
    await load()
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? t('common.forbidden') : e.message
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <div>
    <div class="toolbar">
      <button v-if="canEdit && allowCreate" class="btn btn-primary" @click="openCreate">+ {{ t('common.new') }}</button>
      <button class="btn" @click="load">{{ t('common.refresh') }}</button>
    </div>

    <p v-if="loading" class="muted">{{ t('common.loading') }}</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <p v-else-if="rows.length === 0" class="muted">{{ t('common.empty') }}</p>
    <table v-else>
      <thead>
        <tr>
          <th v-for="c in columns" :key="c.key">{{ fieldLabel({ key: c.key, label: c.label }) }}</th>
          <th class="actions-col"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(r, i) in visibleRows" :key="r.id || i" class="row-clickable" @click="detailRow = r">
          <td v-for="(c, ci) in columns" :key="c.key" :class="{ 'cell-link': ci === 0 }">
            <span v-if="c.pill && r[c.key]" :class="['pill', 'pill-' + (c.pill(r[c.key]) || 'gray')]">{{ enumLabel(r[c.key]) }}</span>
            <span v-else-if="c.tlp && r[c.key]" :class="['tlp', 'tlp-' + r[c.key]]">{{ r[c.key] }}</span>
            <template v-else>{{ r[c.key] != null ? enumLabel(r[c.key]) : '—' }}</template>
          </td>
          <td class="actions" @click.stop>
            <button v-if="!drawer" class="btn slim" @click="detailRow = r">{{ t('common.detail') }}</button>
            <RouterLink v-if="detailRoute && !drawer" class="btn slim" :to="detailRoute(r)">{{ t('common.open') }}</RouterLink>
            <button v-for="a in extraActions" :key="a.label" class="btn slim" @click="a.fn(r)">{{ a.label }}</button>
            <button v-if="canEdit && !drawer" class="btn slim" @click="openEdit(r)">{{ t('common.edit') }}</button>
            <button v-if="canEdit" class="btn slim danger" @click="remove(r)">{{ t('common.delete') }}</button>
          </td>
        </tr>
      </tbody>
    </table>

    <EntityForm
      v-if="formOpen"
      :entity="entity"
      :fields="fields"
      :record="editing"
      :title="(editing ? 'Modifier ' : 'Nouveau ') + (title || entity)"
      @saved="onSaved"
      @close="formOpen = false"
    />
    <component
      v-if="detailRow && drawer"
      :is="drawer"
      :record="detailRow"
      @edit="(r) => { const row = r || detailRow; detailRow = null; openEdit(row) }"
      @saved="() => { detailRow = null; load() }"
      @close="detailRow = null"
    />
    <EntityDrawer
      v-else-if="detailRow"
      :record="detailRow"
      :fields="fields"
      :title="drawerTitle(detailRow)"
      :subtitle="drawerSubtitle"
      :can-edit="canEdit"
      @edit="(r) => { detailRow = null; openEdit(r) }"
      @close="detailRow = null"
    />
  </div>
</template>

<style scoped>
.toolbar{display:flex;justify-content:flex-end;gap:8px;margin-bottom:10px}
.actions-col{width:1%}
.actions{white-space:nowrap;display:flex;gap:6px}
.slim{padding:4px 9px;font-size:12px}
.danger{color:var(--red);border-color:var(--c-red-bd)}
.cell-link{cursor:pointer}
.cell-link:hover{color:var(--violet-accent)}
.row-clickable{cursor:pointer}
.row-clickable:hover td{background:var(--surface-2)}
.row-clickable .cell-link{font-weight:500}
</style>
