<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'

// KPI + Répartition de la page Scénarios de menace. Contrairement aux Ressources
// (agrégats serveur scopés RLS), les scénarios sont une bibliothèque CTI globale déjà
// intégralement chargée par le tableau : les agrégats sont dérivés côté client des
// lignes filtrées passées en prop — aucune requête supplémentaire.
const props = defineProps({
  rows: { type: Array, default: () => [] },
})

const { t } = useI18n()
const { enumLabel } = useLabels()

const ENGAGEMENTS = ['red-team', 'purple-team', 'tabletop', 'assumed-breach']
const SOPHISTICATIONS = ['basique', 'intermediaire', 'avancee', 'apt']

const round = (n) => Math.round(n)
const pct = (n, d) => (d ? round((n / d) * 100) : 0)

const total = computed(() => props.rows.length)
const actors = computed(() => {
  const set = new Set()
  for (const r of props.rows) if (r.acteur_emule) set.add(r.acteur_emule)
  return [...set]
})
const actorsText = computed(() => {
  const names = actors.value.slice(0, 3).join(', ')
  return actors.value.length > 3 ? names + '…' : names
})
const highCred = computed(() => props.rows.filter((r) => r.credibilite != null && r.credibilite <= 2).length)
const advanced = computed(() => props.rows.filter((r) => r.sophistication === 'avancee' || r.sophistication === 'apt').length)

const countBy = (key, values) => values.map((v) => {
  const c = props.rows.filter((r) => r[key] === v).length
  return { key: v, count: c, width: pct(c, total.value) }
})
const barsEngagement = computed(() => countBy('type_engagement', ENGAGEMENTS))
const barsSophistication = computed(() => countBy('sophistication', SOPHISTICATIONS))

// Accordéon : replié par défaut, choix mémorisé localement.
const STORE_KEY = 'scenarios.repartition.open'
const showRepartition = ref(false)
try { showRepartition.value = localStorage.getItem(STORE_KEY) === '1' } catch { /* stockage indispo */ }
watch(showRepartition, (v) => { try { localStorage.setItem(STORE_KEY, v ? '1' : '0') } catch { /* ignore */ } })
</script>

<template>
  <div class="stats">
    <div class="kpis">
      <div class="kpi">
        <div class="klab">{{ t('views.scenarios.kpi.total') }}</div>
        <div class="kpi-value">{{ total }}</div>
        <div class="kpi-foot">{{ t('views.scenarios.kpi.total_foot') }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.scenarios.kpi.acteurs') }}</div>
        <div class="kpi-value">{{ actors.length }}</div>
        <div class="kpi-foot">{{ actorsText || t('views.scenarios.kpi.acteurs_none') }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.scenarios.kpi.cred') }}</div>
        <div class="kpi-value" :class="{ good: highCred }">{{ highCred }}</div>
        <div class="kpi-foot">{{ t('views.scenarios.kpi.cred_foot', { pct: pct(highCred, total) }) }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.scenarios.kpi.apt') }}</div>
        <div class="kpi-value" :class="{ warn: advanced }">{{ advanced }}</div>
        <div class="kpi-foot">{{ t('views.scenarios.kpi.apt_foot', { pct: pct(advanced, total) }) }}</div>
      </div>
    </div>

    <div class="panel">
      <div class="head" @click="showRepartition = !showRepartition">
        <div class="ht">
          <span class="sec-title">{{ t('views.scenarios.repartition.title') }}</span>
          <span class="hint">{{ t('views.scenarios.repartition.resume', { acteurs: actors.length, apt: advanced }) }}</span>
        </div>
        <span class="chev">{{ showRepartition ? '⌃' : '⌄' }}</span>
      </div>
      <div v-if="showRepartition" class="body-wrap">
        <div class="sec-desc">{{ t('views.scenarios.repartition.desc') }}</div>
        <div class="split">
          <div class="col">
            <div class="sub">{{ t('views.scenarios.repartition.par_engagement') }}</div>
            <div class="cbody">
              <div v-for="b in barsEngagement" :key="b.key" class="bar-row">
                <span class="bl">{{ enumLabel(b.key) }}</span>
                <span class="track"><span class="fill" :style="{ width: b.width + '%' }"></span></span>
                <span class="bn">{{ b.count }}<span class="pct">({{ b.width }} %)</span></span>
              </div>
            </div>
          </div>
          <div class="col">
            <div class="sub">{{ t('views.scenarios.repartition.par_sophistication') }}</div>
            <div class="cbody">
              <div v-for="b in barsSophistication" :key="b.key" class="bar-row">
                <span class="bl">{{ enumLabel(b.key) }}</span>
                <span class="track"><span class="fill" :style="{ width: b.width + '%' }"></span></span>
                <span class="bn">{{ b.count }}<span class="pct">({{ b.width }} %)</span></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats{margin:18px 0 14px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:14px 16px;display:flex;flex-direction:column}
.klab{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;line-height:1.25;color:var(--faint);font-weight:var(--eyebrow-weight);min-height:26px}
.kpi-value{font-family:var(--font-data);font-size:30px;font-weight:600;color:var(--heading);line-height:1.1;height:34px;margin-top:6px}
.kpi-value.warn{color:var(--amber)}
.kpi-value.good{color:var(--green)}
.kpi-foot{font-size:11px;color:var(--muted);margin-top:8px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);overflow:hidden}
.head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;cursor:pointer}
.head .ht{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.sec-title{font-size:15px;font-weight:600;color:var(--heading)}
.head .hint{font-size:11.5px;color:var(--faint)}
.chev{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border:1px solid var(--border);border-radius:var(--r-mini);color:var(--muted);font-size:12px}
.body-wrap{padding:0 16px 16px;border-top:1px solid var(--border-2)}
.sec-desc{font-size:12px;color:var(--muted);margin:12px 0 20px;line-height:1.4}
.split{display:grid;grid-template-columns:1fr 1fr;gap:clamp(32px,6%,120px);align-items:stretch}
.col{display:flex;flex-direction:column}
.col .sub{font-family:var(--font-eyebrow);font-size:11px;color:var(--faint);font-weight:var(--eyebrow-weight);text-transform:uppercase;letter-spacing:.04em;min-height:15px}
.col .cbody{flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:10px}
.bar-row{display:grid;grid-template-columns:110px 1fr 66px;align-items:center;gap:8px;margin:5px 0}
.bar-row .bl{font-size:11.5px;color:var(--muted)}
.track{display:block;height:8px;background:var(--c-violet-bg);border-radius:99px;overflow:hidden}
.fill{display:block;height:100%;background:var(--violet);border-radius:99px}
.bn{font-size:12px;color:var(--heading);font-weight:600;text-align:right}
.bn .pct{font-size:11.5px;color:var(--muted);font-weight:400;margin-left:3px}
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} .split{grid-template-columns:1fr;gap:20px} }
</style>
