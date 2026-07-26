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
import { useOrgNames } from '../composables/useOrgNames'
import { useAppNames } from '../composables/useAppNames'

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
  // Style des actions de ligne : 'text' (défaut, boutons libellés) ou 'icon'
  // (boutons-icône crayon/corbeille, sans bouton « Détail » — le clic sur la ligne
  // ouvre déjà le tiroir de lecture).
  actionVariant: { type: String, default: 'text' },
  // Prédicat de filtrage client-side supplémentaire : (row) => boolean. Appliqué
  // après le périmètre client actif. null => aucun filtre additionnel.
  filterFn: { type: Function, default: null },
  // false => masque la toolbar interne (+ Nouveau / Rafraîchir) : le parent rend ces
  // actions ailleurs et pilote via les méthodes exposées (openCreate / load).
  showToolbar: { type: Boolean, default: true },
})

// Émis après une mutation réussie (création / édition / suppression) une fois le tableau
// rechargé. Permet au parent de rafraîchir une section connexe (ex. KPI) découplée du
// tableau. Émis uniquement sur mutation, jamais au montage, pour éviter un double-fetch.
const emit = defineEmits(['changed'])

const { t, te, locale } = useI18n()
const { fieldLabel, enumLabel } = useLabels()
const ui = useUiStore()
const auth = useAuthStore()
// Résolution organisation_id -> nom pour les colonnes marquées { org: true }.
const { preload: preloadOrgs, orgName } = useOrgNames()
// Résolution application_id -> nom pour les colonnes marquées { apps: true } (uuid[]).
const { preload: preloadApps, appName } = useAppNames()
// Une colonne peut forcer l'en-tête via une clé i18n `th` (ex. « Organisation » pour
// client_id, dont fields.client_id vaut « Client »). Repli sur fieldLabel sinon.
function colHeader(c) {
  if (c.th && te(c.th)) return t(c.th)
  return fieldLabel({ key: c.key, label: c.label })
}
// Formatage d'une valeur de date en JJ/MM/AAAA (colonnes { date: true }). Repli sur la
// chaîne brute si non parsable, pour ne jamais masquer une donnée.
function fmtDateCell(v) {
  if (!v) return '—'
  const s = String(v).slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  return m ? `${m[3]}/${m[2]}/${m[1]}` : s
}
// Formatage horodatage (colonnes { datetime: true }) : date + heure + fuseau local
// (ex. « 24/07/2026 14:32 (UTC+2) »), pour tracer précisément une création.
function fmtDateTimeCell(v) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  const loc = locale.value === 'en' ? 'en-GB' : 'fr-FR'
  const date = d.toLocaleDateString(loc, { day: '2-digit', month: '2-digit', year: 'numeric' })
  const time = d.toLocaleTimeString(loc, { hour: '2-digit', minute: '2-digit' })
  const off = -d.getTimezoneOffset() / 60
  const tz = `UTC${off >= 0 ? '+' : ''}${off}`
  return `${date} ${time} (${tz})`
}
// Valeur brute (r[key]) vs valeur d'affichage : une colonne peut fournir un accesseur
// `get(row)` (colonne dérivée d'une autre entité) et/ou un `format(rawValue)`.
function cellRaw(c, r) { return r[c.key] }
function cellText(c, r) {
  const raw = r[c.key]
  if (c.format) return c.format(raw)
  if (c.get) { const g = c.get(r); return g == null || g === '' ? '—' : g }
  return raw != null ? enumLabel(raw) : '—'
}
const hasAppsCol = computed(() => props.columns.some((c) => c.apps))
const rows = ref([])
const loading = ref(true)
// Filtre de périmètre client (multi-clients) : n'affiche que les lignes du client actif,
// uniquement pour les entités qui portent un client_id. Données déjà cloisonnées RLS.
const detailRow = ref(null) // enregistrement affiché dans le tiroir de détail
// Édition lancée DEPUIS un drawer : porte l'id à rouvrir dans le drawer après sauvegarde
// (sinon null → retour à la liste, comme pour l'édition via les boutons de ligne).
const reopenAfterSave = ref(null)

// Sous-titre du drawer : le titre de l'entité (ex. « audit »).
const drawerSubtitle = computed(() => props.title || props.entity)
// Titre : un champ humain de l'enregistrement s'il existe, sinon un libellé générique.
function drawerTitle(r) {
  return r?.nom || r?.titre || r?.code || r?.reference || `${props.title || 'Détail'}`
}

const visibleRows = computed(() => {
  let out = rows.value
  if (ui.activeClient && out.length && 'client_id' in out[0]) {
    out = out.filter((r) => r.client_id === ui.activeClient)
  }
  if (props.filterFn) out = out.filter((r) => props.filterFn(r))
  return out
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

// Par défaut, aucune réouverture de drawer : seul le handler @edit d'un drawer réarme le
// drapeau APRÈS avoir appelé openEdit (les boutons de ligne passent aussi par openEdit).
function openCreate() { editing.value = null; formOpen.value = true; reopenAfterSave.value = null }
function openEdit(row) { editing.value = row; formOpen.value = true; reopenAfterSave.value = null }
// Ouvre le tiroir de lecture sur une ligne (identique au clic sur la ligne) : permet à
// un parent d'exposer une action « Voir » dédiée qui ouvre le même tiroir interne.
function openDetail(row) { detailRow.value = row }

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
  emit('changed')
  // Édition lancée depuis un drawer : rouvrir ce drawer sur l'enregistrement rechargé
  // (détruit puis remonté → son onMounted refait api.get et affiche les données à jour).
  // Repli gracieux sur la liste si l'id n'est plus présent (ex. sorti du périmètre).
  if (reopenAfterSave.value) {
    const id = reopenAfterSave.value
    reopenAfterSave.value = null
    detailRow.value = rows.value.find((r) => r.id === id) || null
  }
}

async function remove(row) {
  const label = row.nom || row.titre || row.code || row.id
  if (!window.confirm(`Supprimer « ${label} » ? Cette action est journalisée.`)) return
  try {
    await api.remove(props.entity, row.id)
    await load()
    emit('changed')
  } catch (e) {
    error.value = e instanceof ApiError && e.status === 403 ? t('common.forbidden') : e.message
  }
}

onMounted(() => { load(); preloadOrgs(); if (hasAppsCol.value) preloadApps() })
// `rows` exposé : permet au parent de dériver options de filtres et KPI des lignes
// déjà chargées (calcul client-side), sans second appel API.
defineExpose({ load, openCreate, openDetail, rows })
</script>

<template>
  <div>
    <div v-if="showToolbar" class="toolbar">
      <button v-if="canEdit && allowCreate" class="btn btn-primary" @click="openCreate">+ {{ t('common.new') }}</button>
      <button class="btn" @click="load">{{ t('common.refresh') }}</button>
    </div>

    <!-- Emplacement optionnel pour un panneau de filtres propre à la vue. -->
    <slot name="filters" />

    <p v-if="loading" class="muted">{{ t('common.loading') }}</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <p v-else-if="rows.length === 0" class="muted">{{ t('common.empty') }}</p>
    <table v-else>
      <thead>
        <tr>
          <th v-for="c in columns" :key="c.key" :class="{ 'col-center': c.center }">{{ colHeader(c) }}</th>
          <th class="actions-col"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(r, i) in visibleRows" :key="r.id || i" class="row-clickable" @click="detailRow = r">
          <td v-for="(c, ci) in columns" :key="c.key" :class="{ 'cell-link': ci === 0, 'col-upper': c.upper, 'col-center': c.center }">
            <span v-if="c.pill && cellRaw(c, r) != null" :class="['pill', 'pill-' + (c.pill(cellRaw(c, r)) || 'gray')]">{{ cellText(c, r) }}</span>
            <span v-else-if="c.tlp && r[c.key]" :class="['tlp', 'tlp-' + r[c.key]]">{{ r[c.key] }}</span>
            <template v-else-if="c.org">{{ r[c.key] ? orgName(r[c.key]) : '—' }}</template>
            <template v-else-if="c.apps">
              <template v-if="Array.isArray(r[c.key]) && r[c.key].length">
                {{ appName(r[c.key][0]) }}<span v-if="r[c.key].length > 1" class="plusn">+{{ r[c.key].length - 1 }}</span>
              </template>
              <template v-else>—</template>
            </template>
            <template v-else-if="c.datetime">{{ fmtDateTimeCell(r[c.key]) }}</template>
            <template v-else-if="c.date">{{ fmtDateCell(r[c.key]) }}</template>
            <template v-else>{{ cellText(c, r) }}</template>
            <span v-if="c.badge && c.badge(r)" class="plusn">{{ c.badge(r) }}</span>
          </td>
          <!-- Variant boutons-icône : actions extra (icône `export` ou libellé), édition, suppression
               (le clic sur la ligne ouvre le tiroir). -->
          <td v-if="actionVariant === 'icon'" class="actions" @click.stop>
            <button v-for="a in extraActions" :key="a.label" class="icon-btn-sm" :title="a.label" :aria-label="a.label" @click="a.fn(r)">
              <svg v-if="a.icon === 'export'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/><path d="M12 3v12"/><path d="m8 7 4-4 4 4"/></svg>
              <svg v-else-if="a.icon === 'download'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/><path d="M12 3v12"/><path d="m8 11 4 4 4-4"/></svg>
              <svg v-else-if="a.icon === 'view'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
              <span v-else class="xa-label">{{ a.label }}</span>
            </button>
            <button v-if="canEdit" class="icon-btn-sm" :title="t('common.edit')" @click="openEdit(r)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
            </button>
            <button v-if="canEdit" class="icon-btn-sm danger" :title="t('common.delete')" @click="remove(r)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
            </button>
          </td>
          <td v-else class="actions" @click.stop>
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
      @close="() => { formOpen = false; reopenAfterSave = null }"
    />
    <component
      v-if="detailRow && drawer"
      :is="drawer"
      :record="detailRow"
      @edit="(r) => { const row = r || detailRow; detailRow = null; openEdit(row); reopenAfterSave = row?.id }"
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
      @edit="(r) => { detailRow = null; openEdit(r); reopenAfterSave = r?.id }"
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
.icon-btn-sm{border:1px solid var(--border);background:var(--surface);color:var(--muted);
  border-radius:var(--r-mini);width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;cursor:pointer}
.icon-btn-sm:hover{border-color:var(--violet-accent);color:var(--violet-accent)}
.icon-btn-sm.danger:hover{border-color:var(--red);color:var(--red)}
.icon-btn-sm:disabled{opacity:.5;cursor:not-allowed}
.icon-btn-sm .xa-label{font-size:10px;font-weight:600;letter-spacing:.02em}
.cell-link{cursor:pointer}
.cell-link:hover{color:var(--violet-accent)}
.col-upper{text-transform:uppercase}
.col-center{text-align:center}
.plusn{display:inline-block;margin-left:6px;background:var(--surface-3);border:1px solid var(--border);
  color:var(--muted);border-radius:99px;font-size:10px;font-family:var(--font-data);padding:1px 6px;vertical-align:1px}
.row-clickable{cursor:pointer}
.row-clickable:hover td{background:var(--surface-2)}
.row-clickable .cell-link{font-weight:500}
</style>
