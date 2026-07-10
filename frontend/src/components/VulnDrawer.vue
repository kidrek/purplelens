<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import DetailDrawer from './DetailDrawer.vue'
import CorpusArticleDrawer from './CorpusArticleDrawer.vue'
import { api } from '../api/client'
import { useRefNames } from '../composables/useRefNames'
import { useOrgNames } from '../composables/useOrgNames'
import { useLabels } from '../composables/useLabels'
import { attackUrl, d3fendUrl } from '../utils/mitreLinks'
import { icons } from '../icons'
const { t } = useI18n()

// Détail d'une vulnérabilité : ordre et contenu alignés sur la maquette (cahier
// « constats » Vulnérabilités) — client, statut, sévérité, découvreur, phase de
// découverte, description, impact métier, exploitabilité, OWASP, CVE + enrichissement
// CIRCL (CPE/EPSS/KEV/SSVC), CVSS, techniques ATT&CK, recommandations (+ D3FEND auto,
// calculé serveur), et un rappel des référentiels utilisés.
const props = defineProps({ vuln: { type: Object, required: true } })
const emit = defineEmits(['close', 'edit', 'saved', 'manual-enrich'])
const { preload, refLabel, refName } = useRefNames()
const { preload: preloadOrgs, orgName } = useOrgNames()
const { enumLabel } = useLabels()

const full = ref(null)
const audit = ref(null)         // audit lié (nom, pour affichage + navigation)
const decouvreur = ref(null)    // ressource découvreur résolue (nom, rôle)
const applications = ref([])    // applications de l'audit lié, résolues (nom)
const enrichment = ref(null)    // détail brut CIRCL (CPE/CAPEC/références/produits)
const circlBusy = ref(false)
const circlMsg = ref(null)
const corpusOpen = ref(false) // "Corpus" (DA §4.6) : ouvre corp-voc-cycle en overlay
const SSVC_TONE = { Act: 'red', Attend: 'amber', 'Track*': 'cyan', Track: 'gray' }
const SEV_TONE = { critique: 'red', haute: 'amber', moyenne: 'cyan', basse: 'green' }
const VEX_LABEL = { affected: 'Affecté', not_affected: 'Non affecté', fixed: 'Corrigé', under_investigation: 'En analyse' }
const VEX_TONE = { affected: 'red', not_affected: 'green', fixed: 'green', under_investigation: 'amber' }
const ENR_LABEL = { enrichi: 'Enrichie', differe: 'Différée', manual: 'Manuelle', echec: 'Échec' }
const ENR_TONE = { enrichi: 'green', differe: 'amber', manual: 'cyan', echec: 'red' }

onMounted(async () => {
  await Promise.all([preload(['cwe', 'owasp', 'attack', 'capec', 'd3fend']), preloadOrgs()])
  try { full.value = await api.get(`/vulnerabilities/${props.vuln.id}`) } catch { full.value = {} }
  try {
    const r = await api.get(`/vulnerabilities/${props.vuln.id}/enrichment`)
    enrichment.value = r.enrichment
  } catch { enrichment.value = null }
  await loadLinks()
})

const v = computed(() => ({ ...(full.value || {}), ...props.vuln }))
const techniques = computed(() => v.value.techniques || [])
const d3fend = computed(() => v.value.d3fend || [])
const cpes = computed(() => enrichment.value?.raw?.cpes || [])
const capecs = computed(() => enrichment.value?.raw?.capec || [])
const fmtEpss = (s) => (s == null ? '—' : (s * 100).toFixed(1) + '%')
// Fiche CIRCL du CVE (cve.circl.lu — même source que l'enrichissement, en minuscules).
function circlUrl(cveId) {
  return cveId ? `https://cve.circl.lu/vuln/${cveId.toLowerCase()}` : null
}

// Chargements secondaires dépendants de l'enregistrement complet (audit lié, découvreur,
// applications). Les applications viennent de l'audit lié (audit.applications) — même
// logique que la liste : le champ propre de la vulnérabilité n'est renseignable nulle part.
async function loadLinks() {
  if (full.value?.audit_id) {
    try { audit.value = await api.get(`/audits/${full.value.audit_id}`) } catch { audit.value = null }
  }
  if (full.value?.decouvreur_id) {
    try { decouvreur.value = await api.get(`/ressources/${full.value.decouvreur_id}`) } catch { decouvreur.value = null }
  }
  const appIds = audit.value?.applications || full.value?.applications || []
  if (appIds.length) {
    const results = await Promise.all(appIds.map((id) => api.get(`/applications/${id}`).catch(() => null)))
    applications.value = results.filter(Boolean)
  } else {
    applications.value = []
  }
}

// Enrichissement CIRCL déclenché directement depuis le drawer (les actions de ligne
// de la liste se limitent désormais à modifier/supprimer, cf. maquette). Rafraîchit le
// drawer lui-même, et prévient le parent (émission 'saved') pour que la liste reflète
// le nouvel enrichissement sans que l'utilisateur ait à rouvrir.
async function enrichCircl() {
  if (!v.value.cve || circlBusy.value) return
  circlBusy.value = true
  circlMsg.value = null
  try {
    const r = await api.post(`/vulnerabilities/${v.value.id}/enrich`)
    if (r.status === 'enrichi') circlMsg.value = { kind: 'ok', text: `Enrichi — SSVC ${r.ssvc_decision}${r.kev ? ', KEV' : ''}.` }
    else circlMsg.value = { kind: 'warn', text: r.message || 'Enrichissement différé.' }
    full.value = await api.get(`/vulnerabilities/${v.value.id}`)
    const er = await api.get(`/vulnerabilities/${v.value.id}/enrichment`)
    enrichment.value = er.enrichment
    emit('saved')
  } catch (e) {
    circlMsg.value = { kind: 'ko', text: e.message || 'Enrichissement impossible.' }
  } finally {
    circlBusy.value = false
  }
}
</script>

<template>
  <DetailDrawer :title="v.titre || v.cve || 'Vulnérabilité'" subtitle="Vulnérabilité" wide @close="emit('close')">
    <template #actions>
      <button class="btn slim" @click="corpusOpen = true" :title="t('corpus.more')">
        <span v-html="icons.book" style="width:14px;height:14px;display:inline-flex"></span> {{ t('corpus.more') }}
      </button>
      <button class="btn slim" @click="emit('manual-enrich', v)">Enrichissement manuel</button>
      <button class="btn slim" @click="emit('edit', v)">{{ t('common.edit') }}</button>
    </template>

    <!-- Bandeau d'état -->
    <div class="badges">
      <span v-if="v.severite" :class="['pill', 'pill-' + (SEV_TONE[String(v.severite).toLowerCase()] || 'gray')]">{{ enumLabel(v.severite) }}</span>
      <span v-if="v.statut" class="pill pill-gray">{{ enumLabel(v.statut) }}</span>
      <span v-if="v.cvss_score != null" class="pill pill-gray">CVSS {{ Number(v.cvss_score).toFixed(1) }}</span>
      <span v-if="v.kev" class="pill pill-red">KEV<span v-if="v.kev_ransomware"> ⚠</span></span>
      <span v-if="v.ssvc_decision" :class="['pill', 'pill-' + (SSVC_TONE[v.ssvc_decision] || 'gray')]">SSVC {{ v.ssvc_decision }}</span>
      <span v-if="v.vex_status" class="pill pill-cyan">VEX {{ VEX_LABEL[v.vex_status] || v.vex_status }}</span>
      <span v-if="v.tlp" class="pill pill-gray">TLP:{{ v.tlp }}</span>
    </div>

    <!-- 1. Identité : client, audit lié, statut, sévérité, découvreur, phase, SLA -->
    <section class="sec">
      <div class="sec-t">{{ t('sec.identite') }}</div>
      <dl class="dl">
        <dt>Client</dt><dd>{{ v.client_id ? orgName(v.client_id) : '—' }}</dd>
        <dt>Audit lié</dt>
        <dd>
          <RouterLink v-if="audit" :to="`/audits/${audit.id}`" class="link">{{ audit.nom }}</RouterLink>
          <span v-else class="faint">Aucun audit lié.</span>
        </dd>
        <dt>Application(s)</dt>
        <dd>
          <template v-if="applications.length">{{ applications.map((a) => a.nom).join(', ') }}</template>
          <span v-else class="faint">—</span>
        </dd>
        <dt>Statut</dt><dd>{{ v.statut ? enumLabel(v.statut) : '—' }}</dd>
        <dt>Sévérité</dt><dd>{{ v.severite ? enumLabel(v.severite) : '—' }}</dd>
        <dt>Découvreur</dt>
        <dd>
          <template v-if="decouvreur">{{ decouvreur.nom }} <span class="faint">({{ enumLabel(decouvreur.role) }})</span></template>
          <span v-else class="faint">—</span>
        </dd>
        <dt>Phase de découverte</dt><dd>{{ v.phase_decouverte ? enumLabel(v.phase_decouverte) : '—' }}</dd>
        <dt>SLA</dt><dd>{{ v.sla_niveau || '—' }}<span v-if="v.sla_echeance"> · échéance {{ v.sla_echeance }}</span>
          <span v-if="v.sla_overdue" class="over"> (dépassée)</span></dd>
      </dl>
    </section>

    <!-- 2. Analyse : description, impact métier, exploitabilité -->
    <section v-if="v.description || v.impact_metier || v.exploitabilite" class="sec">
      <div class="sec-t">{{ t('sec.analysis') }}</div>
      <div v-if="v.description" class="prose"><b>Description.</b> {{ v.description }}</div>
      <div v-if="v.impact_metier" class="prose"><b>Impact métier.</b> {{ v.impact_metier }}</div>
      <div v-if="v.exploitabilite" class="prose"><b>Exploitabilité.</b> {{ enumLabel(v.exploitabilite) }}</div>
      <div v-if="v.preuve_exploitation" class="prose"><b>Preuve d'exploitation.</b> {{ v.preuve_exploitation }}</div>
    </section>

    <!-- 3. Classification : OWASP, CVE + enrichissement CIRCL, CVSS, CWE -->
    <section class="sec">
      <div class="sec-t">{{ t('sec.classification') }}</div>
      <dl class="dl">
        <dt>OWASP Top 10</dt><dd>{{ v.owasp_top10 ? refLabel('owasp', v.owasp_top10) : '—' }}</dd>
        <dt>CVE</dt>
        <dd class="mono">
          <a v-if="v.cve" :href="circlUrl(v.cve)" target="_blank" rel="noopener noreferrer"
             class="link" :title="'Voir ' + v.cve + ' sur cve.circl.lu'">{{ v.cve }} ↗</a>
          <span v-else>—</span>
        </dd>
        <dt>CWE</dt><dd>{{ v.cwe ? refLabel('cwe', v.cwe) : '—' }}</dd>
        <dt>Vecteur CVSS</dt><dd class="mono">{{ v.cvss_vector || '—' }}</dd>
        <dt>Score CVSS</dt><dd class="mono">{{ v.cvss_score != null ? Number(v.cvss_score).toFixed(1) : '—' }}</dd>
      </dl>
      <div v-if="capecs.length" class="sub">
        <span class="sub-lbl">CAPEC :</span>
        <span v-for="c in capecs" :key="c" class="chip gray">{{ c }}</span>
      </div>
    </section>

    <!-- Enrichissement VOC : carte dédiée (style maquette) — statut, action CIRCL, EPSS/KEV/SSVC/VEX -->
    <section class="sec">
      <div class="voc-card">
        <div class="voc-head">
          <div class="voc-title">Enrichissement VOC</div>
          <div class="voc-actions">
            <span :class="['pill', 'pill-' + (ENR_TONE[v.enrichment_status] || 'gray')]">
              <span class="dot"></span>{{ ENR_LABEL[v.enrichment_status] || 'Non enrichie' }}
            </span>
            <button class="btn slim" :disabled="!v.cve || circlBusy"
                    :title="v.cve ? 'Enrichir via CIRCL' : 'Aucun CVE'" @click="enrichCircl">
              <span v-if="circlBusy" class="spin"></span>{{ circlBusy ? '…' : 'Enrichir via CIRCL' }}
            </button>
          </div>
        </div>
        <p class="voc-sub">Sources en ligne CIRCL (vulnerability-lookup, EPSS dédié) — dégradation gracieuse si aucun CVE ou source injoignable.</p>
        <p v-if="circlMsg" :class="['circl-msg', circlMsg.kind]">{{ circlMsg.text }}</p>
        <div class="voc-divider"></div>
        <div class="voc-grid">
          <div class="voc-metric">
            <div class="vm-label">EPSS</div>
            <div class="vm-value">{{ fmtEpss(v.epss_score) }}</div>
            <div v-if="v.epss_percentile != null" class="vm-sub">percentile {{ (v.epss_percentile * 100).toFixed(0) }}%</div>
          </div>
          <div class="voc-metric">
            <div class="vm-label">CISA KEV</div>
            <span v-if="v.kev" class="pill pill-red"><span class="dot"></span>Exploitée (KEV)<span v-if="v.kev_ransomware"> ⚠</span></span>
            <span v-else class="pill pill-gray">Non exploitée</span>
            <div v-if="enrichment?.kev_date_added" class="vm-sub">ajoutée le {{ enrichment.kev_date_added }}</div>
            <div v-else-if="v.kev_due_date" class="vm-sub">échéance {{ v.kev_due_date }}</div>
          </div>
          <div class="voc-metric">
            <div class="vm-label">SSVC <span class="info-dot" title="Stakeholder-Specific Vulnerability Categorization — décision de remédiation calculée (CVSS + KEV + EPSS).">ⓘ</span></div>
            <span v-if="v.ssvc_decision" :class="['pill', 'pill-' + (SSVC_TONE[v.ssvc_decision] || 'gray')]">{{ v.ssvc_decision }}</span>
            <span v-else class="faint">—</span>
          </div>
          <div class="voc-metric">
            <div class="vm-label">VEX</div>
            <span v-if="v.vex_status" :class="['pill', 'pill-' + (VEX_TONE[v.vex_status] || 'gray')]">{{ VEX_LABEL[v.vex_status] || v.vex_status }}</span>
            <span v-else class="faint">—</span>
          </div>
        </div>
        <div v-if="cpes.length" class="sub">
          <span class="sub-lbl">CPE :</span>
          <span v-for="c in cpes" :key="c" class="chip mono">{{ c }}</span>
        </div>
        <div v-if="v.enrichment_source" class="voc-source">Source : {{ v.enrichment_source }}</div>
      </div>
    </section>

    <!-- 4. Techniques ATT&CK -->
    <section class="sec">
      <div class="sec-t">{{ t('sec.techniques') }}</div>
      <template v-if="techniques.length">
        <a v-for="tq in techniques" :key="tq" :href="attackUrl(tq)" target="_blank" rel="noopener noreferrer"
           class="chip link-chip" :title="'Voir ' + tq + ' sur attack.mitre.org'">{{ refLabel('attack', tq) }} ↗</a>
      </template>
      <span v-else class="faint">—</span>
    </section>

    <!-- 5. Recommandations : texte libre + contre-mesures D3FEND (lecture seule, auto) -->
    <section v-if="v.recommandation || d3fend.length" class="sec">
      <div class="sec-t">{{ t('sec.recommendations') }}</div>
      <div v-if="v.recommandation" class="prose">{{ v.recommandation }}</div>
      <div v-if="d3fend.length" class="sub">
        <span class="sub-lbl">Contre-mesures D3FEND (auto, d'après les techniques ci-dessus) :</span>
        <a v-for="d in d3fend" :key="d" :href="d3fendUrl(refName('d3fend', d))" target="_blank" rel="noopener noreferrer"
           class="chip link-chip green" :title="'Voir sur d3fend.mitre.org'">{{ refLabel('d3fend', d) }} ↗</a>
      </div>
    </section>

    <!-- 6. À propos des référentiels -->
    <section class="sec">
      <div class="sec-t">{{ t('sec.referentiels') }}</div>
      <div class="ref-block">
        <p><b>Classification de la faille</b></p>
        <p><b>OWASP Top 10</b> — les 10 risques de sécurité web les plus critiques ; un langage commun pour situer une faille.</p>
        <p><b>CWE</b> — dictionnaire des types de faiblesses logicielles : le « quoi » technique (ex. injection, contrôle d'accès défaillant).</p>
        <p><b>CAPEC</b> — catalogue des schémas d'attaque : « comment » un attaquant exploite une faiblesse.</p>
        <p class="mt"><b>Offensif ↔ défensif</b></p>
        <p><b>MITRE ATT&CK</b> — tactiques et techniques réellement observées chez les attaquants (ex. T1190).</p>
        <p><b>MITRE D3FEND</b> — contrepartie défensive d'ATT&CK : contre-mesures (durcir, détecter, isoler…) liées aux techniques.</p>
        <p class="mt"><b>Identification &amp; priorisation</b></p>
        <p><b>CVE</b> — identifiant unique d'une vulnérabilité publiquement connue (ex. CVE-2024-3094).</p>
        <p><b>CVSS</b> — score de gravité de 0 à 10 ; plus il est élevé, plus la faille est grave.</p>
        <p><b>EPSS</b> — probabilité qu'une faille soit exploitée dans les 30 jours (0 à 100 %).</p>
        <p><b>CISA KEV</b> — catalogue des failles à exploitation avérée ; remédiation prioritaire.</p>
        <p><b>SSVC</b> — aide à la décision de remédiation (Suivre / Surveiller / Agir) selon l'exploitation et l'impact.</p>
        <p><b>VEX</b> — statut d'exploitabilité d'un produit : affecté, non affecté, corrigé, à l'étude.</p>
      </div>
    </section>
  </DetailDrawer>

  <CorpusArticleDrawer v-if="corpusOpen" slug="corp-voc-cycle" @close="corpusOpen = false" />
</template>

<style scoped>
.slim{padding:3px 9px;font-size:11.5px}
.primary-ghost{border-color:var(--violet);color:var(--violet-accent)}
.spin{width:10px;height:10px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;display:inline-block;animation:spin .7s linear infinite;margin-right:4px;vertical-align:-1px}
@keyframes spin{to{transform:rotate(360deg)}}
.circl-msg{font-size:12px;margin:0 0 12px}
.circl-msg.ok{color:var(--green)} .circl-msg.warn{color:var(--amber)} .circl-msg.ko{color:var(--red)}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}
.sec{margin-bottom:18px}
.sec-t{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.05em;font-size:10.5px;color:var(--faint);font-weight:var(--eyebrow-weight);margin-bottom:8px;padding-bottom:5px;border-bottom:1px solid var(--border-2)}
.dl{display:grid;grid-template-columns:130px 1fr;gap:7px 12px;margin:0;font-size:13px}
.dl dt{color:var(--muted)} .dl dd{margin:0;color:var(--text)}
.mono{font-family:var(--font-data);font-size:12.5px} .over{color:var(--red)}
.link{color:var(--violet-accent);text-decoration:none;cursor:pointer}
.link:hover{text-decoration:underline}
.chip{display:inline-block;background:var(--c-violet-bg);border:1px solid var(--c-violet-bd);color:var(--c-violet-tx);
  border-radius:var(--r-pill);padding:1px 8px;font-size:11.5px;font-family:var(--font-data);margin:0 4px 4px 0}
.chip.gray{background:var(--surface-3);border-color:var(--border-2);color:var(--muted)}
.chip.green{background:var(--c-green-bg);border-color:var(--c-green-bd,var(--border-2));color:var(--green)}
.chip.mono{font-family:var(--font-data)}
.link-chip{text-decoration:none;cursor:pointer}
.link-chip:hover{border-color:var(--violet-accent);text-decoration:none;filter:brightness(1.1)}

.voc-card{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-card);padding:16px}
.voc-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.voc-title{font-family:var(--font-display);font-weight:600;color:var(--heading);font-size:14.5px}
.voc-actions{display:flex;align-items:center;gap:8px}
.voc-sub{font-size:12px;color:var(--faint);margin:8px 0 0}
.voc-divider{height:1px;background:var(--border-2);margin:14px 0}
.voc-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.voc-metric{background:var(--surface-3);border:1px solid var(--border);border-radius:var(--r-mini);padding:12px;box-shadow:var(--shadow)}
.vm-label{font-family:var(--font-eyebrow);text-transform:uppercase;letter-spacing:.04em;font-size:10px;color:var(--faint);margin-bottom:8px}
.vm-value{font-family:var(--font-data);font-size:22px;font-weight:700;color:var(--heading);line-height:1}
.vm-sub{font-size:10.5px;color:var(--faint);margin-top:6px}
.info-dot{font-size:10px;color:var(--faint);cursor:help}
.voc-source{font-size:11px;color:var(--faint);margin-top:12px}
.pill .dot{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block;margin-right:5px}
@media (max-width:720px){ .voc-grid{grid-template-columns:repeat(2,1fr)} }
.prose{font-size:13px;color:var(--text);line-height:1.5;margin-bottom:8px}
.sub{margin-top:10px}
.sub-lbl{display:block;font-size:11px;color:var(--faint);margin-bottom:5px}
.ref-block{font-size:12px;color:var(--muted);line-height:1.6}
.ref-block p{margin:0 0 4px}
.ref-block .mt{margin-top:10px}
.ref-block b{color:var(--text)}
</style>

