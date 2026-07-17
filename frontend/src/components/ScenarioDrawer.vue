<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import DetailDrawer from './DetailDrawer.vue'
import CorpusArticleDrawer from './CorpusArticleDrawer.vue'
import AttckTtpMatrix from './AttckTtpMatrix.vue'
import { api } from '../api/client'
import { useRefNames } from '../composables/useRefNames'
import { attackUrl, d3fendUrl } from '../utils/mitreLinks'
import { icons } from '../icons'
const { t } = useI18n()

// Détail d'un scénario de menace — thème et ordre repris de la maquette (captures
// fournies) : KPI (acteur/TTPs/couverture/audits), identité, TTPs ATT&CK (tactiques +
// grille de techniques), étapes offensives (chaîne détaillée), contre-mesures D3FEND
// (liste plate, badge de catégorie), contexte d'utilisation (clients/applications/
// audits/exercices), rapport STIX (aperçu + copier/télécharger).
// Prop nommée "record" : contrat générique qu'EntityTable utilise pour tout composant
// passé via :drawer="...".
const props = defineProps({ record: { type: Object, required: true } })
const emit = defineEmits(['close', 'edit'])
const { preload, refName, refMeta } = useRefNames()

const usage = ref(null)           // { audits, clients, applications, exercices, coverage }
const steps = ref([])             // chaîne d'étapes offensives (table scenario_step)
const stepsLoaded = ref(false)
const d3fendCategoryFallback = { Detect: 'Detect' }
const stixBundle = ref(null)
const stixText = ref('')
const stixBusy = ref(false)
const copyMsg = ref(false)
const corpusOpen = ref(false) // "Corpus" (DA §4.6) : ouvre corp-cti-scenario en overlay

const TACTIC_LABEL = {
  'reconnaissance': 'Reconnaissance', 'resource-development': 'Développement de ressources',
  'initial-access': 'Accès initial', 'execution': 'Exécution', 'persistence': 'Persistance',
  'privilege-escalation': 'Élévation de privilèges', 'defense-evasion': 'Évasion défensive',
  'credential-access': 'Accès aux identifiants', 'discovery': 'Découverte',
  'lateral-movement': 'Mouvement latéral', 'collection': 'Collecte',
  'command-and-control': 'Commande & contrôle', 'exfiltration': 'Exfiltration', 'impact': 'Impact',
}
const ENGAGEMENT_LABEL = { 'red-team': 'Red', 'purple-team': 'Purple', 'tabletop': 'Tabletop', 'assumed-breach': 'Assumed Breach' }
const ENGAGEMENT_TONE = { 'red-team': 'red', 'purple-team': 'violet', 'tabletop': 'cyan', 'assumed-breach': 'amber' }
const TLP_TONE = { RED: 'red', AMBER: 'amber', GREEN: 'green', WHITE: 'gray', CLEAR: 'gray' }
const CATEGORY_TONE = { Harden: 'green', Detect: 'blue', Isolate: 'amber', Deceive: 'violet', Evict: 'red', Restore: 'cyan' }

const s = computed(() => props.record)
const techniques = computed(() => s.value.techniques || [])
const d3fend = computed(() => s.value.d3fend || [])

// Techniques ATT&CK de la matrice/KPI = techniques distinctes des étapes offensives
// réellement chargées (scenario_step). On ne s'appuie plus sur scenario.techniques,
// champ stocké et dédoublonné qui peut être en retard sur la chaîne d'étapes (import
// STIX, étapes semées hors du chemin `etapes`). Repli sur le champ stocké tant que les
// étapes ne sont pas chargées ou pour un scénario sans étapes détaillées.
const matrixTechniques = computed(() => {
  const out = []
  for (const st of steps.value) {
    const tq = st.technique
    if (tq && !out.includes(tq)) out.push(tq)
  }
  return out.length ? out : techniques.value
})

function categoryOf(extId) {
  return refMeta('d3fend', extId)?.category || d3fendCategoryFallback.Detect
}

onMounted(async () => {
  await preload(['attack', 'd3fend'])
  try { usage.value = await api.get(`/analytics/scenario-usage/${props.record.id}`) }
  catch { usage.value = { audits: [], clients: [], applications: [], exercices: [], coverage: { total: 0, covered: 0, gaps: 0, covered_pct: 0 } } }
  try {
    const rows = await api.list('scenario_steps', `?scenario_id=${props.record.id}`)
    steps.value = (Array.isArray(rows) ? rows : (rows.items ?? [])).slice().sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0))
  } catch { steps.value = [] }
  finally { stepsLoaded.value = true }
  loadStix()
})

async function loadStix() {
  stixBusy.value = true
  try {
    stixBundle.value = await api.get(`/stix/scenarios/${props.record.id}`)
    stixText.value = JSON.stringify(stixBundle.value, null, 2)
  } catch { stixBundle.value = null; stixText.value = '' }
  finally { stixBusy.value = false }
}
function downloadJson(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}
function exportStix() { if (stixBundle.value) downloadJson(stixBundle.value, `scenario-${s.value.id}.stix.json`) }
async function copyStix() {
  try { await navigator.clipboard.writeText(stixText.value) } catch { /* presse-papiers indisponible */ }
  copyMsg.value = true
  setTimeout(() => { copyMsg.value = false }, 1500)
}
</script>

<template>
  <DetailDrawer :title="s.nom" subtitle="Scénario de menace" wide @close="emit('close')">
    <template #actions>
      <button class="btn slim" @click="corpusOpen = true" :title="t('corpus.more')">
        <span v-html="icons.book" style="width:14px;height:14px;display:inline-flex"></span> {{ t('corpus.more') }}
      </button>
      <button class="btn slim" @click="emit('edit', s)">{{ t('common.edit') }}</button>
    </template>

    <!-- 1. KPI -->
    <section class="sec">
      <div class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-label">Acteur</div>
          <div class="kpi-value">{{ s.acteur_emule || '—' }}</div>
          <span v-if="s.type_engagement" :class="['pill', 'pill-' + (ENGAGEMENT_TONE[s.type_engagement] || 'gray')]">
            <span class="dot"></span>{{ ENGAGEMENT_LABEL[s.type_engagement] || s.type_engagement }}
          </span>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">TTPs</div>
          <div class="kpi-value">{{ matrixTechniques.length }}</div>
          <span class="pill pill-cyan"><span class="dot"></span>{{ d3fend.length }} D3FEND</span>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Couverture</div>
          <div class="kpi-value">{{ usage?.coverage?.covered_pct ?? 0 }}%</div>
          <span v-if="usage?.coverage?.gaps" class="pill pill-red"><span class="dot"></span>{{ usage.coverage.gaps }} angle{{ usage.coverage.gaps > 1 ? 's' : '' }} mort{{ usage.coverage.gaps > 1 ? 's' : '' }}</span>
          <span v-else class="pill pill-green"><span class="dot"></span>Aucun angle mort</span>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Audits liés</div>
          <div class="kpi-value">{{ usage?.audits?.length ?? 0 }}</div>
          <span v-if="s.tlp" :class="['pill', 'pill-' + (TLP_TONE[s.tlp] || 'gray')]">TLP:{{ s.tlp }}</span>
        </div>
      </div>
    </section>

    <!-- 2. Identité -->
    <section class="sec">
      <div class="sec-t">{{ t('sec.identite') }}</div>
      <dl class="dl">
        <dt>Type d'engagement</dt><dd>{{ s.type_engagement || '—' }}</dd>
        <dt>Sophistication</dt><dd>{{ s.sophistication || '—' }}</dd>
        <dt>Crédibilité (Admiralty)</dt><dd>{{ s.credibilite || '—' }}</dd>
        <dt>Marquages</dt><dd>TLP:{{ s.tlp || '—' }} <span v-if="s.pap" class="faint">· PAP:{{ s.pap }}</span></dd>
      </dl>
      <div v-if="s.objectif" class="prose objective"><b>Objectif.</b> {{ s.objectif }}</div>
      <div v-if="s.notes" class="prose">{{ s.notes }}</div>
    </section>

    <!-- 3. TTPs ATT&CK (lecture seule — généré depuis les techniques des étapes) -->
    <section class="sec">
      <AttckTtpMatrix :techniques="matrixTechniques" :steps-count="steps.length"
                      description="Couverture ATT&amp;CK des étapes offensives du scénario — techniques distinctes." />
    </section>

    <!-- 4. Étapes offensives -->
    <section class="sec">
      <div class="panel-card">
        <div class="panel-head">
          <div class="panel-title"><span class="badge badge-red">ATT&CK</span>Étapes offensives</div>
          <span class="count-badge">{{ steps.length }}</span>
        </div>
        <div v-if="steps.length" class="step-list">
          <div v-for="(st, i) in steps" :key="st.id" class="step-item">
            <div class="step-n">{{ i + 1 }}</div>
            <div class="step-content">
              <div class="step-head">
                <span v-if="st.tactique" class="tactic-tag">{{ TACTIC_LABEL[st.tactique] || st.tactique }}</span>
                <a v-if="st.technique" :href="attackUrl(st.technique)" target="_blank" rel="noopener noreferrer" class="step-tech">
                  <span class="tech-id">{{ st.technique }}</span> {{ refName('attack', st.technique) || '' }}
                </a>
              </div>
              <div v-if="st.commande" class="term-box"><span class="prompt">$</span> {{ st.commande }}</div>
              <div v-if="st.description" class="step-desc">{{ st.description }}</div>
            </div>
          </div>
        </div>
        <div v-else-if="stepsLoaded" class="usage-empty">Aucune étape renseignée pour l'instant.</div>
      </div>
    </section>

    <!-- 5. Contre-mesures D3FEND -->
    <section v-if="d3fend.length" class="sec">
      <div class="panel-card">
        <div class="panel-head">
          <div class="panel-title"><span class="badge badge-green">D3FEND</span>Contre-mesures D3FEND</div>
          <span class="count-badge">{{ d3fend.length }}</span>
        </div>
        <div class="d3-list">
          <a v-for="d in d3fend" :key="d" :href="d3fendUrl(refName('d3fend', d))" target="_blank" rel="noopener noreferrer" class="d3-row">
            <span :class="['pill', 'pill-' + (CATEGORY_TONE[categoryOf(d)] || 'cyan')]">{{ categoryOf(d).toUpperCase() }}</span>
            <span class="d3-name">{{ refName('d3fend', d) || d }}</span>
            <span class="tech-id">{{ d }}</span>
          </a>
        </div>
        <p class="faint auto-note">Calculées automatiquement à partir des techniques ci-dessus (socle de correspondance partiel).</p>
      </div>
    </section>

    <section v-if="s.ioc || s.ioa" class="sec">
      <div class="sec-t">{{ t('sec.indicators') }}</div>
      <dl class="dl">
        <dt>IOC</dt><dd class="mono">{{ s.ioc || '—' }}</dd>
        <dt>IOA</dt><dd class="mono">{{ s.ioa || '—' }}</dd>
      </dl>
    </section>

    <!-- 6. Contexte d'utilisation -->
    <section class="sec">
      <div class="panel-card">
        <div class="panel-title plain">Contexte d'utilisation</div>
        <div class="ctx-cols">
          <div class="ctx-col">
            <div class="ctx-label">Clients concernés</div>
            <div v-if="usage?.clients?.length" class="ctx-chips">
              <span v-for="c in usage.clients" :key="c" class="pill pill-violet"><span class="dot"></span>{{ c }}</span>
            </div>
            <span v-else class="faint">—</span>
          </div>
          <div class="ctx-col">
            <div class="ctx-label">Applications</div>
            <div v-if="usage?.applications?.length" class="ctx-chips">
              <span v-for="a in usage.applications" :key="a.id" class="pill pill-gray">{{ a.nom }}</span>
            </div>
            <span v-else class="faint">—</span>
          </div>
        </div>
        <div class="ctx-block">
          <div class="ctx-label">Audits utilisant ce scénario</div>
          <div v-if="usage?.audits?.length" class="ctx-boxes">
            <RouterLink v-for="a in usage.audits" :key="a.id" :to="`/audits/${a.id}`" class="ctx-box link">{{ a.nom }}</RouterLink>
          </div>
          <div v-else class="usage-empty">Ce scénario n'est référencé par aucun audit pour l'instant. Rattachez-le lors du cadrage d'un audit.</div>
        </div>
        <div v-if="usage?.exercices?.length" class="ctx-block">
          <div class="ctx-label">Exercices Purple</div>
          <div class="ctx-boxes">
            <RouterLink v-for="ex in usage.exercices" :key="ex.id" :to="`/exercices/${ex.id}`" class="ctx-box link">{{ ex.nom }}</RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- 7. Rapport STIX -->
    <section class="sec">
      <div class="panel-card">
        <div class="panel-head">
          <div class="panel-title plain">STIX 2.1</div>
          <div class="stix-actions">
            <span v-if="copyMsg" class="copied">Copié !</span>
            <button class="btn slim" :disabled="!stixText" @click="copyStix">Copier</button>
            <button class="btn slim btn-primary" :disabled="!stixBundle" @click="exportStix">Télécharger</button>
          </div>
        </div>
        <p v-if="stixBusy" class="faint">Génération du bundle…</p>
        <pre v-else-if="stixText" class="stix-preview">{{ stixText }}</pre>
        <p v-else class="faint">Bundle indisponible.</p>
      </div>
    </section>
  </DetailDrawer>

  <CorpusArticleDrawer v-if="corpusOpen" slug="corp-cti-scenario" @close="corpusOpen = false" />
</template>

<style scoped>
.slim{padding:3px 9px;font-size:11.5px}
.sec{margin-bottom:18px}
.sec-t{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight);margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--border-2)}
.dl{display:grid;grid-template-columns:150px 1fr;gap:7px 12px;margin:0;font-size:13px}
.dl dt{color:var(--muted)} .dl dd{margin:0;color:var(--text)}
.mono{font-family:var(--font-data);font-size:12.5px} .prose{font-size:13px;color:var(--text);line-height:1.5;margin-top:8px}
.objective{margin-top:10px}

.pill .dot{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block;margin-right:5px}
.pill-blue{background:var(--c-blue-bg);border-color:var(--c-blue-bd);color:var(--c-blue-tx)}

.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.kpi-card{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-card);padding:14px;box-shadow:var(--shadow)}
.kpi-label{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10px;color:var(--faint);margin-bottom:8px}
.kpi-value{font-family:var(--font-data);font-size:22px;font-weight:700;color:var(--heading);margin-bottom:9px;line-height:1}

.panel-card{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-card);padding:16px}
.panel-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}
.panel-title{display:flex;align-items:center;gap:9px;font-family:var(--font-display);font-weight:600;color:var(--heading);font-size:14px}
.panel-title.plain{font-size:14.5px}
.panel-meta{font-size:11.5px;color:var(--faint)}
.badge{font-family:var(--font-data);font-size:10px;font-weight:700;border-radius:var(--r-mini);padding:3px 7px;letter-spacing:.02em}
.badge-red{background:var(--c-red-bg);color:var(--c-red-tx);border:1px solid var(--c-red-bd)}
.badge-green{background:var(--c-green-bg);color:var(--green);border:1px solid var(--c-green-bd,var(--border-2))}
.count-badge{display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:22px;
  border-radius:var(--r-mini);background:var(--surface-3);color:var(--text);font-family:var(--font-data);font-size:11.5px;padding:0 6px}

.tech-id{font-family:var(--font-data);font-size:11.5px;font-weight:700;color:var(--c-violet-tx)}

.step-list{display:flex;flex-direction:column;gap:10px}
.step-item{display:flex;gap:10px;background:var(--surface-3);border:1px solid var(--border);border-radius:var(--r-mini);padding:12px;box-shadow:var(--shadow)}
.step-n{flex:0 0 auto;width:22px;height:22px;border-radius:50%;background:var(--c-violet-bg);color:var(--c-violet-tx);
  display:flex;align-items:center;justify-content:center;font-family:var(--font-data);font-size:11px;font-weight:700;margin-top:1px}
.step-content{flex:1;min-width:0}
.step-head{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:8px}
.tactic-tag{font-size:11px;color:var(--c-violet-tx);border:1px solid var(--c-violet-bd);
  border-radius:var(--r-pill);padding:3px 10px;font-family:var(--font-eyebrow)}
.step-tech{color:var(--text);text-decoration:none;font-size:13px;cursor:pointer}
.step-tech:hover{text-decoration:underline}
.step-tech .tech-id{color:var(--c-violet-tx)}
.term-box{font-family:var(--font-data);font-size:12px;color:var(--text);background:var(--bg);
  border:1px solid var(--border);border-radius:var(--r-mini);padding:8px 11px;margin-bottom:7px}
.term-box .prompt{color:var(--violet-accent);margin-right:6px;font-weight:700}
.step-desc{font-size:12.5px;color:var(--muted);line-height:1.45}

.d3-list{display:flex;flex-direction:column;gap:1px;border:1px solid var(--border);border-radius:var(--r-mini);overflow:hidden}
.d3-row{display:flex;align-items:center;gap:12px;padding:10px 12px;background:var(--surface-3);text-decoration:none;
  border-bottom:1px solid var(--border-2)}
.d3-row:last-child{border-bottom:none}
.d3-row:hover{background:var(--surface-3)}
.d3-name{flex:1;font-size:13px;color:var(--text)}
.auto-note{font-size:11px;margin-top:10px}

.ctx-cols{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:16px}
.ctx-label{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10px;color:var(--faint);margin-bottom:8px}
.ctx-chips{display:flex;flex-wrap:wrap;gap:6px}
.ctx-block{margin-top:16px}
.ctx-boxes{display:flex;flex-wrap:wrap;gap:8px}
.ctx-box{display:inline-block;background:var(--surface-3);border:1px solid var(--border);border-radius:var(--r-mini);
  padding:8px 12px;font-size:12px;color:var(--text);text-decoration:none}
.ctx-box.link:hover{border-color:var(--violet-accent);color:var(--violet-accent)}
.usage-empty{font-size:12px;color:var(--muted);background:var(--surface-3);border:1px solid var(--border);border-radius:var(--r-mini);padding:9px 12px}

.stix-actions{display:flex;align-items:center;gap:8px}
.copied{font-size:11.5px;color:var(--green)}
.stix-preview{font-family:var(--font-data);font-size:11px;color:var(--text);background:var(--bg);
  border:1px solid var(--border);border-radius:var(--r-mini);padding:12px;max-height:280px;overflow:auto;
  white-space:pre-wrap;word-break:break-word;margin:0}
@media (max-width:820px){ .kpi-row{grid-template-columns:repeat(2,1fr)} .ctx-cols{grid-template-columns:1fr} }
</style>
