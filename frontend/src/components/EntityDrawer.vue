<script setup>
import { computed, onMounted } from 'vue'
import DetailDrawer from './DetailDrawer.vue'
import { useRefNames } from '../composables/useRefNames'
import { useOrgNames } from '../composables/useOrgNames'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'

// Drawer de détail générique : rend un enregistrement à partir de son schéma de champs
// (fields.js), en formatant chaque valeur selon son type. Utilisé par EntityTable pour
// offrir un tiroir de détail cohérent sur toutes les entités listées.
const props = defineProps({
  record: { type: Object, required: true },
  fields: { type: Array, required: true },
  title: { type: String, default: 'Détail' },
  subtitle: { type: String, default: '' },
  canEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'edit'])

const { t } = useI18n()
const { fieldLabel, enumLabel } = useLabels()
const { preload, refLabel } = useRefNames()
const { preload: preloadOrgs, orgName } = useOrgNames()

// Catalogues de référentiel utilisés par les champs refpick (pour résoudre les noms).
const CATALOGS = ['attack', 'd3fend', 'cwe', 'owasp', 'capec']
onMounted(() => { preload(CATALOGS); preloadOrgs() })

const TLP_TONE = { RED: 'red', AMBER: 'amber', GREEN: 'green', WHITE: 'gray', CLEAR: 'gray' }
const clientName = (id) => orgName(id)

function isEmpty(v) {
  return v === null || v === undefined || v === '' ||
    (Array.isArray(v) && v.length === 0)
}

// Champs à afficher : ceux du schéma qui ont une valeur (on masque les vides).
const rows = computed(() =>
  props.fields.filter((f) => !isEmpty(props.record[f.key])))

function catalogFor(f) {
  // refpick porte son catalogue ; sinon on devine d'après la clé.
  if (f.catalog) return f.catalog
  const k = f.key
  if (k.includes('techniqu') || k === 'technique_attack') return 'attack'
  if (k.includes('d3fend') || k.includes('mesure')) return 'd3fend'
  if (k === 'cwe') return 'cwe'
  if (k.includes('owasp')) return 'owasp'
  return null
}
</script>

<template>
  <DetailDrawer :title="title" :subtitle="subtitle" wide @close="emit('close')">
    <template v-if="canEdit" #actions>
      <button class="btn slim" @click="emit('edit', record)">{{ t('common.edit') }}</button>
    </template>

    <dl class="dl">
      <template v-for="f in rows" :key="f.key">
        <dt>{{ fieldLabel(f) }}</dt>
        <dd>
          <!-- TLP / PAP : pastille colorée -->
          <span v-if="f.type === 'tlp'" :class="['pill', 'pill-' + (TLP_TONE[record[f.key]] || 'gray')]">
            {{ f.variant === 'pap' ? 'PAP' : 'TLP' }}:{{ record[f.key] }}
          </span>

          <!-- Booléen -->
          <span v-else-if="f.type === 'bool'">{{ record[f.key] ? 'Oui' : 'Non' }}</span>

          <!-- Client : nom résolu -->
          <span v-else-if="f.type === 'client'">{{ clientName(record[f.key]) }}</span>

          <!-- Référentiel (refpick) : chips avec noms résolus -->
          <template v-else-if="f.type === 'refpick'">
            <template v-if="Array.isArray(record[f.key])">
              <span v-for="x in record[f.key]" :key="x" class="chip">{{ refLabel(catalogFor(f), x) }}</span>
            </template>
            <span v-else class="chip">{{ refLabel(catalogFor(f), record[f.key]) }}</span>
          </template>

          <!-- Listes (tags / lines / tableaux) : chips -->
          <template v-else-if="f.type === 'tags' || f.type === 'lines' || Array.isArray(record[f.key])">
            <span v-for="x in record[f.key]" :key="x" class="chip">{{ enumLabel(x) }}</span>
          </template>

          <!-- Texte long -->
          <span v-else-if="f.type === 'textarea'" class="prose">{{ record[f.key] }}</span>

          <!-- Défaut -->
          <span v-else>{{ enumLabel(record[f.key]) }}</span>
        </dd>
      </template>
    </dl>

    <p v-if="!rows.length" class="empty">{{ t('common.none') }}</p>
  </DetailDrawer>
</template>

<style scoped>
.slim{padding:3px 9px;font-size:11.5px}
.dl{display:grid;grid-template-columns:150px 1fr;gap:9px 14px;margin:0;font-size:13px}
.dl dt{color:var(--muted)} .dl dd{margin:0;color:var(--text);word-break:break-word}
.chip{display:inline-block;background:var(--surface-3);border:1px solid var(--border-2);border-radius:var(--r-pill);
  padding:1px 8px;font-size:11.5px;margin:0 4px 4px 0}
.prose{white-space:pre-wrap;line-height:1.5}
.empty{color:var(--faint);font-size:13px}
</style>
