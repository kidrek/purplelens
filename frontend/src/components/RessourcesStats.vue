<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'
import { fieldsFor } from '../fields'
import { api } from '../api/client'

// KPI de la page Ressources. Les agrégats sont calculés côté serveur
// (/analytics/ressources, scopé RLS) et reflètent les filtres du tableau, passés en
// props par RessourcesView. Aucun état de filtre dupliqué ici.
const props = defineProps({
  fOrgs: { type: Array, default: () => [] },
  fTypes: { type: Array, default: () => [] },
  fRoles: { type: Array, default: () => [] },
})

const { t } = useI18n()
const { enumLabel } = useLabels()

const KNOWN_ROLES = (fieldsFor('ressources').find((f) => f.key === 'role')?.options || []).map((r) => r.value)
const SOUS_DOTE_THRESHOLD = 2

const data = ref(null)

async function load() {
  const p = new URLSearchParams()
  props.fOrgs.forEach((v) => p.append('organisation_id', v))
  props.fTypes.forEach((v) => p.append('type', v))
  props.fRoles.forEach((v) => p.append('role', v))
  const qs = p.toString()
  try {
    data.value = await api.get('/analytics/ressources' + (qs ? '?' + qs : ''))
  } catch { /* garder l'affichage précédent en cas d'erreur transitoire */ }
}

// Debounce : les filtres changent par à-coups (chips, RefacSelect) ; coalescer les refetch.
let timer = null
function scheduleLoad() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(load, 250)
}
watch(() => [props.fOrgs, props.fTypes, props.fRoles], scheduleLoad, { deep: true })
onMounted(load)

const pct = (n, d) => (d ? Math.round((n / d) * 100) : 0)

const total = computed(() => data.value?.total || 0)
const byRole = computed(() => data.value?.by_role || {})
const orgs = computed(() => data.value?.organisations || { total: 0, covered: 0 })

const sousDotes = computed(() => KNOWN_ROLES.filter((r) => (byRole.value[r] || 0) <= SOUS_DOTE_THRESHOLD))
const sousDotesText = computed(() => sousDotes.value.map((r) => enumLabel(r)).join(', '))

// Rechargement à la demande du parent (après une mutation du tableau ou clic Rafraîchir).
defineExpose({ reload: load })
</script>

<template>
  <div class="stats">
    <div class="kpis">
      <div class="kpi">
        <div class="klab">{{ t('views.ressources.kpi.ressources') }}</div>
        <div class="kpi-value">{{ total }}</div>
        <div class="kpi-foot">{{ t('views.ressources.kpi.ressources_foot') }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.ressources.kpi.orgs') }}</div>
        <div class="kpi-value">{{ orgs.covered }}<span class="u">/{{ orgs.total }}</span></div>
        <div class="kpi-foot">{{ t('views.ressources.kpi.orgs_foot', { pct: pct(orgs.covered, orgs.total) }) }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.ressources.kpi.renforcer') }}</div>
        <div class="kpi-value" :class="{ warn: sousDotes.length }">{{ sousDotes.length }}</div>
        <div class="kpi-foot">
          {{ sousDotes.length
            ? t('views.ressources.kpi.renforcer_foot', { roles: sousDotesText, seuil: SOUS_DOTE_THRESHOLD })
            : t('views.ressources.kpi.renforcer_ok') }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats{margin:18px 0 14px}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:14px 16px;display:flex;flex-direction:column}
.klab{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;line-height:1.25;color:var(--faint);font-weight:var(--eyebrow-weight);min-height:26px}
.kpi-value{font-family:var(--font-data);font-size:30px;font-weight:600;color:var(--heading);line-height:1.1;height:34px;margin-top:6px}
.kpi-value.warn{color:var(--amber)}
.kpi-value .u{font-size:16px;color:var(--muted);margin-left:3px}
.kpi-foot{font-size:11px;color:var(--muted);margin-top:8px}
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} }
</style>
