<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLabels } from '../composables/useLabels'
import { api } from '../api/client'

// KPI + Répartition de la page Organisations. Les agrégats sont calculés côté serveur
// (/analytics/organisations, scopé RLS) et reflètent les filtres du tableau, passés en
// props par OrganisationsView. Aucun état de filtre dupliqué ici. Calqué sur
// RessourcesStats (mêmes classes/tokens) — barres horizontales, pas de radar.
const props = defineProps({
  fRoles: { type: Array, default: () => [] },
  fStatuts: { type: Array, default: () => [] },
  fSecteurs: { type: Array, default: () => [] },
  fTlp: { type: Array, default: () => [] },
})

const { t } = useI18n()
const { enumLabel } = useLabels()

const ROLES = ['client', 'prestataire', 'interne']
const SECTEUR_TOP = 8

const data = ref(null)

async function load() {
  const p = new URLSearchParams()
  props.fRoles.forEach((v) => p.append('role', v))
  props.fStatuts.forEach((v) => p.append('statut', v))
  props.fSecteurs.forEach((v) => p.append('secteur', v))
  props.fTlp.forEach((v) => p.append('tlp', v))
  const qs = p.toString()
  try {
    data.value = await api.get('/analytics/organisations' + (qs ? '?' + qs : ''))
  } catch { /* garder l'affichage précédent en cas d'erreur transitoire */ }
}

// Debounce : les filtres changent par à-coups (chips, RefacSelect) ; coalescer les refetch.
let timer = null
function scheduleLoad() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(load, 250)
}
watch(() => [props.fRoles, props.fStatuts, props.fSecteurs, props.fTlp], scheduleLoad, { deep: true })
onMounted(load)

const round = (n) => Math.round(n)
const pct = (n, d) => (d ? round((n / d) * 100) : 0)

const total = computed(() => data.value?.total || 0)
const byRole = computed(() => data.value?.by_role || {})
const byStatut = computed(() => data.value?.by_statut || {})
const bySecteur = computed(() => data.value?.by_secteur || {})
const coverage = computed(() => data.value?.coverage || { audited: 0, with_apps: 0, with_ress: 0 })

const clients = computed(() => byRole.value.client || 0)
const prestataires = computed(() => byRole.value.prestataire || 0)
const internes = computed(() => byRole.value.interne || 0)
const inactives = computed(() => byStatut.value.inactif || 0)
const secteurCount = computed(() => Object.keys(bySecteur.value).length)

const roleBars = computed(() => ROLES.map((r) => {
  const c = byRole.value[r] || 0
  return { key: r, count: c, width: pct(c, total.value) }
}))

// Secteurs présents, triés par effectif décroissant, tronqués au top N pour rester lisible.
const secteurBars = computed(() => Object.entries(bySecteur.value)
  .sort((a, b) => b[1] - a[1])
  .slice(0, SECTEUR_TOP)
  .map(([key, count]) => ({ key, count, width: pct(count, total.value) })))

// Accordéon : replié par défaut, choix mémorisé localement.
const STORE_KEY = 'organisations.repartition.open'
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
        <div class="klab">{{ t('views.organisations.kpi.organisations') }}</div>
        <div class="kpi-value">{{ total }}</div>
        <div class="kpi-foot">{{ t('views.organisations.kpi.organisations_foot', { c: clients, p: prestataires, i: internes }) }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.organisations.kpi.sous_audit') }}</div>
        <div class="kpi-value">{{ coverage.audited }}<span class="u">/{{ total }}</span></div>
        <div class="kpi-foot">{{ t('views.organisations.kpi.sous_audit_foot', { pct: pct(coverage.audited, total) }) }}</div>
      </div>
      <div class="kpi">
        <div class="klab">{{ t('views.organisations.kpi.inactives') }}</div>
        <div class="kpi-value" :class="{ warn: inactives }">{{ inactives }}</div>
        <div class="kpi-foot">
          {{ inactives
            ? t('views.organisations.kpi.inactives_foot', { pct: pct(inactives, total) })
            : t('views.organisations.kpi.inactives_ok') }}
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="head" @click="showRepartition = !showRepartition">
        <div class="ht">
          <span class="sec-title">{{ t('views.organisations.repartition.title') }}</span>
          <span class="hint">{{ t('views.organisations.repartition.resume', { clients, secteurs: secteurCount }) }}</span>
        </div>
        <span class="chev">{{ showRepartition ? '⌃' : '⌄' }}</span>
      </div>
      <div v-if="showRepartition" class="body-wrap">
        <div class="sec-desc">{{ t('views.organisations.repartition.desc') }}</div>
        <div class="split">
          <div class="col">
            <div class="sub">{{ t('views.organisations.repartition.par_role') }}</div>
            <div class="cbody">
              <div v-for="b in roleBars" :key="b.key" class="bar-row">
                <span class="bl">{{ enumLabel(b.key) }}</span>
                <span class="track"><span class="fill" :style="{ width: b.width + '%' }"></span></span>
                <span class="bn">{{ b.count }}<span class="pct">({{ b.width }} %)</span></span>
              </div>
            </div>
          </div>
          <div class="col">
            <div class="sub">{{ t('views.organisations.repartition.par_secteur') }}</div>
            <div class="cbody">
              <div v-if="!secteurBars.length" class="empty">{{ t('views.organisations.repartition.no_secteur') }}</div>
              <div v-for="b in secteurBars" :key="b.key" class="bar-row sect">
                <span class="bl" :title="enumLabel(b.key)">{{ enumLabel(b.key) }}</span>
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
.sec-desc{font-size:12px;color:var(--muted);margin:12px 0 20px;line-height:1.4}
.split{display:grid;grid-template-columns:1fr 1fr;gap:clamp(32px,6%,80px);align-items:start}
.col{display:flex;flex-direction:column}
.col .sub{font-family:var(--font-eyebrow);font-size:11px;color:var(--faint);font-weight:var(--eyebrow-weight);text-transform:uppercase;letter-spacing:.04em;min-height:15px}
.col .cbody{flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:10px;gap:2px}
.bar-row{display:grid;grid-template-columns:92px 1fr 66px;align-items:center;gap:8px;margin:5px 0}
.bar-row.sect{grid-template-columns:minmax(90px,150px) 1fr 66px}
.bar-row .bl{font-size:11.5px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.track{display:block;height:8px;background:var(--c-violet-bg);border-radius:99px;overflow:hidden}
.fill{display:block;height:100%;background:var(--violet);border-radius:99px}
.bn{font-size:12px;color:var(--heading);font-weight:600;text-align:right}
.bn .pct{font-size:11.5px;color:var(--muted);font-weight:400;margin-left:3px}
.empty{font-size:12px;color:var(--muted)}
@media (max-width:820px){ .kpis{grid-template-columns:repeat(2,1fr)} .split{grid-template-columns:1fr;gap:20px} }
</style>
