<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

// KPI de la page Exercices Purple. Les agrégats sont dérivés côté client des lignes
// déjà chargées et filtrées (prop `rows`) — aucune requête supplémentaire. `runsTotal`
// (optionnel) porte le nombre de RUNs sous-jacents avant regroupement.
const props = defineProps({
  rows: { type: Array, default: () => [] },
  runsTotal: { type: Number, default: null },
})

const { t } = useI18n()

const round = (n) => Math.round(n)
const pct = (n, d) => (d ? round((n / d) * 100) : 0)

const total = computed(() => props.rows.length)
const active = computed(() => props.rows.filter((r) => r.statut === 'en_cours').length)
const done = computed(() => props.rows.filter((r) => r.statut === 'termine').length)
const clients = computed(() => new Set(props.rows.map((r) => r.client_id).filter(Boolean)).size)
// Pied de la carte « Exercices » : rappel des RUNs cumulés quand la vue est groupée.
const runsFoot = computed(() => (props.runsTotal != null && props.runsTotal !== total.value))
</script>

<template>
  <div class="stats">
    <div class="kpis">
      <div class="kpi">
        <div class="klab">{{ t('views.exercices.kpi.total') }}</div>
        <div class="kpi-value">{{ total }}</div>
        <div class="kpi-foot">
          {{ runsFoot ? t('views.exercices.kpi.total_runs_foot', { n: runsTotal }) : t('views.exercices.kpi.total_foot') }}
        </div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.exercices.kpi.active') }}</div>
        <div class="kpi-value" :class="{ warn: active }">{{ active }}</div>
        <div class="kpi-foot">{{ t('views.exercices.kpi.active_foot') }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.exercices.kpi.done') }}</div>
        <div class="kpi-value" :class="{ good: done }">{{ done }}</div>
        <div class="kpi-foot">{{ t('views.exercices.kpi.done_foot', { pct: pct(done, total) }) }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.exercices.kpi.clients') }}</div>
        <div class="kpi-value">{{ clients }}</div>
        <div class="kpi-foot">{{ t('views.exercices.kpi.clients_foot') }}</div>
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
.kpi-value.good{color:var(--green)}
.kpi-foot{font-size:11px;color:var(--muted);margin-top:8px}
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} }
</style>
