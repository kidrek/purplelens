<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'
import { fieldsFor } from '../fields'
import { api } from '../api/client'

// KPI + Répartition de la page Ressources. Les agrégats sont calculés côté serveur
// (/analytics/ressources, scopé RLS) et reflètent les filtres du tableau, passés en
// props par RessourcesView. Aucun état de filtre dupliqué ici.
const props = defineProps({
  fOrgs: { type: Array, default: () => [] },
  fTypes: { type: Array, default: () => [] },
  fRoles: { type: Array, default: () => [] },
})

const { t } = useI18n()
const { enumLabel } = useLabels()

const TYPES = ['humaine', 'materielle', 'logicielle', 'documentaire']
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

const round = (n) => Math.round(n)
const pct = (n, d) => (d ? round((n / d) * 100) : 0)

const total = computed(() => data.value?.total || 0)
const byType = computed(() => data.value?.by_type || {})
const byRole = computed(() => data.value?.by_role || {})
const orgs = computed(() => data.value?.organisations || { total: 0, covered: 0 })

const humaines = computed(() => byType.value.humaine || 0)
const roleHolders = computed(() => KNOWN_ROLES.reduce((a, r) => a + (byRole.value[r] || 0), 0))
const sousDotes = computed(() => KNOWN_ROLES.filter((r) => (byRole.value[r] || 0) <= SOUS_DOTE_THRESHOLD))
const sousDotesText = computed(() => sousDotes.value.map((r) => enumLabel(r)).join(', '))

const bars = computed(() => TYPES.map((ty) => {
  const c = byType.value[ty] || 0
  return { key: ty, count: c, width: pct(c, total.value) }
}))

// Radar par rôle : pentagone à angles fixes, rayon proportionnel à l'effectif (échelle
// au rôle le plus pourvu, pour rester lisible) ; % = part des rôles pourvus.
const RADAR = { cx: 115, cy: 100, R: 60, off: 14 }
const radar = computed(() => {
  const counts = KNOWN_ROLES.map((r) => byRole.value[r] || 0)
  const max = Math.max(...counts, 1)
  const holders = roleHolders.value
  const pts = KNOWN_ROLES.map((role, i) => {
    const ang = ((-90 + i * 72) * Math.PI) / 180
    const rr = RADAR.R * (counts[i] / max)
    const cos = Math.cos(ang), sin = Math.sin(ang)
    return {
      role,
      count: counts[i],
      part: holders ? round((counts[i] / holders) * 100) : 0,
      low: counts[i] <= SOUS_DOTE_THRESHOLD,
      x: RADAR.cx + rr * cos, y: RADAR.cy + rr * sin,
      ax: RADAR.cx + RADAR.R * cos, ay: RADAR.cy + RADAR.R * sin,
      lx: RADAR.cx + (RADAR.R + RADAR.off) * cos,
      ly: RADAR.cy + (RADAR.R + RADAR.off) * sin,
      anchor: cos > 0.3 ? 'start' : cos < -0.3 ? 'end' : 'middle',
    }
  })
  const join = (fx, fy) => pts.map((p) => `${fx(p).toFixed(1)},${fy(p).toFixed(1)}`).join(' ')
  return {
    pts,
    polygon: join((p) => p.x, (p) => p.y),
    gridOuter: join((p) => p.ax, (p) => p.ay),
    gridMid: join((p) => RADAR.cx + (p.ax - RADAR.cx) * 0.5, (p) => RADAR.cy + (p.ay - RADAR.cy) * 0.5),
  }
})

// Accordéon : replié par défaut, choix mémorisé localement.
const STORE_KEY = 'ressources.repartition.open'
const showRepartition = ref(false)
try { showRepartition.value = localStorage.getItem(STORE_KEY) === '1' } catch { /* stockage indispo */ }
watch(showRepartition, (v) => { try { localStorage.setItem(STORE_KEY, v ? '1' : '0') } catch { /* ignore */ } })

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

    <div class="panel">
      <div class="head" @click="showRepartition = !showRepartition">
        <div class="ht">
          <span class="sec-title">{{ t('views.ressources.repartition.title') }}</span>
          <span class="hint">{{ t('views.ressources.repartition.resume', { humaines, n: sousDotes.length }) }}</span>
        </div>
        <span class="chev">{{ showRepartition ? '⌃' : '⌄' }}</span>
      </div>
      <div v-if="showRepartition" class="body-wrap">
        <div class="sec-desc">{{ t('views.ressources.repartition.desc') }}</div>
        <div class="split">
          <div class="col">
            <div class="sub">{{ t('views.ressources.repartition.par_type') }}</div>
            <div class="cbody">
              <div v-for="b in bars" :key="b.key" class="bar-row">
                <span class="bl">{{ enumLabel(b.key) }}</span>
                <span class="track"><span class="fill" :style="{ width: b.width + '%' }"></span></span>
                <span class="bn">{{ b.count }}<span class="pct">({{ b.width }} %)</span></span>
              </div>
            </div>
          </div>
          <div class="col">
            <div class="sub center">{{ t('views.ressources.repartition.par_role') }}</div>
            <div class="cbody">
              <svg viewBox="-40 0 305 205" width="100%" role="img" :aria-label="t('views.ressources.repartition.par_role')">
                <polygon class="rgrid" :points="radar.gridOuter" />
                <polygon class="rgrid" :points="radar.gridMid" />
                <line v-for="p in radar.pts" :key="'s' + p.role" class="rspoke" :x1="RADAR.cx" :y1="RADAR.cy" :x2="p.ax" :y2="p.ay" />
                <polygon class="rpoly" :points="radar.polygon" />
                <circle v-for="p in radar.pts" :key="'d' + p.role" :class="['rdot', { low: p.low }]" :cx="p.x" :cy="p.y" :r="p.low ? 3.2 : 2.6" />
                <text v-for="p in radar.pts" :key="'t' + p.role" class="rax" :x="p.lx" :y="p.ly" :text-anchor="p.anchor">{{ enumLabel(p.role) }} · {{ p.count }}<tspan :class="['rax2', { lo: p.low }]" :x="p.lx" dy="11">{{ p.part }} %</tspan></text>
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats{margin:18px 0 14px}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:14px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:14px 16px;display:flex;flex-direction:column}
.klab{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;line-height:1.25;color:var(--faint);font-weight:var(--eyebrow-weight);min-height:26px}
.kpi-value{font-family:var(--font-data);font-size:30px;font-weight:600;color:var(--heading);line-height:1.1;height:34px;margin-top:6px}
.kpi-value.warn{color:var(--amber)}
.kpi-value .u{font-size:16px;color:var(--muted);margin-left:3px}
.kpi-foot{font-size:11px;color:var(--muted);margin-top:8px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);overflow:hidden}
.head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;cursor:pointer}
.head .ht{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.sec-title{font-size:15px;font-weight:600;color:var(--heading)}
.head .hint{font-size:11.5px;color:var(--faint)}
.chev{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border:1px solid var(--border);border-radius:var(--r-mini);color:var(--muted);font-size:12px}
.body-wrap{padding:0 16px 16px;border-top:1px solid var(--border-2)}
.sec-desc{font-size:12px;color:var(--muted);margin:12px 0 56px;line-height:1.4}
.split{display:grid;grid-template-columns:minmax(300px,380px) 340px;gap:clamp(48px,8%,180px);justify-content:center;margin:0 auto;align-items:stretch}
.col{display:flex;flex-direction:column}
.col .sub{font-family:var(--font-eyebrow);font-size:11px;color:var(--faint);font-weight:var(--eyebrow-weight);text-transform:uppercase;letter-spacing:.04em;min-height:15px}
.col .sub.center{text-align:center}
.col .cbody{flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:10px}
.bar-row{display:grid;grid-template-columns:92px 1fr 66px;align-items:center;gap:8px;margin:5px 0}
.bar-row .bl{font-size:11.5px;color:var(--muted)}
.track{display:block;height:8px;background:var(--c-violet-bg);border-radius:99px;overflow:hidden}
.fill{display:block;height:100%;background:var(--violet);border-radius:99px}
.bn{font-size:12px;color:var(--heading);font-weight:600;text-align:right}
.bn .pct{font-size:11.5px;color:var(--muted);font-weight:400;margin-left:3px}
.rax{font-size:11px;fill:var(--muted);text-transform:uppercase}
.rax2{font-size:9.5px;fill:var(--faint);text-transform:none}
.rax2.lo{fill:var(--amber)}
.rgrid{fill:none;stroke:var(--border-2);stroke-width:1}
.rspoke{stroke:var(--border-2);stroke-width:1}
.rpoly{fill:var(--c-violet-bg);stroke:var(--violet);stroke-width:1.6}
.rdot{fill:var(--violet)}
.rdot.low{fill:var(--amber)}
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} .split{grid-template-columns:1fr;gap:20px} }
</style>
