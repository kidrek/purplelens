<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { useUiStore } from '../stores/ui'
import { api } from '../api/client'
import { useLabels } from '../composables/useLabels'
const { t } = useI18n()
const { enumLabel } = useLabels()

const d = ref(null)
const ui = useUiStore()
const loading = ref(true)
const error = ref(null)

const VERDICTS = [
  { k: 'prevented', label: 'Prévenu', color: 'var(--green)' },
  { k: 'alerted', label: 'Alerté', color: 'var(--cyan)' },
  { k: 'logged', label: 'Journalisé', color: 'var(--amber)' },
  { k: 'no_telemetry', label: 'Sans télémétrie', color: 'var(--red)' },
  { k: 'not_tested', label: 'Non testé', color: 'var(--faint)' },
]
const SEV = [
  { k: 'critique', label: 'Critique', color: 'var(--red)' },
  { k: 'haute', label: 'Haute', color: 'var(--amber)' },
  { k: 'moyenne', label: 'Moyenne', color: 'var(--cyan)' },
  { k: 'basse', label: 'Basse', color: 'var(--green)' },
]
const AUDIT_TONE = { purple_team: 'var(--violet)', red_team: 'var(--red)', pentest: 'var(--cyan)', bas: 'var(--amber)' }

// Libellés courts des tactiques (bande kill-chain).
const TAC_LABEL = {
  'reconnaissance': 'Recon', 'resource-development': 'Ressources', 'initial-access': 'Accès initial',
  'execution': 'Exécution', 'persistence': 'Persistance', 'privilege-escalation': 'Élév. privilèges',
  'defense-evasion': 'Évasion', 'credential-access': 'Identifiants', 'discovery': 'Découverte',
  'lateral-movement': 'Latéralisation', 'collection': 'Collecte', 'command-and-control': 'C2',
  'exfiltration': 'Exfiltration', 'impact': 'Impact',
}
const tacLabel = (t) => TAC_LABEL[t] || t

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

const postureTotal = computed(() => {
  const v = d.value?.posture?.verdicts || {}
  return Object.values(v).reduce((a, b) => a + b, 0) || 1
})
const verdictPct = (k) => Math.round(((d.value?.posture?.verdicts?.[k] || 0) / postureTotal.value) * 100)

const vulnTotal = computed(() => d.value?.vulnerabilities?.total || 0)
const sevPct = (k) => {
  const n = d.value?.vulnerabilities?.by_severity?.[k] || 0
  return vulnTotal.value ? Math.round((n / vulnTotal.value) * 100) : 0
}
const auditEntries = computed(() => Object.entries(d.value?.audits_by_type || {}))
const auditMax = computed(() => Math.max(1, ...auditEntries.value.map(([, n]) => n)))

const fmtEvent = (e) => e.replace(/\./g, ' · ')
const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '')

watch(() => ui.activeClient, load)
onMounted(load)
</script>

<template>
  <div>
    <div class="eyebrow">{{ t('views.cockpit.eyebrow') }}</div>
    <h1>{{ t('views.cockpit.title') }}</h1>

    <p v-if="loading" class="muted">Chargement…</p>
    <p v-else-if="error" class="err">{{ error }}</p>

    <template v-else-if="d">
      <div class="kpis">
        <div class="kpi">
          <div class="kpi-label">Taux de détection moyen</div>
          <div class="kpi-value">{{ d.kpis.detection_rate ?? '—' }}<span v-if="d.kpis.detection_rate != null" class="u">%</span></div>
          <div class="kpi-foot">{{ d.posture.caught }} / {{ d.posture.tested }} étapes couvertes</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Angles morts</div>
          <div class="kpi-value" :class="{ warn: d.kpis.blind_spots > 0 }">{{ d.kpis.blind_spots }}</div>
          <div class="kpi-foot">étapes jouées sans télémétrie</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Criticals hors SLA</div>
          <div class="kpi-value" :class="{ bad: d.kpis.p1_breached > 0 }">{{ d.kpis.p1_breached }}</div>
          <div class="kpi-foot">P1 au-delà de l'échéance</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Audits</div>
          <div class="kpi-value">{{ d.kpis.audits }}</div>
          <div class="kpi-foot">{{ d.exercises }} exercice(s) Purple</div>
        </div>
      </div>

      <!-- Couverture par tactique MITRE — ordre kill-chain -->
      <section v-if="d.tactic_coverage?.length" class="panel wide">
        <div class="p-head"><span class="p-title">Couverture par tactique MITRE</span>
          <span class="p-note">ordre kill-chain</span></div>
        <div class="tstrip">
          <div v-for="t in d.tactic_coverage" :key="t.tactic" :class="['tcell', 't-' + t.state]"
               :title="t.detected + '/' + t.total + ' techniques détectées'">
            <div class="tname">{{ tacLabel(t.tactic) }}</div>
            <div class="tfoot"><span class="tbead"></span><span class="tfrac">{{ t.detected }}/{{ t.total }}</span>
              <span class="tlbl">{{ t.state === 'detected' ? 'couvert' : (t.state === 'gap' ? 'écart' : 'partiel') }}</span></div>
          </div>
        </div>
      </section>

      <!-- Tendance du taux de détection -->
      <section v-if="trendGeo" class="panel wide">
        <div class="p-head"><span class="p-title">Tendance du taux de détection</span>
          <span class="p-note">dernier run par audit, cumulé</span></div>
        <div class="trend">
          <svg :viewBox="'0 0 ' + 560 + ' ' + 96" preserveAspectRatio="none" class="trend-svg">
            <polyline :points="trendGeo.line" fill="none" stroke="var(--violet-accent)" stroke-width="2" />
            <circle v-for="(pt, i) in trendGeo.dots" :key="i" :cx="pt.x" :cy="pt.y" r="3" fill="var(--violet-accent)" />
          </svg>
          <div class="trend-pts">
            <span v-for="(pt, i) in d.trend" :key="i" class="trend-pt"
                  :title="pt.caught + '/' + pt.tested + ' · ' + pt.audits + ' audits'">
              <span class="rl">{{ pt.date.slice(2, 7) }}</span><b>{{ pt.pct }}%</b>
            </span>
          </div>
        </div>
      </section>

      <div class="cols">
        <section class="panel">
          <div class="p-head"><span class="p-title">Posture défensive agrégée</span>
            <RouterLink class="link" to="/attack-matrix">Matrice ATT&CK →</RouterLink></div>
          <div class="bars">
            <div v-for="v in VERDICTS" :key="v.k" class="barrow">
              <span class="bl">{{ v.label }}</span>
              <div class="track"><div class="fill" :style="{ width: verdictPct(v.k) + '%', background: v.color }"></div></div>
              <span class="bn">{{ d.posture.verdicts[v.k] || 0 }}</span>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="p-head"><span class="p-title">Angles morts</span></div>
          <p v-if="!d.blind_techniques.length" class="muted sm">Aucun angle mort — toutes les étapes jouées ont laissé une trace.</p>
          <ul v-else class="blind">
            <li v-for="b in d.blind_techniques" :key="b.technique">
              <span class="code">{{ b.technique }}</span>
              <span class="dots"></span>
              <span class="cnt">{{ b.count }}×</span>
            </li>
          </ul>
        </section>
      </div>

      <div class="cols">
        <section class="panel">
          <div class="p-head"><span class="p-title">Vulnérabilités par sévérité</span>
            <RouterLink class="link" to="/vulnerabilities">Voir tout ({{ vulnTotal }}) →</RouterLink></div>
          <div class="bars">
            <div v-for="s in SEV" :key="s.k" class="barrow">
              <span class="bl">{{ s.label }}</span>
              <div class="track"><div class="fill" :style="{ width: sevPct(s.k) + '%', background: s.color }"></div></div>
              <span class="bn">{{ d.vulnerabilities.by_severity[s.k] || 0 }}</span>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="p-head"><span class="p-title">Audits par type</span></div>
          <p v-if="!auditEntries.length" class="muted sm">Aucun audit.</p>
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
        <div class="p-head"><span class="p-title">Activité récente</span>
          <RouterLink class="link" to="/journal">Journal complet →</RouterLink></div>
        <table class="jtable">
          <thead><tr><th>#</th><th>Événement</th><th>Acteur</th><th>Horodatage</th></tr></thead>
          <tbody>
            <tr v-for="j in d.journal" :key="j.seq">
              <td class="seq">{{ j.seq }}</td>
              <td class="ev">{{ fmtEvent(j.event_type) }}</td>
              <td>{{ j.actor || '—' }}</td>
              <td class="ts">{{ fmtTime(j.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>

<style scoped>
.sm{font-size:12.5px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:14px 16px}
.kpi-label{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.kpi-value{font-family:var(--font-data);font-size:30px;font-weight:600;color:var(--heading);line-height:1.1;margin-top:4px}
.kpi-value .u{font-size:16px;color:var(--muted);margin-left:2px}
.kpi-value.warn{color:var(--amber)} .kpi-value.bad{color:var(--red)}
.kpi-foot{font-size:11px;color:var(--muted);margin-top:3px}
.panel.wide{margin-bottom:12px}
.p-note{font-size:10.5px;color:var(--faint);font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em}
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
.bars{padding:14px 16px;display:flex;flex-direction:column;gap:9px}
.barrow{display:flex;align-items:center;gap:10px}
.bl{width:110px;font-size:12px;color:var(--muted);flex:0 0 auto}
.track{flex:1;height:9px;background:var(--surface-3);border-radius:99px;overflow:hidden}
.fill{height:100%;border-radius:99px;transition:width var(--t) var(--ease);min-width:2px}
.bn{width:34px;text-align:right;font-family:var(--font-data);font-size:12px;color:var(--text)}
.blind{list-style:none;margin:0;padding:10px 16px 14px;display:flex;flex-direction:column;gap:7px}
.blind li{display:flex;align-items:center;gap:8px;font-size:12.5px}
.blind .code{font-family:var(--font-data);font-weight:600;color:var(--red)}
.blind .dots{flex:1;border-bottom:1px dotted var(--border)}
.blind .cnt{font-family:var(--font-data);color:var(--muted)}
.atypes{display:flex;align-items:flex-end;gap:20px;padding:16px;min-height:110px}
.atype{display:flex;flex-direction:column;align-items:center;gap:4px}
.acol{width:34px;border-radius:6px 6px 0 0;transition:height var(--t) var(--ease)}
.an{font-family:var(--font-data);font-size:13px;font-weight:600;color:var(--heading)}
.ac{font-size:10.5px;color:var(--muted)}
.jtable{width:100%;border-collapse:collapse}
.jtable th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--faint);padding:8px 16px;border-bottom:1px solid var(--border-2)}
.jtable td{padding:8px 16px;border-bottom:1px solid var(--border-2);font-size:12.5px}
.jtable tr:last-child td{border-bottom:0}
.jtable .seq{font-family:var(--font-data);color:var(--faint);width:44px}
.jtable .ev{font-family:var(--font-data);color:var(--heading)}
.jtable .ts{color:var(--muted);white-space:nowrap;font-family:var(--font-data);font-size:11.5px}
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} .cols{grid-template-columns:1fr} }
</style>
