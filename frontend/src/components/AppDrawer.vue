<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import { useLabels } from '../composables/useLabels'
import { useOrgNames } from '../composables/useOrgNames'
import { icons } from '../icons'
import DetailDrawer from './DetailDrawer.vue'
import AttckTtpMatrix from './AttckTtpMatrix.vue'
const { t, te, locale } = useI18n()
const { enumLabel } = useLabels()
const { preload: preloadOrgs, orgName } = useOrgNames()

// Détail d'une application enrichi de sa posture Purple Team agrégée (mini-cockpit
// contextualisé à l'app) : KPI, couverture MITRE, tendance, top audits, vulns actives.
// Les données de posture sont calculées côté serveur (/analytics/application/{id}),
// cloisonnées RLS ; le drawer reste en lecture seule.
const props = defineProps({ app: { type: Object, required: true } })
const emit = defineEmits(['close', 'edit'])

const CRIT_TONE = { critique: 'red', haute: 'amber', elevee: 'amber', moyenne: 'cyan', basse: 'green', faible: 'green' }
const SEV_TONE = { critique: 'red', haute: 'amber', elevee: 'amber', moyenne: 'cyan', basse: 'green', faible: 'green' }
const AUDIT_TONE = { purple_team: 'violet', red_team: 'red', pentest: 'cyan', bas: 'amber' }
const a = computed(() => props.app)
const tags = computed(() => (Array.isArray(a.value.tags) ? a.value.tags : []))

// Organisation propriétaire (résolue côté client, toutes organisations confondues).
const org = computed(() => orgName(a.value.client_id))
// Initiales pour le glyphe : 2 premières lettres significatives du nom (repli sur le code).
const initials = computed(() => {
  const src = String(a.value.nom || a.value.code || '?').trim()
  const words = src.split(/\s+/).filter(Boolean)
  const raw = words.length >= 2 ? words[0][0] + words[1][0] : src.slice(0, 2)
  return raw.toUpperCase()
})
// Valeur métier bornée à 1..5 (pips) ; null/0 → non renseignée.
const valeurMetier = computed(() => {
  const n = Number(a.value.valeur_metier)
  return Number.isFinite(n) && n > 0 ? Math.min(5, Math.round(n)) : null
})

// Icônes des champs — style DA (viewBox 24, currentColor, stroke 1.7), rendues via v-html.
const META_ICONS = {
  type: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3" y="3" width="7" height="7" rx="1.5"/><path d="M14 4h6M14 8h6M6 14v6M3 17h6M14 14h6v6h-6z"/></svg>',
  version: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M3 12l9-9 9 9-9 9z"/><circle cx="12" cy="12" r="2.2"/></svg>',
  stack: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3 3 8l9 5 9-5-9-5Z"/><path d="M3 12l9 5 9-5M3 16l9 5 9-5"/></svg>',
  contact: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="8" r="3.4"/><path d="M5 20a7 7 0 0 1 14 0"/></svg>',
  url: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/></svg>',
  exposition: icons.shield,
  valeur: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8L3.5 9.2l5.9-.9Z"/></svg>',
  organisation: icons.building,
}

// ── Posture agrégée ─────────────────────────────────────────────────────────
const d = ref(null)
const loading = ref(true)
const error = ref(null)
const showMatrix = ref(false)

const tacLabel = (k) => (te('views.cockpit.tactics.' + k) ? t('views.cockpit.tactics.' + k) : k)
const critTone = (c) => CRIT_TONE[String(c || '').toLowerCase()] || 'gray'
const sevTone = (s) => SEV_TONE[String(s || '').toLowerCase()] || 'gray'
const auditTone = (c) => AUDIT_TONE[c] || 'violet'

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString(locale.value === 'en' ? 'en-GB' : 'fr-FR', { day: '2-digit', month: 'short', year: '2-digit' }) : '—')
const fmtMonth = (iso) => (iso ? new Date(iso).toLocaleDateString(locale.value === 'en' ? 'en-GB' : 'fr-FR', { month: 'short', year: '2-digit' }) : '')

const kpis = computed(() => d.value?.kpis || {})
const activeVulns = computed(() => d.value?.active_vulns || [])
const topAudits = computed(() => d.value?.top_audits || [])
const tacticCoverage = computed(() => d.value?.tactic_coverage || [])
const techniques = computed(() => d.value?.techniques || [])
const hasActivity = computed(() => (d.value?.kpis?.exercises || 0) > 0 || topAudits.value.length > 0)

// Courbe de tendance : polyline SVG des 5 derniers exercices (Y = 0-100).
const TREND_W = 520, TREND_H = 90
const trendGeo = computed(() => {
  const pts = d.value?.trend || []
  if (pts.length < 2) return null
  const xs = pts.map((_, i) => 14 + (TREND_W - 28) * (i / (pts.length - 1)))
  const ys = pts.map((pt) => 10 + (TREND_H - 26) * (1 - pt.pct / 100))
  return {
    line: xs.map((x, i) => `${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' '),
    dots: xs.map((x, i) => ({ x, y: ys[i] })),
  }
})

// Posture segmentée du dernier exercice Purple (barre + légende, repris du cockpit).
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
const postureLast = computed(() => d.value?.posture_last_exercise || null)
const posture = computed(() => {
  const v = postureLast.value?.verdicts || {}
  return {
    prev: v.prevented || 0,
    alert: v.alerted || 0,
    logged: v.logged || 0,
    blind: v.no_telemetry || 0,
    tested: postureLast.value?.tested || 0,
    caught: postureLast.value?.caught || 0,
    covPct: postureLast.value?.pct ?? 0,
  }
})
const segPct = (n) => Math.round((n / (posture.value.tested || 1)) * 100)

async function load() {
  loading.value = true; error.value = null
  try { d.value = await api.get('/analytics/application/' + a.value.id) }
  catch (e) { error.value = e.message || t('views.applications.drawer.load_error') }
  finally { loading.value = false }
}
onMounted(() => { load(); preloadOrgs() })
</script>

<template>
  <DetailDrawer wide :title="a.nom" :subtitle="a.code ? 'Application · ' + a.code : 'Application'" @close="emit('close')">
    <template #actions>
      <button class="btn slim" @click="emit('edit', a)">{{ t('common.edit') }}</button>
    </template>

    <div class="badges">
      <span v-if="a.criticite" :class="['pill', 'pill-' + critTone(a.criticite)]">{{ t('fields.criticite') }} {{ a.criticite }}</span>
      <span v-if="a.exposition" class="pill pill-amber">{{ a.exposition }}</span>
      <span v-if="a.statut" class="pill pill-gray">{{ a.statut }}</span>
      <span v-if="a.tlp" class="pill pill-gray">TLP:{{ a.tlp }}</span>
    </div>

    <!-- ── Carte d'identité (au-dessus des KPI) ─────────────────────────── -->
    <section class="id-card">
      <div class="id-head">
        <div class="id-glyph">{{ initials }}</div>
        <div class="id-org">
          <div class="id-org-lbl"><span class="id-ico" v-html="META_ICONS.organisation"></span>{{ t('views.applications.drawer.organisation') }}</div>
          <div class="id-org-name">{{ org }}</div>
          <div class="id-org-sub">{{ [a.type, a.code, a.version].filter(Boolean).join(' · ') || '—' }}</div>
        </div>
      </div>

      <div class="id-grid">
        <div class="id-cell">
          <div class="id-lbl"><span class="id-ico" v-html="META_ICONS.type"></span>{{ t('fields.type') }}</div>
          <div class="id-val">{{ a.type || '—' }}</div>
        </div>
        <div class="id-cell">
          <div class="id-lbl"><span class="id-ico" v-html="META_ICONS.version"></span>{{ t('fields.version') }}</div>
          <div class="id-val">{{ a.version || '—' }}</div>
        </div>
        <div class="id-cell">
          <div class="id-lbl"><span class="id-ico" v-html="META_ICONS.stack"></span>{{ t('fields.stack') }}</div>
          <div class="id-val">{{ a.stack || '—' }}</div>
        </div>
        <div class="id-cell">
          <div class="id-lbl"><span class="id-ico" v-html="META_ICONS.contact"></span>{{ t('fields.contact_metier') }}</div>
          <div class="id-val">{{ a.contact_metier || '—' }}</div>
        </div>
        <div class="id-cell">
          <div class="id-lbl"><span class="id-ico" v-html="META_ICONS.url"></span>{{ t('fields.url') }}</div>
          <div class="id-val"><a v-if="a.url" :href="a.url" target="_blank" rel="noopener" class="a">{{ a.url }}</a><span v-else>—</span></div>
        </div>
        <div class="id-cell">
          <div class="id-lbl"><span class="id-ico" v-html="META_ICONS.exposition"></span>{{ t('fields.exposition') }}</div>
          <div class="id-val"><span v-if="a.exposition" class="pill pill-amber">{{ a.exposition }}</span><span v-else>—</span></div>
        </div>
        <div class="id-cell id-cell-wide">
          <div class="id-lbl"><span class="id-ico" v-html="META_ICONS.valeur"></span>{{ t('fields.valeur_metier') }}</div>
          <div class="id-val id-val-row">
            <template v-if="valeurMetier">
              <span class="id-pips"><i v-for="n in 5" :key="n" :class="['pip', { on: n <= valeurMetier }]"></i></span>
              <span class="id-pips-n">{{ valeurMetier }}<span class="id-pips-d">/5</span></span>
            </template>
            <span v-else>—</span>
          </div>
        </div>
      </div>

      <div v-if="tags.length" class="id-tags">
        <span class="id-tags-lbl">{{ t('fields.tags') }}</span>
        <span v-for="tg in tags" :key="tg" class="chip">{{ tg }}</span>
      </div>
    </section>

    <!-- ── Posture agrégée ──────────────────────────────────────────────── -->
    <p v-if="loading" class="muted sm posture-loading">{{ t('common.loading') }}</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <template v-else-if="d">
      <div class="sec-t">{{ t('views.applications.drawer.posture_eyebrow') }}</div>

      <div class="kpis">
        <div class="kpi">
          <div class="kpi-label">{{ t('views.applications.drawer.kpi_detection') }}</div>
          <div class="kpi-value">{{ kpis.detection_rate ?? '—' }}<span v-if="kpis.detection_rate != null" class="u">%</span></div>
          <div class="kpi-foot">{{ t('views.applications.drawer.kpi_detection_foot', { caught: d.posture.caught, tested: d.posture.tested }) }}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">{{ t('views.applications.drawer.kpi_blind') }}</div>
          <div class="kpi-value" :class="{ warn: kpis.blind_spots > 0 }">{{ kpis.blind_spots ?? 0 }}</div>
          <div class="kpi-foot">{{ t('views.applications.drawer.kpi_blind_foot') }}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">{{ t('views.applications.drawer.kpi_crit') }}</div>
          <div class="kpi-value" :class="{ bad: kpis.vuln_critical_active > 0 }">{{ kpis.vuln_critical_active ?? 0 }}</div>
          <div class="kpi-foot">{{ t('views.applications.drawer.kpi_crit_foot', { n: activeVulns.length }) }}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">{{ t('views.applications.drawer.kpi_audits') }}</div>
          <div class="kpi-value">{{ kpis.audits ?? 0 }}</div>
          <div class="kpi-foot">{{ t('views.applications.drawer.kpi_audits_foot', { n: kpis.exercises ?? 0 }) }}</div>
        </div>
      </div>

      <p v-if="!hasActivity" class="muted sm empty-note">{{ t('views.applications.drawer.empty_posture') }}</p>

      <!-- Posture agrégée — barre segmentée du dernier exercice Purple -->
      <section v-if="postureLast && posture.tested > 0" class="panel">
        <div class="p-head"><span class="p-title">{{ t('views.cockpit.posture.title') }}</span>
          <span class="p-note">{{ t('views.applications.drawer.posture_panel_note') }}</span></div>
        <div class="pbody">
          <div class="pcov">{{ posture.covPct }} %</div>
          <div class="pcov-sub">{{ posture.caught }} / {{ posture.tested }} {{ t('views.cockpit.posture.testedN') }}</div>
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
      </section>

      <!-- Couverture par tactique MITRE -->
      <section v-if="tacticCoverage.length" class="panel">
        <div class="p-head"><span class="p-title">{{ t('views.applications.drawer.mitre_title') }}</span>
          <span class="p-note">{{ t('views.applications.drawer.mitre_note') }}</span></div>
        <div class="tstrip">
          <div v-for="tc in tacticCoverage" :key="tc.tactic" :class="['tcell', 't-' + tc.state]"
               :title="t('views.cockpit.tacticsPanel.cellTitle', { detected: tc.detected, total: tc.total })">
            <div class="tname">{{ tacLabel(tc.tactic) }}</div>
            <div class="tfoot"><span class="tbead"></span><span class="tfrac">{{ tc.detected }}/{{ tc.total }}</span></div>
          </div>
        </div>
        <div v-if="techniques.length" class="matrix-wrap">
          <button class="btn slim ghost" @click="showMatrix = !showMatrix">
            {{ showMatrix ? t('views.applications.drawer.matrix_hide') : t('views.applications.drawer.matrix_show') }}
            <span class="chev">{{ showMatrix ? '⌃' : '⌄' }}</span>
          </button>
          <AttckTtpMatrix v-if="showMatrix" :techniques="techniques"
                          :description="t('views.applications.drawer.matrix_desc')" />
        </div>
      </section>

      <!-- Tendance du taux de détection (5 derniers exercices) -->
      <section v-if="trendGeo" class="panel">
        <div class="p-head"><span class="p-title">{{ t('views.applications.drawer.trend_title') }}</span>
          <span class="p-note">{{ t('views.applications.drawer.trend_note') }}</span></div>
        <div class="trend">
          <svg :viewBox="'0 0 ' + TREND_W + ' ' + TREND_H" preserveAspectRatio="none" class="trend-svg">
            <polyline :points="trendGeo.line" fill="none" stroke="var(--violet-accent)" stroke-width="2" />
            <circle v-for="(pt, i) in trendGeo.dots" :key="i" :cx="pt.x" :cy="pt.y" r="3" fill="var(--violet-accent)" />
          </svg>
          <div class="trend-pts">
            <span v-for="(pt, i) in d.trend" :key="i" class="trend-pt"
                  :title="t('views.cockpit.trend.pointTitle', { caught: pt.caught, tested: pt.tested, audits: 1 })">
              <span class="rl">{{ fmtMonth(pt.date) }}</span><b>{{ pt.pct }}%</b>
            </span>
          </div>
        </div>
      </section>

      <!-- Top 5 audits réalisés -->
      <section v-if="topAudits.length" class="panel">
        <div class="p-head"><span class="p-title">{{ t('views.applications.drawer.audits_title') }}</span></div>
        <div class="table-wrap">
          <table class="dense">
            <thead><tr>
              <th>{{ t('views.applications.drawer.col_audit') }}</th>
              <th>{{ t('views.applications.drawer.col_type') }}</th>
              <th>{{ t('views.applications.drawer.col_auditor') }}</th>
              <th>{{ t('views.applications.drawer.col_date') }}</th>
              <th class="num">{{ t('views.applications.drawer.col_detection') }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="au in topAudits" :key="au.id">
                <td>{{ au.nom }}</td>
                <td><span :class="['chip', 'sm', auditTone(au.categorie)]">{{ enumLabel(au.categorie) }}</span></td>
                <td class="muted">{{ au.auditeurs.length ? au.auditeurs.join(', ') : '—' }}</td>
                <td class="mono-cell">{{ fmtDate(au.date) }}</td>
                <td class="num mono-cell" :class="au.detection_rate == null ? 'muted' : ''">{{ au.detection_rate != null ? au.detection_rate + '%' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Vulnérabilités actives (les plus récentes en tête) -->
      <section class="panel">
        <div class="p-head"><span class="p-title">{{ t('views.applications.drawer.vulns_title') }}
          <span class="count-badge">{{ activeVulns.length }}</span></span></div>
        <div v-if="activeVulns.length" class="table-wrap">
          <table class="dense">
            <thead><tr>
              <th>{{ t('views.applications.drawer.col_vuln') }}</th>
              <th>{{ t('views.applications.drawer.col_severity') }}</th>
              <th>{{ t('views.applications.drawer.col_status') }}</th>
              <th>{{ t('views.applications.drawer.col_created') }}</th>
              <th>{{ t('views.applications.drawer.col_sla') }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="v in activeVulns" :key="v.id">
                <td>{{ v.titre }}</td>
                <td><span :class="['pill', 'pill-' + sevTone(v.severite)]">{{ v.severite || '—' }}</span></td>
                <td class="muted">{{ enumLabel(v.statut) }}</td>
                <td class="mono-cell">{{ fmtDate(v.created_at) }}</td>
                <td class="mono-cell muted">{{ v.sla_niveau || '—' }}<span v-if="v.sla_echeance"> · {{ fmtDate(v.sla_echeance) }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="muted sm pad">{{ t('views.applications.drawer.empty_vulns') }}</p>
      </section>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.slim{padding:3px 9px;font-size:11.5px}
.btn.ghost{background:var(--surface);border:1px solid var(--border);color:var(--violet-accent)}
.btn.ghost .chev{margin-left:4px;font-size:10px}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}
.sm{font-size:12.5px}
.posture-loading{margin:4px 0 16px}
.empty-note{margin:2px 0 14px}
.pad{padding:12px 16px;margin:0}
.sec-t{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight);margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--border-2)}
.a{color:var(--violet-accent);text-decoration:none} .a:hover{text-decoration:underline}
.chip{display:inline-block;background:var(--surface-3);border:1px solid var(--border-2);border-radius:var(--r-pill);padding:1px 8px;font-size:11.5px;margin:0 4px 4px 0}
/* Carte d'identité de l'application */
.id-card{border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:16px}
.id-head{display:flex;align-items:center;gap:12px;padding:14px 15px;background:var(--surface-2);border-bottom:1px solid var(--border-2)}
.id-glyph{width:42px;height:42px;flex:0 0 auto;border-radius:10px;background:var(--violet-soft);color:var(--violet-accent);display:flex;align-items:center;justify-content:center;font-family:var(--font-display);font-weight:600;font-size:15px}
.id-org{min-width:0}
.id-org-lbl{display:flex;align-items:center;gap:6px;font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.id-org-name{font-family:var(--font-display);font-size:15px;font-weight:600;color:var(--heading);margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.id-org-sub{font-size:11.5px;color:var(--muted);margin-top:1px}
.id-grid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--border-2)}
.id-cell{background:var(--surface);padding:11px 15px;min-width:0}
.id-cell-wide{grid-column:1 / -1}
.id-lbl{display:flex;align-items:center;gap:6px;font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.id-val{font-size:13px;color:var(--text);margin-top:4px;overflow:hidden;text-overflow:ellipsis}
.id-val .a{white-space:nowrap}
.id-val-row{display:flex;align-items:center;justify-content:space-between;gap:10px}
.id-ico{display:inline-flex;width:13px;height:13px;color:var(--faint)}
.id-ico :deep(svg){width:100%;height:100%;display:block}
.id-pips{display:inline-flex;gap:3px}
.id-pips .pip{width:9px;height:9px;border-radius:50%;background:var(--border-2)}
.id-pips .pip.on{background:var(--violet-accent)}
.id-pips-n{font-family:var(--font-data);font-size:12px;font-weight:600;color:var(--heading)}
.id-pips-d{color:var(--faint);font-weight:400}
.id-tags{display:flex;flex-wrap:wrap;align-items:center;gap:7px;padding:11px 15px;border-top:1px solid var(--border-2)}
.id-tags .chip{margin:0}
.id-tags-lbl{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10px;color:var(--faint);font-weight:var(--eyebrow-weight);margin-right:2px}
/* KPI (repris de CockpitView, DA) */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:0 0 14px}
.kpi{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-card);padding:12px 13px}
.kpi-label{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10px;color:var(--faint);font-weight:var(--eyebrow-weight)}
.kpi-value{font-family:var(--font-data);font-size:27px;font-weight:600;color:var(--heading);line-height:1.1;margin-top:3px}
.kpi-value .u{font-size:15px;color:var(--muted);margin-left:2px}
.kpi-value.warn{color:var(--amber)} .kpi-value.bad{color:var(--red)}
.kpi-foot{font-size:10.5px;color:var(--muted);margin-top:2px}
/* Panneaux */
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-panel);padding:0;overflow:hidden;margin-bottom:12px}
.p-head{display:flex;align-items:center;justify-content:space-between;padding:11px 14px;border-bottom:1px solid var(--border-2)}
.p-title{font-family:var(--font-display);font-size:13.5px;font-weight:600;color:var(--heading)}
.p-note{font-size:10px;color:var(--faint);font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em}
.count-badge{display:inline-flex;align-items:center;justify-content:center;min-width:18px;height:18px;border-radius:99px;background:var(--c-red-bg);color:var(--c-red-tx);font-size:11px;font-family:var(--font-data);padding:0 6px;margin-left:6px}
/* Posture agrégée — barre segmentée (repris de CockpitView, DA) */
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
/* Bande tactique */
.tstrip{display:flex;gap:6px;overflow-x:auto;padding:11px 13px}
.tcell{flex:1;min-width:82px;border:1px solid var(--border-2);border-radius:var(--r-mini);padding:7px 8px;border-top:3px solid var(--border-2)}
.tcell .tname{font-size:10.5px;font-weight:600;color:var(--heading);line-height:1.2}
.tfoot{display:flex;align-items:center;gap:5px;margin-top:5px}
.tbead{width:7px;height:7px;border-radius:50%}
.tfrac{font-family:var(--font-data);font-size:11px;color:var(--heading);font-weight:600}
.tcell.t-detected{border-top-color:var(--green)} .tcell.t-detected .tbead{background:var(--green)}
.tcell.t-partial{border-top-color:var(--amber)} .tcell.t-partial .tbead{background:var(--amber)}
.tcell.t-gap{border-top-color:var(--red)} .tcell.t-gap .tbead{background:var(--red)}
.matrix-wrap{padding:0 14px 14px}
.matrix-wrap .btn{margin-top:2px}
/* Tendance */
.trend{padding:12px 14px}
.trend-svg{display:block;width:100%;height:90px;overflow:visible}
.trend-pts{display:flex;justify-content:space-between;margin-top:6px}
.trend-pt{font-family:var(--font-data);font-size:10px;color:var(--muted);text-align:center;flex:1;min-width:0}
.trend-pt b{display:block;color:var(--heading);font-size:12px;font-weight:600}
.trend-pt .rl{color:var(--faint);font-size:9px}
/* Tableaux denses */
.table-wrap{overflow-x:auto}
table.dense{width:100%;border-collapse:collapse;font-size:12.5px}
table.dense thead th{text-align:left;padding:9px 12px;font-family:var(--font-eyebrow);font-size:10px;font-weight:var(--eyebrow-weight);letter-spacing:.05em;text-transform:uppercase;color:var(--muted);background:var(--surface-2);border-bottom:1px solid var(--border)}
table.dense thead th.num{text-align:right}
table.dense tbody td{padding:8px 12px;border-bottom:1px solid var(--border-2);vertical-align:middle;color:var(--text)}
table.dense tbody tr:last-child td{border-bottom:0}
table.dense tbody tr:hover{background:var(--surface-2)}
table.dense td.num{text-align:right;font-variant-numeric:tabular-nums}
table.dense td.muted{color:var(--muted)}
.mono-cell{font-family:var(--font-data);font-size:11px;color:var(--faint);white-space:nowrap}
</style>
