<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { useUiStore } from '../stores/ui'
import { api } from '../api/client'
import { useLabels } from '../composables/useLabels'
const { t, te, locale } = useI18n()
const { enumLabel } = useLabels()

const d = ref(null)
const ui = useUiStore()
const loading = ref(true)
const error = ref(null)

const SEV = [
  { k: 'critique', color: 'var(--red)' },
  { k: 'haute', color: 'var(--amber)' },
  { k: 'moyenne', color: 'var(--cyan)' },
  { k: 'basse', color: 'var(--green)' },
]
const AUDIT_TONE = { purple_team: 'var(--violet)', red_team: 'var(--red)', pentest: 'var(--cyan)', bas: 'var(--amber)' }

// Libellés des tactiques (bande kill-chain) — i18n, slug brut en repli.
const tacLabel = (k) => (te('views.cockpit.tactics.' + k) ? t('views.cockpit.tactics.' + k) : k)

// Posture agrégée (maquette §dash.posture) : segments du pool « dernier run par
// audit » calculé côté API. covPct = détecté/testé (KPI detection_rate).
const posture = computed(() => {
  const v = d.value?.posture?.verdicts || {}
  return {
    prev: v.prevented || 0,
    alert: v.alerted || 0,
    logged: v.logged || 0,
    blind: v.no_telemetry || 0,
    tested: d.value?.posture?.tested || 0,
    covPct: d.value?.kpis?.detection_rate ?? 0,
  }
})
// Segments de la barre : clé posture/i18n, classe DA, icône (SVG maquette).
const SEGMENTS = [
  { k: 'prev', cls: 'prev' },
  { k: 'alert', cls: 'alrt' },
  { k: 'logged', cls: 'logd' },
  { k: 'blind', cls: 'blnd' },
]
const SEG_ICONS = {
  prev: '<path d="M8 1.6 13.4 3.6V7.6C13.4 10.6 11 12.9 8 14.1 5 12.9 2.6 10.6 2.6 7.6V3.6Z"/><path d="M5.7 7.8 7.3 9.4 10.4 6.2"/>',
  alert: '<path d="M8 2.2C6 2.2 4.8 3.6 4.8 5.6 4.8 8.2 3.9 9.6 3 10.4H13C12.1 9.6 11.2 8.2 11.2 5.6 11.2 3.6 10 2.2 8 2.2Z"/><path d="M6.6 12.2A1.5 1.5 0 0 0 9.4 12.2"/>',
  logged: '<rect x="3.2" y="2.4" width="9.6" height="11.2" rx="1.4"/><path d="M5.4 5.6H10.6M5.4 8H10.6M5.4 10.4H8.6"/>',
  blind: '<path d="M2.2 8S4.5 3.8 8 3.8s5.8 4.2 5.8 4.2-2.3 4.2-5.8 4.2c-1 0-1.9-.3-2.7-.7"/><circle cx="8" cy="8" r="1.9"/><path d="M2.5 2.5 13.5 13.5"/>',
}
const segPct = (n) => Math.round((n / (posture.value.tested || 1)) * 100)

// Courbe de tendance : polyline SVG normalisée (0-100 en Y).
const TREND_W = 560, TREND_H = 96
const trendGeo = computed(() => {
  const pts = d.value?.trend || []
  if (pts.length < 2) return null
  const xs = pts.map((_, i) => 12 + (TREND_W - 24) * (i / (pts.length - 1)))
  const ys = pts.map((p) => 10 + (TREND_H - 26) * (1 - p.pct / 100))
  return {
    line: xs.map((x, i) => `${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' '),
    dots: xs.map((x, i) => ({ x, y: ys[i] })),
  }
})

async function load() {
  loading.value = true; error.value = null
  try { d.value = await api.get('/analytics/cockpit' + (ui.clientQuery ? '?' + ui.clientQuery : '')) }
  catch (e) { error.value = e.message || 'Erreur' }
  finally { loading.value = false }
}

const vulnTotal = computed(() => d.value?.vulnerabilities?.total || 0)
const sevPct = (k) => {
  const n = d.value?.vulnerabilities?.by_severity?.[k] || 0
  return vulnTotal.value ? Math.round((n / vulnTotal.value) * 100) : 0
}
const auditEntries = computed(() => Object.entries(d.value?.audits_by_type || {}))
const auditMax = computed(() => Math.max(1, ...auditEntries.value.map(([, n]) => n)))

// Angles morts par tactique (maquette §panel.blind) : barres relatives au max.
const blindMax = computed(() => Math.max(1, ...(d.value?.blind_tactics || []).map((b) => b.count)))

// Journal (maquette §panel.journal) : event_type = "<entité>.<action>" — le 1er segment
// donne l'entité (libellé nav si connu), le reste l'action (chip colorée par nature).
const evEntity = (e) => e.split('.')[0]
const evAction = (e) => e.split('.').slice(1).join('.')
const actionClass = (a) => ({ create: 'green', update: 'blue', delete: 'red', archive: 'amber', import: 'violet' }[a] || 'gray')
const actionLabel = (a) => (te('views.cockpit.journal.actions.' + a) ? t('views.cockpit.journal.actions.' + a) : a)
const entityLabel = (e) => (te('nav.' + e) ? t('nav.' + e) : e)
const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString(locale.value === 'en' ? 'en-GB' : 'fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '')
// Fuseau d'affichage : l'API renvoie de l'UTC (timestamptz), rendu en heure locale du poste.
const tz = Intl.DateTimeFormat().resolvedOptions().timeZone

watch(() => ui.activeClient, load)
onMounted(load)
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.cockpit.eyebrow') }}</div>
    <h1>{{ t('views.cockpit.title') }}</h1>

    <p v-if="loading" class="muted">{{ t('views.cockpit.loading') }}</p>
    <p v-else-if="error" class="err">{{ error }}</p>

    <template v-else-if="d">
      <div class="kpis">
        <div class="kpi">
          <div class="kpi-label">{{ t('views.cockpit.kpi.detection') }}</div>
          <div class="kpi-value">{{ d.kpis.detection_rate ?? '—' }}<span v-if="d.kpis.detection_rate != null" class="u">%</span></div>
          <div class="kpi-foot">{{ t('views.cockpit.kpi.detectionFoot', { caught: d.posture.caught, tested: d.posture.tested }) }}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">{{ t('views.cockpit.kpi.blind') }}</div>
          <div class="kpi-value" :class="{ warn: d.kpis.blind_spots > 0 }">{{ d.kpis.blind_spots }}</div>
          <div class="kpi-foot">{{ t('views.cockpit.kpi.blindFoot') }}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">{{ t('views.cockpit.kpi.sla') }}</div>
          <div class="kpi-value" :class="{ bad: d.kpis.p1_breached > 0 }">{{ d.kpis.p1_breached }}</div>
          <div class="kpi-foot">{{ t('views.cockpit.kpi.slaFoot') }}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">{{ t('views.cockpit.kpi.audits') }}</div>
          <div class="kpi-value">{{ d.kpis.audits }}</div>
          <div class="kpi-foot">{{ t('views.cockpit.kpi.auditsFoot', { n: d.exercises }) }}</div>
        </div>
      </div>

      <!-- Couverture par tactique MITRE — ordre kill-chain -->
      <section v-if="d.tactic_coverage?.length" class="panel wide">
        <div class="p-head"><span class="p-title">{{ t('views.cockpit.tacticsPanel.title') }}</span>
          <span class="p-note">{{ t('views.cockpit.tacticsPanel.note') }}</span></div>
        <div class="tstrip">
          <div v-for="tc in d.tactic_coverage" :key="tc.tactic" :class="['tcell', 't-' + tc.state]"
               :title="t('views.cockpit.tacticsPanel.cellTitle', { detected: tc.detected, total: tc.total })">
            <div class="tname">{{ tacLabel(tc.tactic) }}</div>
            <div class="tfoot"><span class="tbead"></span><span class="tfrac">{{ tc.detected }}/{{ tc.total }}</span>
              <span class="tlbl">{{ t('views.cockpit.tacticsPanel.' + (tc.state === 'detected' ? 'covered' : tc.state)) }}</span></div>
          </div>
        </div>
      </section>

      <!-- Tendance du taux de détection -->
      <section v-if="trendGeo" class="panel wide">
        <div class="p-head"><span class="p-title">{{ t('views.cockpit.trend.title') }}</span>
          <span class="p-note">{{ t('views.cockpit.trend.note') }}</span></div>
        <div class="trend">
          <svg :viewBox="'0 0 ' + 560 + ' ' + 96" preserveAspectRatio="none" class="trend-svg">
            <polyline :points="trendGeo.line" fill="none" stroke="var(--violet-accent)" stroke-width="2" />
            <circle v-for="(pt, i) in trendGeo.dots" :key="i" :cx="pt.x" :cy="pt.y" r="3" fill="var(--violet-accent)" />
          </svg>
          <div class="trend-pts">
            <span v-for="(pt, i) in d.trend" :key="i" class="trend-pt"
                  :title="t('views.cockpit.trend.pointTitle', { caught: pt.caught, tested: pt.tested, audits: pt.audits })">
              <span class="rl">{{ pt.date.slice(2, 7) }}</span><b>{{ pt.pct }}%</b>
            </span>
          </div>
        </div>
      </section>

      <div class="cols">
        <!-- Posture agrégée — barre segmentée de la maquette (pool dernier run/audit) -->
        <section class="panel">
          <div class="p-head"><span class="p-title">{{ t('views.cockpit.posture.title') }}</span>
            <span class="p-side">
              <span class="p-note">{{ t('views.cockpit.posture.method') }}</span>
              <RouterLink class="link" to="/attack-matrix">{{ t('views.cockpit.posture.matrixLink') }}</RouterLink>
            </span></div>
          <div class="pbody">
            <div class="pcov">{{ posture.covPct }} %</div>
            <div class="pcov-sub">{{ posture.prev + posture.alert }} / {{ posture.tested }} {{ t('views.cockpit.posture.testedN') }}</div>
            <div v-if="posture.tested > 0">
              <div class="pbar" style="margin-top:14px">
                <div v-for="sg in SEGMENTS" v-show="posture[sg.k] > 0" :key="sg.k"
                     class="pseg" :class="sg.cls" :style="{ flexGrow: posture[sg.k] }"
                     :title="t('views.cockpit.posture.' + sg.k) + ' — ' + posture[sg.k]">
                  <svg class="pg" viewBox="0 0 16 16" v-html="SEG_ICONS[sg.k]"></svg>
                  <span class="ppc">{{ segPct(posture[sg.k]) }}%</span>
                </div>
              </div>
              <div class="pbar-legend">
                <span v-for="sg in SEGMENTS" :key="sg.k" class="pleg" :class="sg.cls">
                  <svg class="pg" viewBox="0 0 16 16" v-html="SEG_ICONS[sg.k]"></svg>
                  <span>{{ t('views.cockpit.posture.' + sg.k) }}</span> <b>{{ posture[sg.k] }}</b>
                </span>
              </div>
            </div>
            <div v-else class="muted sm">{{ t('views.cockpit.posture.empty') }}</div>
          </div>
        </section>

        <!-- Angles morts par tactique — ordre kill-chain (maquette) -->
        <section class="panel">
          <div class="p-head"><span class="p-title">{{ t('views.cockpit.blindPanel.title') }}</span>
            <span class="p-note">{{ t('views.cockpit.tacticsPanel.note') }}</span></div>
          <div class="pbody">
            <template v-if="d.blind_tactics.length">
              <div class="blind-total"><span class="bn2">{{ d.kpis.blind_spots }}</span>
                <span class="bl2">{{ t('views.cockpit.blindPanel.totalLabel') }}</span></div>
              <div class="blind-list">
                <div v-for="b in d.blind_tactics" :key="b.tactic" class="brow">
                  <div class="bt"><span class="btn2">{{ tacLabel(b.tactic) }}</span><span class="btid">{{ b.tactic }}</span></div>
                  <div class="bbar"><i :style="{ width: Math.round(b.count / blindMax * 100) + '%' }"></i></div>
                  <span class="bc">{{ b.count }}</span>
                </div>
              </div>
              <p class="bhint">{{ t('views.cockpit.blindPanel.hint') }}</p>
            </template>
            <p v-else class="muted sm">{{ t('views.cockpit.blindPanel.empty') }}</p>
          </div>
        </section>
      </div>

      <div class="cols">
        <section class="panel">
          <div class="p-head"><span class="p-title">{{ t('views.cockpit.vulns.title') }}</span>
            <RouterLink class="link" to="/vulnerabilities">{{ t('views.cockpit.vulns.all', { n: vulnTotal }) }}</RouterLink></div>
          <div class="bars">
            <div v-for="s in SEV" :key="s.k" class="barrow">
              <span class="bl">{{ t('views.cockpit.vulns.' + s.k) }}</span>
              <div class="track"><div class="fill" :style="{ width: sevPct(s.k) + '%', background: s.color }"></div></div>
              <span class="bn">{{ d.vulnerabilities.by_severity[s.k] || 0 }}</span>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="p-head"><span class="p-title">{{ t('views.cockpit.auditTypes.title') }}</span></div>
          <p v-if="!auditEntries.length" class="muted sm pad">{{ t('views.cockpit.auditTypes.empty') }}</p>
          <div v-else class="atypes">
            <div v-for="[cat, n] in auditEntries" :key="cat" class="atype">
              <div class="acol" :style="{ height: (n / auditMax * 70 + 8) + 'px', background: AUDIT_TONE[cat] || 'var(--violet)' }"></div>
              <div class="an">{{ n }}</div>
              <div class="ac">{{ enumLabel(cat) }}</div>
            </div>
          </div>
        </section>
      </div>

      <section class="panel">
        <div class="p-head"><span class="p-title">{{ t('views.cockpit.journal.title') }}</span>
          <RouterLink class="link" to="/journal">{{ t('views.cockpit.journal.all') }}</RouterLink></div>
        <div class="table-wrap">
          <table class="dense">
            <thead><tr><th class="num">{{ t('views.cockpit.journal.seq') }}</th>
              <th>{{ t('views.cockpit.journal.time') }} <span class="tz">({{ tz }})</span></th>
              <th>{{ t('views.cockpit.journal.actor') }}</th>
              <th>{{ t('views.cockpit.journal.action') }}</th>
              <th>{{ t('views.cockpit.journal.entity') }}</th></tr></thead>
            <tbody>
              <tr v-for="j in d.journal" :key="j.seq">
                <td class="num mono-cell">{{ j.seq }}</td>
                <td class="mono-cell">{{ fmtTime(j.created_at) }}</td>
                <td><span v-if="j.actor" class="chip violet sm">{{ j.actor }}</span><span v-else class="muted">—</span></td>
                <td><span class="chip sm" :class="actionClass(evAction(j.event_type))">{{ actionLabel(evAction(j.event_type)) }}</span></td>
                <td class="muted">{{ entityLabel(evEntity(j.event_type)) }}</td>
              </tr>
              <tr v-if="!d.journal.length"><td colspan="5" class="list-empty">{{ t('common.empty') }}</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.sm{font-size:12.5px}
.pad{padding:12px 16px;margin:0}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:14px 16px}
.kpi-label{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.kpi-value{font-family:var(--font-data);font-size:30px;font-weight:600;color:var(--heading);line-height:1.1;margin-top:4px}
.kpi-value .u{font-size:16px;color:var(--muted);margin-left:2px}
.kpi-value.warn{color:var(--amber)} .kpi-value.bad{color:var(--red)}
.kpi-foot{font-size:11px;color:var(--muted);margin-top:3px}
.panel.wide{margin-bottom:12px}
.p-note{font-size:10.5px;color:var(--faint);font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em}
.p-side{display:flex;align-items:center;gap:10px}
.tstrip{display:flex;gap:6px;overflow-x:auto;padding:12px 14px}
.tcell{flex:1;min-width:88px;border:1px solid var(--border-2);border-radius:var(--r-mini);padding:7px 8px;border-top:3px solid var(--border-2)}
.tcell .tname{font-size:10.5px;font-weight:600;color:var(--heading);line-height:1.2}
.tfoot{display:flex;align-items:center;gap:5px;margin-top:5px}
.tbead{width:7px;height:7px;border-radius:50%}
.tfrac{font-family:var(--font-data);font-size:11px;color:var(--heading);font-weight:600}
.tlbl{font-size:9.5px;color:var(--muted)}
.tcell.t-detected{border-top-color:var(--green)} .tcell.t-detected .tbead{background:var(--green)}
.tcell.t-partial{border-top-color:var(--amber)} .tcell.t-partial .tbead{background:var(--amber)}
.tcell.t-gap{border-top-color:var(--red)} .tcell.t-gap .tbead{background:var(--red)}
.trend{padding:12px 14px}
.trend-svg{display:block;width:100%;height:96px;overflow:visible}
.trend-pts{display:flex;justify-content:space-between;margin-top:6px}
.trend-pt{font-family:var(--font-data);font-size:10px;color:var(--muted);text-align:center;flex:1;min-width:0}
.trend-pt b{display:block;color:var(--heading);font-size:12px;font-weight:600}
.trend-pt .rl{color:var(--faint);font-size:9px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-panel);padding:0;overflow:hidden}
.p-head{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border-2)}
.p-title{font-family:var(--font-display);font-size:14px;font-weight:600;color:var(--heading)}
.link{font-size:11.5px;color:var(--violet-accent);text-decoration:none}
.link:hover{text-decoration:underline}
/* Posture agrégée — barre segmentée (maquette, DA) */
.pbody{padding:14px 16px}
.pcov{font-family:var(--font-data);font-size:32px;font-weight:600;color:var(--c-green-tx);line-height:1}
.pcov-sub{font-size:11.5px;color:var(--muted);margin-top:3px}
.pbar{display:flex;height:34px;border-radius:8px;overflow:hidden;border:1px solid var(--border-2)}
.pseg{display:flex;align-items:center;justify-content:center;gap:5px;min-width:0;flex-basis:0;
  color:var(--c-tx);background:var(--c-bg);border-right:1px solid var(--surface);
  transition:flex-grow var(--t) var(--ease)}
.pseg:last-child{border-right:0}
.pseg .pg{width:14px;height:14px;flex:0 0 auto;stroke:currentColor;fill:none;stroke-width:1.6;
  stroke-linecap:round;stroke-linejoin:round}
.pseg .ppc{font-family:var(--font-data);font-size:11px;font-weight:600;white-space:nowrap}
.pseg.prev{--c-bg:var(--c-green-bg);--c-tx:var(--c-green-tx)}
.pseg.alrt{--c-bg:var(--c-green-bg);--c-tx:var(--c-green-tx);border-left:2px dashed var(--c-green-bd)}
.pseg.logd{--c-bg:var(--c-amber-bg);--c-tx:var(--c-amber-tx)}
.pseg.blnd{--c-bg:var(--c-red-bg);--c-tx:var(--c-red-tx)}
.pbar-legend{display:flex;flex-wrap:wrap;gap:13px;margin-top:9px}
.pleg{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:var(--muted)}
.pleg .pg{width:13px;height:13px;stroke:currentColor;stroke-width:1.6;fill:none;stroke-linecap:round;stroke-linejoin:round}
.pleg b{font-family:var(--font-data);font-weight:600}
.pleg.prev,.pleg.prev .pg,.pleg.prev b{color:var(--c-green-tx)}
.pleg.alrt,.pleg.alrt .pg,.pleg.alrt b{color:var(--c-green-tx)}
.pleg.logd,.pleg.logd .pg,.pleg.logd b{color:var(--c-amber-tx)}
.pleg.blnd,.pleg.blnd .pg,.pleg.blnd b{color:var(--c-red-tx)}
.bars{padding:14px 16px;display:flex;flex-direction:column;gap:9px}
.barrow{display:flex;align-items:center;gap:10px}
.bl{width:110px;font-size:12px;color:var(--muted);flex:0 0 auto}
.track{flex:1;height:9px;background:var(--surface-3);border-radius:99px;overflow:hidden}
.fill{height:100%;border-radius:99px;transition:width var(--t) var(--ease);min-width:2px}
.bn{width:34px;text-align:right;font-family:var(--font-data);font-size:12px;color:var(--text)}
/* Angles morts par tactique (maquette) */
.blind-total{display:flex;align-items:baseline;gap:9px;margin-bottom:4px}
.blind-total .bn2{font-family:var(--font-data);font-size:28px;font-weight:600;color:var(--c-red-tx);line-height:1}
.blind-total .bl2{font-size:12px;color:var(--muted)}
.blind-list{display:flex;flex-direction:column;gap:7px;margin-top:12px}
.brow{display:grid;grid-template-columns:170px 1fr 26px;gap:10px;align-items:center}
.brow .bt{display:flex;flex-direction:column;gap:1px;min-width:0}
.brow .btn2{font-size:11.5px;color:var(--heading);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.brow .btid{font-family:var(--font-data);font-size:9px;color:var(--faint)}
.brow .bbar{height:12px;border-radius:6px;background:var(--border-2);overflow:hidden}
.brow .bbar i{display:block;height:100%;border-radius:6px;background:var(--c-red-tx);opacity:.55}
.brow .bc{font-family:var(--font-data);font-size:12px;font-weight:600;color:var(--c-red-tx);text-align:right}
.bhint{margin:12px 0 0;font-size:11.5px;color:var(--faint);line-height:1.5}
.atypes{display:flex;align-items:flex-end;gap:20px;padding:16px;min-height:110px}
.atype{display:flex;flex-direction:column;align-items:center;gap:4px}
.acol{width:34px;border-radius:6px 6px 0 0;transition:height var(--t) var(--ease)}
.an{font-family:var(--font-data);font-size:13px;font-weight:600;color:var(--heading)}
.ac{font-size:10.5px;color:var(--muted)}
/* Journal — tableau dense (maquette) */
.table-wrap{overflow-x:auto}
table.dense{width:100%;border-collapse:collapse;font-size:12.5px}
table.dense thead th{text-align:left;padding:9px 12px;font-family:var(--font-eyebrow);font-size:10.5px;
  font-weight:var(--eyebrow-weight);letter-spacing:.05em;text-transform:uppercase;color:var(--muted);
  background:var(--surface-2);border-bottom:1px solid var(--border)}
table.dense tbody td{padding:9px 12px;border-bottom:1px solid var(--border-2);vertical-align:middle}
table.dense tbody tr:last-child td{border-bottom:0}
table.dense tbody tr:hover{background:var(--surface-2)}
table.dense .num{font-family:var(--font-data);text-align:right;font-variant-numeric:tabular-nums;width:44px}
.mono-cell{font-family:var(--font-data);font-size:11px;color:var(--faint);white-space:nowrap}
table.dense thead th .tz{text-transform:none;letter-spacing:0;color:var(--faint);font-weight:400}
.list-empty{padding:34px 16px;text-align:center;color:var(--muted);font-size:12.5px}
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} .cols{grid-template-columns:1fr} }
</style>
