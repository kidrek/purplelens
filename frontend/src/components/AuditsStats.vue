<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'

// KPI de la page Audits. Les agrégats sont calculés côté serveur (/analytics/audits,
// scopé RLS) et reflètent les filtres du tableau, passés en props par AuditsView.
// Aucun état de filtre dupliqué ici — même contrat que RessourcesStats.
const props = defineProps({
  fOrgs: { type: Array, default: () => [] },
  fApps: { type: Array, default: () => [] },
  fCats: { type: Array, default: () => [] },
  fStatuts: { type: Array, default: () => [] },
  fTypes: { type: Array, default: () => [] },
  fPrios: { type: Array, default: () => [] },
  fTlp: { type: Array, default: () => [] },
})

const { t } = useI18n()

const data = ref(null)

async function load() {
  const p = new URLSearchParams()
  props.fOrgs.forEach((v) => p.append('organisation_id', v))
  props.fApps.forEach((v) => p.append('application', v))
  props.fCats.forEach((v) => p.append('categorie', v))
  props.fStatuts.forEach((v) => p.append('statut', v))
  props.fTypes.forEach((v) => p.append('type', v))
  props.fPrios.forEach((v) => p.append('priorite', v))
  props.fTlp.forEach((v) => p.append('tlp', v))
  const qs = p.toString()
  try {
    data.value = await api.get('/analytics/audits' + (qs ? '?' + qs : ''))
  } catch { /* garder l'affichage précédent en cas d'erreur transitoire */ }
}

// Debounce : les filtres changent par à-coups (chips, RefacSelect) ; coalescer les refetch.
let timer = null
function scheduleLoad() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(load, 250)
}
watch(
  () => [props.fOrgs, props.fApps, props.fCats, props.fStatuts, props.fTypes, props.fPrios, props.fTlp],
  scheduleLoad, { deep: true },
)
onMounted(load)

const round = (n) => Math.round(n)
const pct = (n, d) => (d ? round((n / d) * 100) : 0)

const total = computed(() => data.value?.total || 0)
const byStatut = computed(() => data.value?.by_statut || {})
const byPriorite = computed(() => data.value?.by_priorite || {})
const orgs = computed(() => data.value?.organisations || { total: 0, covered: 0 })

const enCours = computed(() => byStatut.value.en_cours || 0)
const planifies = computed(() => byStatut.value.planifie || 0)
const p1 = computed(() => byPriorite.value.P1 || 0)

// Rechargement à la demande du parent (après une mutation du tableau ou clic Rafraîchir).
defineExpose({ reload: load })
</script>

<template>
  <div class="stats">
    <div class="kpis">
      <div class="kpi">
        <div class="klab">{{ t('views.audits.kpi.audits') }}</div>
        <div class="kpi-value">{{ total }}</div>
        <div class="kpi-foot">{{ t('views.audits.kpi.audits_foot', { covered: orgs.covered, total: orgs.total }) }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.audits.kpi.en_cours') }}</div>
        <div class="kpi-value">{{ enCours }}</div>
        <div class="kpi-foot">{{ t('views.audits.kpi.en_cours_foot', { pct: pct(enCours, total) }) }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.audits.kpi.planifies') }}</div>
        <div class="kpi-value">{{ planifies }}</div>
        <div class="kpi-foot">{{ t('views.audits.kpi.planifies_foot') }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.audits.kpi.p1') }}</div>
        <div class="kpi-value" :class="{ warn: p1 }">{{ p1 }}</div>
        <div class="kpi-foot">{{ t('views.audits.kpi.p1_foot') }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats{margin:18px 0 14px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:14px 16px;display:flex;flex-direction:column}
.klab{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;line-height:1.25;color:var(--faint);font-weight:var(--eyebrow-weight);min-height:26px}
.kpi-value{font-family:var(--font-data);font-size:30px;font-weight:600;color:var(--heading);line-height:1.1;height:34px;margin-top:6px}
.kpi-value.warn{color:var(--amber)}
.kpi-foot{font-size:11px;color:var(--muted);margin-top:8px}
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} }
</style>
