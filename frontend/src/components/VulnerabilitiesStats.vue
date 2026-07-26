<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

// Section KPI de la page Vulnérabilités. Contrairement à RessourcesStats (agrégats
// serveur), tout est calculé côté client à partir de la liste déjà chargée par
// /vulnerabilities-enriched : la vue passe `filtered`, donc les KPI suivent le client
// actif et les filtres. Aucune requête supplémentaire.
const props = defineProps({ items: { type: Array, default: () => [] } })

const { t } = useI18n()

// Statuts considérés « clos » (convention backend _CLOSED, restreinte aux valeurs de
// l'énumération STATUT_VULN de cette page).
const CLOSED = new Set(['corrigee', 'acceptee', 'faux_positif'])

const round = (n) => Math.round(n)
const pct = (n, d) => (d ? round((n / d) * 100) : 0)

const total = computed(() => props.items.length)

const clientsCount = computed(() => new Set(props.items.map((v) => v.client_id).filter(Boolean)).size)
const appsCount = computed(() => {
  const s = new Set()
  for (const v of props.items) for (const a of (v.applications || [])) s.add(a)
  return s.size
})

const critiquesTotal = computed(() => props.items.filter((v) => v.severite === 'critique').length)
const critiquesOuvertes = computed(() =>
  props.items.filter((v) => v.severite === 'critique' && !CLOSED.has(v.statut)).length)

const slaOverdue = computed(() => props.items.filter((v) => v.sla_overdue).length)
const slaP1 = computed(() => props.items.filter((v) => v.sla_overdue && v.sla_niveau === 'P1').length)

const kevActives = computed(() => props.items.filter((v) => v.kev).length)
const kevRansom = computed(() => props.items.filter((v) => v.kev && v.kev_ransomware).length)

const corrigees = computed(() => props.items.filter((v) => v.statut === 'corrigee').length)
const acceptees = computed(() => props.items.filter((v) => v.statut === 'acceptee').length)
const remediationPct = computed(() => pct(corrigees.value, total.value))
</script>

<template>
  <div class="kpis">
    <div class="kpi">
      <div class="klab">{{ t('views.vulnerabilities.kpi.total') }}</div>
      <div class="kpi-value">{{ total }}</div>
      <div class="kpi-foot">{{ t('views.vulnerabilities.kpi.total_foot', { clients: clientsCount, apps: appsCount }) }}</div>
    </div>
    <div class="kpi">
      <div class="klab">{{ t('views.vulnerabilities.kpi.critiques') }}</div>
      <div class="kpi-value" :class="{ bad: critiquesOuvertes }">{{ critiquesOuvertes }}</div>
      <div class="kpi-foot">{{ t('views.vulnerabilities.kpi.critiques_foot', { n: critiquesTotal }) }}</div>
    </div>
    <div class="kpi">
      <div class="klab">{{ t('views.vulnerabilities.kpi.sla') }}</div>
      <div class="kpi-value" :class="{ warn: slaOverdue }">{{ slaOverdue }}</div>
      <div class="kpi-foot">
        {{ slaOverdue ? t('views.vulnerabilities.kpi.sla_foot', { n: slaP1 }) : t('views.vulnerabilities.kpi.sla_ok') }}
      </div>
    </div>
    <div class="kpi">
      <div class="klab">{{ t('views.vulnerabilities.kpi.kev') }}</div>
      <div class="kpi-value" :class="{ bad: kevActives }">{{ kevActives }}</div>
      <div class="kpi-foot">
        {{ kevActives ? t('views.vulnerabilities.kpi.kev_foot', { n: kevRansom }) : t('views.vulnerabilities.kpi.kev_none') }}
      </div>
    </div>
    <div class="kpi">
      <div class="klab">{{ t('views.vulnerabilities.kpi.remediation') }}</div>
      <div class="kpi-value" :class="{ good: corrigees }">{{ remediationPct }}<span class="u"> %</span></div>
      <div class="kpi-foot">{{ t('views.vulnerabilities.kpi.remediation_foot', { corrigees, acceptees }) }}</div>
    </div>
  </div>
</template>

<style scoped>
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:18px 0 14px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:14px 16px;display:flex;flex-direction:column}
.klab{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;line-height:1.25;color:var(--faint);font-weight:var(--eyebrow-weight);min-height:26px}
.kpi-value{font-family:var(--font-data);font-size:30px;font-weight:600;color:var(--heading);line-height:1.1;height:34px;margin-top:6px}
.kpi-value.warn{color:var(--amber)}
.kpi-value.bad{color:var(--red)}
.kpi-value.good{color:var(--green)}
.kpi-value .u{font-size:16px;color:var(--muted);margin-left:2px}
.kpi-foot{font-size:11px;color:var(--muted);margin-top:8px}
@media (max-width:980px){ .kpis{grid-template-columns:repeat(3,1fr)} }
@media (max-width:620px){ .kpis{grid-template-columns:repeat(2,1fr)} }
</style>
