<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

// KPI de la page Journal (inviolable). Contrairement aux Scénarios (agrégats dérivés
// des lignes chargées), les compteurs décrivent TOUTE la chaîne : ils viennent de
// l'endpoint serveur /journal/stats (scope-aware), indépendants des filtres/pagination.
// L'état d'intégrité vient de /journal/verify (recalcul de la chaîne côté serveur).
const props = defineProps({
  stats: { type: Object, default: null },
  verify: { type: Object, default: null },
})

const { t } = useI18n()
const round = (n) => Math.round(n)
const pct = (n, d) => (d ? round((n / d) * 100) : 0)

const total = computed(() => props.stats?.total ?? 0)
const denied = computed(() => props.stats?.denied ?? 0)
const actors = computed(() => props.stats?.distinct_actors ?? 0)

// Trois états d'intégrité : inconnu (pas encore vérifié), intacte, rompue.
const integrity = computed(() => {
  if (!props.verify) return 'unknown'
  return props.verify.intact ? 'ok' : 'ko'
})
const integrityLabel = computed(() => {
  if (integrity.value === 'ok') return t('views.journal.kpi.integrity_ok')
  if (integrity.value === 'unknown') return t('views.journal.kpi.integrity_unknown')
  const seq = props.verify?.break_at_seq
  return seq != null
    ? t('views.journal.kpi.integrity_ko_seq', { seq })
    : t('views.journal.kpi.integrity_ko')
})
const integrityFoot = computed(() => t('views.journal.kpi.integrity_foot_' + integrity.value))
</script>

<template>
  <div class="kpis">
    <div class="kpi">
      <div class="klab">{{ t('views.journal.kpi.total') }}</div>
      <div class="kpi-value">{{ total }}</div>
      <div class="kpi-foot">{{ t('views.journal.kpi.total_foot') }}</div>
    </div>
    <div class="kpi">
      <div class="klab">{{ t('views.journal.kpi.integrity') }}</div>
      <div class="kpi-value txt" :class="{ good: integrity === 'ok', bad: integrity === 'ko' }">{{ integrityLabel }}</div>
      <div class="kpi-foot">{{ integrityFoot }}</div>
    </div>
    <div class="kpi">
      <div class="klab">{{ t('views.journal.kpi.actors') }}</div>
      <div class="kpi-value">{{ actors }}</div>
      <div class="kpi-foot">{{ t('views.journal.kpi.actors_foot') }}</div>
    </div>
    <div class="kpi">
      <div class="klab">{{ t('views.journal.kpi.denied') }}</div>
      <div class="kpi-value" :class="{ warn: denied }">{{ denied }}</div>
      <div class="kpi-foot">{{ t('views.journal.kpi.denied_foot', { pct: pct(denied, total) }) }}</div>
    </div>
  </div>
</template>

<style scoped>
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0 14px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:14px 16px;display:flex;flex-direction:column}
.klab{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;line-height:1.25;color:var(--faint);font-weight:var(--eyebrow-weight);min-height:26px}
.kpi-value{font-family:var(--font-data);font-size:30px;font-weight:600;color:var(--heading);line-height:1.1;height:34px;margin-top:6px}
.kpi-value.txt{font-size:21px;display:flex;align-items:center}
.kpi-value.warn{color:var(--amber)}
.kpi-value.good{color:var(--green)}
.kpi-value.bad{color:var(--red)}
.kpi-foot{font-size:11px;color:var(--muted);margin-top:8px}
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} }
</style>
