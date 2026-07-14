<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, ApiError } from '../api/client'
import DetailDrawer from './DetailDrawer.vue'
import EngagementForm from './EngagementForm.vue'
import EntityForm from './EntityForm.vue'
import AttckTtpMatrix from './AttckTtpMatrix.vue'
import { ENTITY_FIELDS } from '../fields'
import { useRefNames } from '../composables/useRefNames'
import { useLabels } from '../composables/useLabels'

// Drawer d'audit consolidé (maquette phase 4.5, drawer « auditView ») : l'analyste
// consulte TOUT l'audit sans quitter la liste — KPI, faits, bloc engagement, jalons
// PTES, actions de test, exercices rattachés, livrables. Lecture seule : les
// écritures se font sur la fiche (« Ouvrir ») ou via les formulaires dédiés.
// Le serveur reste l'autorité : chaque appel de chargement repasse par can() + RLS,
// et un 403 sur une sous-ressource masque simplement le panneau correspondant.
const props = defineProps({
  record: { type: Object, required: true },
})
const emit = defineEmits(['close', 'edit'])

const { enumLabel } = useLabels()
const { preload, refLabel } = useRefNames()

const PTES_ORDER = [
  'pre-engagement', 'reconnaissance', 'threat-modeling', 'vulnerability-analysis',
  'exploitation', 'post-exploitation', 'reporting',
]
const DELIVERABLE_LABELS = { engagement: "Lettre d'engagement", nda: 'NDA', rapport: 'Rapport PTES' }

const audit = ref(props.record)
const actions = ref([])
const milestones = ref([])
const exercices = ref([])
const vulns = ref([])
const deliverables = ref([])
const scenario = ref(null) // scénario CTI rattaché (pour ses TTP)
const names = ref({ orgs: {}, apps: {}, ressources: {}, scenarios: {} })
const loading = ref(true)

const unwrap = (d) => (Array.isArray(d) ? d : (d?.items ?? []))
const safeList = (entity, q = '') => api.list(entity, q).then(unwrap).catch(() => [])
const toMap = (list) => Object.fromEntries(list.map((o) => [o.id, o.nom || o.titre || o.id]))

async function loadAll() {
  loading.value = true
  const id = props.record.id
  try {
    // Enregistrement rechargé (la ligne de liste peut être partielle/stale).
    const [full, acts, miles, exos, vulnz, delivs, orgs, apps, ress, scens] = await Promise.all([
      api.get(`/audits/${id}`).catch(() => props.record),
      safeList('audit_actions', `?audit_id=${id}`),
      safeList('audit_milestones', `?audit_id=${id}`),
      safeList('exercices', `?audit_id=${id}`),
      safeList('vulnerabilities', `?audit_id=${id}`),
      safeList('deliverables', `?audit_id=${id}`),
      safeList('organisations'),
      safeList('applications'),
      safeList('ressources'),
      safeList('scenarios'),
    ])
    audit.value = full
    actions.value = acts
    milestones.value = miles
    exercices.value = exos
    vulns.value = vulnz
    deliverables.value = delivs
    names.value = { orgs: toMap(orgs), apps: toMap(apps), ressources: toMap(ress), scenarios: toMap(scens) }
    // Scénario CTI rattaché → ses techniques ATT&CK (TTP) affichées dans le drawer.
    if (full.scenario_id) {
      scenario.value = await api.get(`/scenarios/${full.scenario_id}`).catch(() => null)
    }
  } finally {
    loading.value = false
  }
}
onMounted(() => { loadAll(); preload(['attack']) })

const nameOf = (kind, id) => names.value[kind][id] || id || '—'

// ── KPI (mêmes définitions que la maquette) ─────────────────────────────────
const jalonsByPhase = computed(() => {
  const map = {}
  for (const m of milestones.value) map[m.ptes_phase] = m
  return PTES_ORDER.map((phase) => ({ phase, jalon: map[phase] || null }))
})
const doneMilestones = computed(() => milestones.value.filter((m) => m.statut === 'termine' || m.statut === 'atteint').length)
const ptesPct = computed(() => (milestones.value.length ? Math.round((doneMilestones.value / milestones.value.length) * 100) : 0))
const vulnsFound = computed(() => new Set(actions.value.map((a) => a.vulnerabilite_id).filter(Boolean)).size)

const eng = computed(() => audit.value?.engagement || null)
const engHas = (k) => Array.isArray(eng.value?.[k]) ? eng.value[k].length > 0 : !!eng.value?.[k]
const scenarioTTPs = computed(() => scenario.value?.techniques || [])

// Éditeur du bloc engagement (bouton « Modifier » du panneau, comme la maquette).
const engOpen = ref(false)
async function onEngSaved() {
  engOpen.value = false
  audit.value = await api.get(`/audits/${props.record.id}`).catch(() => audit.value)
}

// Valeurs par défaut de l'engagement/NDA, dérivées de l'audit pour faire gagner du
// temps à l'auditeur (il ne remplit que ce qui est propre à la mission). Les clauses
// NDA type décrivent les garanties réelles de la plateforme (cloisonnement, WORM, chiffrement).
const engagementDefaults = computed(() => {
  const a = audit.value || {}
  const clientNom = names.value.orgs[a.client_id] || 'le client'
  const apps = (a.applications || []).map((id) => nameOf('apps', id)).filter(Boolean)
  const clientCode = clientNom.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toUpperCase().replace(/[^A-Z0-9]+/g, '').slice(0, 14)
  const year = (a.date_debut || '').slice(0, 4) || String(new Date().getFullYear())
  const fenetres = a.date_debut && a.date_fin ? [`${a.date_debut} → ${a.date_fin}`] : []

  // Contexte lisible dérivé de l'audit, réutilisé dans les textes rédigés.
  const cat = a.categorie || 'pentest'
  const box = ({ blackbox: 'boîte noire', graybox: 'boîte grise', whitebox: 'boîte blanche' }[a.type_test]
    || (a.type_test ? a.type_test : 'boîte grise'))
  const env = a.environnement || "l'environnement convenu"
  const refs = (a.referentiels_methodo || [])
  const refsTxt = refs.length ? refs.join(', ') : 'PTES et OWASP WSTG'
  const acteur = scenario.value?.acteur_emule
  const perimetreTxt = apps.length ? apps.join(', ') : 'le périmètre convenu'

  // Objectifs et livrables adaptés au type d'engagement (pentest / red team / BAS).
  const OBJECTIFS = {
    pentest: [
      `Identifier et qualifier les vulnérabilités exploitables du périmètre (${perimetreTxt}) en conditions réelles.`,
      "Évaluer l'impact métier d'une compromission et la profondeur d'accès atteignable.",
      'Formuler des recommandations de remédiation priorisées par le niveau de risque.',
    ],
    red_team: [
      'Évaluer la capacité de détection et de réaction des équipes défensives face à un adversaire réaliste'
        + (acteur ? ` (émulation ${acteur}).` : '.'),
      "Démontrer une chaîne d'attaque de bout en bout : accès initial → progression → atteinte de l'objectif.",
      'Mesurer les délais de détection (MTTD) et de réaction (MTTR) sur les TTP mis en œuvre.',
    ],
    bas: [
      "Valider l'efficacité des contrôles de sécurité en place face à un ensemble de TTP ATT&CK.",
      'Mesurer la couverture de détection et identifier les angles morts de la télémétrie.',
    ],
  }
  const LIVRABLES = {
    pentest: ["Lettre d'engagement signée", "Rapport de test d'intrusion (synthèse exécutive + détails techniques)",
      'Registre des vulnérabilités priorisées (CVSS et SLA de remédiation)', "Restitution orale et plan d'action"],
    red_team: ["Lettre d'engagement signée", "Rapport Red Team (récit d'attaque, chaîne ATT&CK, recommandations)",
      'Synthèse détection/réaction (MTTD/MTTR) à destination de la Blue Team', 'Restitution conjointe (purple debrief)'],
    bas: ["Lettre d'engagement signée", 'Rapport de simulation (couverture ATT&CK, verdicts par TTP)',
      'Matrice des angles morts de détection', "Recommandations d'amélioration de la télémétrie"],
  }

  return {
    objectifs: OBJECTIFS[cat] || OBJECTIFS.pentest,

    perimetre_inclus: apps.length ? apps : [],
    perimetre_exclus: [
      'Tout système, application ou plage réseau non explicitement listé au périmètre inclus.',
      'Attaques par déni de service (DoS/DDoS), sauf autorisation écrite explicite.',
      'Ingénierie sociale et intrusions physiques, sauf mention contraire au périmètre.',
      "Services tiers et infrastructures hébergées non maîtrisés par le client (autorisation de l'hébergeur requise).",
    ],

    regles_engagement:
      `Tests menés en approche ${box} sur ${env}, selon la méthodologie ${refsTxt}. `
      + 'Aucune exfiltration réelle de données : les preuves collectées sont limitées au strict nécessaire à la '
      + "démonstration de la vulnérabilité. Toute vulnérabilité critique susceptible d'affecter la disponibilité ou "
      + "l'intégrité des services fait l'objet d'une notification immédiate au contact d'urgence avant toute "
      + 'exploitation approfondie. Les tests destructifs et le déni de service sont proscrits sauf autorisation écrite. '
      + "En cas de découverte de données personnelles ou sensibles, l'auditeur interrompt l'action en cours et en "
      + 'informe sans délai le client.',

    fenetres_test: fenetres.length
      ? [...fenetres, "Actions à risque planifiées et confirmées avec le contact d'urgence ; tests hors heures ouvrées à privilégier."]
      : ["Fenêtre de test à convenir ; actions à risque planifiées et confirmées avec le contact d'urgence."],

    contacts_autorisation: ['Responsable habilité du client (RSSI ou équivalent) — nom, fonction et courriel à compléter'],
    contacts_urgence: [`Astreinte sécurité / SOC de ${clientNom} — joignable pendant la fenêtre de test (à compléter)`],

    sow: `SOW-${year}-${clientCode || 'CLIENT'}`,
    ref_nda: clientCode ? `NDA-${clientCode}-${year}` : `NDA-${year}`,
    niveau_intensite: 'Modéré — exploitation contrôlée, sans impact recherché sur la disponibilité des services.',
    livrables_attendus: LIVRABLES[cat] || LIVRABLES.pentest,

    clauses_legales:
      "Prestation exécutée dans le cadre du bon de commande (SOW) référencé et de l'accord de confidentialité (NDA) "
      + 'en vigueur, sous obligation de moyens. Le prestataire est tenu à la confidentialité et à la non-divulgation, '
      + "et déclare disposer d'une assurance responsabilité civile professionnelle en cours de validité. Sa "
      + 'responsabilité est limitée au montant de la prestation, hors faute lourde ou dolosive. Le traitement '
      + "d'éventuelles données personnelles est réalisé conformément au RGPD (accord de sous-traitance au titre de "
      + "l'article 28 le cas échéant).",

    nda_objet:
      'Sont réputées confidentielles toutes les informations techniques, organisationnelles ou personnelles '
      + `relatives au périmètre audité (${perimetreTxt}), aux vulnérabilités identifiées, aux preuves collectées et `
      + "aux livrables produits, quel qu'en soit le support. En sont exclues les informations publiques, celles déjà "
      + 'légitimement détenues, ou développées de manière indépendante par la partie réceptrice.',
    nda_duree: 'Trois (3) ans à compter de la fin de la mission, sans préjudice des obligations légales plus longues.',
    nda_traitement:
      'Données cloisonnées par client et marquées selon le protocole TLP ; accès tracé dans un journal '
      + 'tamper-evident ; preuves chiffrées au repos (AES-256-GCM). Aucun partage ni corrélation inter-clients. '
      + "Accès restreint aux seuls intervenants de la mission (besoin d'en connaître).",
    nda_restitution:
      "Restitution ou destruction certifiée de l'ensemble des données et preuves dans un délai de 30 jours suivant "
      + 'la diffusion du rapport final, sur demande écrite du client et attestée par le prestataire.',
    nda_droit: 'Droit français ; tribunaux compétents du ressort du siège du prestataire (à adapter au contrat).',
  }
})

// Ajout / édition / suppression d'une action de test depuis le drawer (le serveur reste
// l'autorité : un rôle sans droit E/S reçoit un 403 surfacé, cf. matrice RBAC).
const actionOpen = ref(false)
const editingAction = ref(null) // action en cours d'édition, ou null
function editAction(a) { editingAction.value = a }
async function onActionSaved() {
  actionOpen.value = false
  editingAction.value = null
  actions.value = await safeList('audit_actions', `?audit_id=${props.record.id}`)
}
async function delAction(a) {
  if (!window.confirm('Supprimer cette action de test ? Action journalisée.')) return
  try {
    await api.remove('audit_actions', a.id)
    actions.value = await safeList('audit_actions', `?audit_id=${props.record.id}`)
  } catch (e) {
    window.alert(e instanceof ApiError && e.status === 403
      ? 'Action refusée (droits ou cloisonnement).' : (e.message || 'Erreur.'))
  }
}

// Ajout d'une vulnérabilité liée à l'audit (client/audit pré-remplis et figés).
const vulnOpen = ref(false)
async function onVulnSaved() {
  vulnOpen.value = false
  vulns.value = await safeList('vulnerabilities', `?audit_id=${props.record.id}`)
}
const SEV_TONE = { critique: 'red', haute: 'amber', moyenne: 'cyan', basse: 'green' }
const sevPill = (s) => SEV_TONE[s] || 'gray'

// Génération de livrables ancrée sur l'audit (client/audit/TLP pré-remplis).
// Le serveur décide (can() + cloisonnement) ; le binaire ne transite jamais par l'API.
const DELIVERABLE_TYPES = [
  { v: 'engagement', label: "Lettre d'engagement" },
  { v: 'nda', label: 'NDA' },
  { v: 'rapport', label: 'Rapport PTES' },
]
const genBusy = ref(null)
const genMsg = ref(null)
const genLangue = ref('fr') // langue de génération des livrables (fr/en)
async function generateDeliverable(type) {
  genMsg.value = null
  genBusy.value = type
  try {
    await api.post('/deliverables/generate', {
      client_id: audit.value.client_id,
      audit_id: props.record.id,
      type,
      langue: genLangue.value,
      tlp: audit.value.tlp || 'AMBER',
    })
    genMsg.value = { kind: 'ok', text: `Livrable généré (${DELIVERABLE_LABELS[type] || type}).` }
    deliverables.value = await safeList('deliverables', `?audit_id=${props.record.id}`)
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) genMsg.value = { kind: 'ko', text: 'Génération refusée (droits ou cloisonnement).' }
    else genMsg.value = { kind: 'ko', text: e.message || 'Erreur de génération.' }
  } finally {
    genBusy.value = null
  }
}

const TLP_TONE = { RED: 'red', AMBER: 'amber', GREEN: 'green', WHITE: 'gray', CLEAR: 'gray' }
const statutPill = (s) => ({ termine: 'green', atteint: 'green', en_cours: 'cyan', traite: 'green',
  a_venir: 'gray', ouvert: 'amber', manque: 'red', clos: 'green', planifie: 'gray',
  genere: 'green', valide: 'green', diffuse: 'cyan',
  'succès': 'green', succes: 'green', 'échec': 'red', echec: 'red', partiel: 'amber', info: 'cyan' }[s] || 'gray')
const ptesStepClass = (j) => !j ? 'todo' :
  ({ termine: 'done', atteint: 'done', en_cours: 'run', saute: 'skip', manque: 'skip' }[j.statut] || 'todo')

// ── Cycle de jalon cliquable (maquette : cycleJalon) ────────────────────────
// Un clic fait avancer le jalon de la phase : a_venir → en_cours → atteint → manque → …
// Premier clic sur une phase non planifiée : crée le jalon en « en_cours ».
// Passage à « atteint » : date réelle posée au jour même si absente (comme la maquette).
// Le serveur décide (can() + RLS) et journalise ; un refus s'affiche sans casser le tiroir.
const JALON_CYCLE = ['a_venir', 'en_cours', 'atteint', 'manque']
const jalonBusy = ref(null) // phase en cours de mise à jour
const jalonMsg = ref(null)

async function cycleJalon(entry) {
  if (jalonBusy.value) return
  jalonMsg.value = null
  jalonBusy.value = entry.phase
  const today = new Date().toISOString().slice(0, 10)
  try {
    if (!entry.jalon) {
      await api.create('audit_milestones', {
        audit_id: props.record.id,
        client_id: audit.value.client_id,
        ptes_phase: entry.phase,
        statut: 'en_cours',
      })
    } else {
      const i = JALON_CYCLE.indexOf(entry.jalon.statut)
      const next = JALON_CYCLE[(i + 1) % JALON_CYCLE.length]
      const payload = { statut: next }
      if (next === 'atteint' && !entry.jalon.date_reelle) payload.date_reelle = today
      await api.update('audit_milestones', entry.jalon.id, payload)
    }
    milestones.value = await safeList('audit_milestones', `?audit_id=${props.record.id}`)
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) jalonMsg.value = 'Modification refusée (droits ou cloisonnement).'
    else jalonMsg.value = e.message || 'Erreur.'
  } finally {
    jalonBusy.value = null
  }
}

async function downloadDeliverable(d) {
  try {
    const res = await api.get(`/deliverables/${d.id}/download`)
    window.open(res.url, '_blank', 'noopener') // URL présignée courte, binaire hors API
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) window.alert('Livrable pas encore prêt.')
  }
}
const fmtDate = (iso) => (iso ? String(iso).slice(0, 10) : '—')
</script>

<template>
  <DetailDrawer :title="audit?.nom || 'Audit'" subtitle="audit" wide @close="emit('close')">
    <template #actions>
      <button class="btn slim" @click="emit('edit', audit)">✎ Modifier</button>
    </template>

    <p v-if="loading" class="muted">Chargement…</p>
    <div v-else class="stack">

      <!-- KPI -->
      <div class="kpis">
        <div class="kpi"><div class="k-label">Avancement PTES</div><div class="k-value">{{ ptesPct }}%</div>
          <div class="k-foot">{{ doneMilestones }}/{{ milestones.length }} jalons</div></div>
        <div class="kpi"><div class="k-label">Actions de test</div><div class="k-value">{{ actions.length }}</div>
          <div class="k-foot">{{ exercices.length }} exercice(s) Purple</div></div>
        <div class="kpi"><div class="k-label">Vulnérabilités liées</div><div class="k-value">{{ vulnsFound }}</div>
          <div class="k-foot">via actions de test</div></div>
        <div class="kpi"><div class="k-label">Statut</div>
          <div class="k-value sm"><span :class="['pill','pill-'+statutPill(audit.statut)]">{{ enumLabel(audit.statut) }}</span></div>
          <div class="k-foot"><span :class="['pill', 'pill-' + (TLP_TONE[audit.tlp] || 'gray')]">TLP:{{ audit.tlp }}</span></div></div>
      </div>

      <!-- Faits -->
      <section class="panel">
        <div class="p-head">Faits</div>
        <dl class="dl">
          <dt>Client</dt><dd>{{ nameOf('orgs', audit.client_id) }}</dd>
          <dt>Catégorie</dt><dd>{{ enumLabel(audit.categorie) }}<template v-if="audit.type_test"> · {{ enumLabel(audit.type_test) }}</template></dd>
          <dt>Applications</dt><dd>
            <template v-if="(audit.applications || []).length">
              <span v-for="a in audit.applications" :key="a" class="chip">{{ nameOf('apps', a) }}</span>
            </template><span v-else class="faint">—</span></dd>
          <dt>Auditeurs</dt><dd>
            <template v-if="(audit.auditeurs || []).length">
              <span v-for="a in audit.auditeurs" :key="a" class="chip">{{ nameOf('ressources', a) }}</span>
            </template><span v-else class="faint">—</span></dd>
          <dt>Scénario</dt><dd>{{ audit.scenario_id ? nameOf('scenarios', audit.scenario_id) : '—' }}</dd>
          <dt>Environnement</dt><dd>{{ enumLabel(audit.environnement) || '—' }}</dd>
          <dt>Dates</dt><dd>{{ audit.date_debut || '—' }} → {{ audit.date_fin || '—' }}</dd>
          <dt>Priorité</dt><dd>{{ audit.priorite || '—' }}<template v-if="audit.budget"> · {{ audit.budget }} j-h</template></dd>
          <dt v-if="(audit.referentiels_methodo || []).length">Référentiels</dt>
          <dd v-if="(audit.referentiels_methodo || []).length">
            <span v-for="r in audit.referentiels_methodo" :key="r" class="chip">{{ r }}</span></dd>
          <dt v-if="audit.notes">Notes</dt><dd v-if="audit.notes" class="prose">{{ audit.notes }}</dd>
        </dl>
      </section>

      <!-- Scénario CTI rattaché : TTP (techniques ATT&CK) -->
      <section v-if="scenario" class="panel">
        <div class="p-head">Scénario CTI · TTP
          <span v-if="scenario.acteur_emule" class="pill pill-violet">{{ scenario.acteur_emule }}</span>
          <span class="count">{{ scenarioTTPs.length }} technique(s)</span>
        </div>
        <dl class="dl">
          <dt>Scénario</dt><dd>{{ scenario.nom }}</dd>
          <dt v-if="scenario.objectif">Objectif</dt>
          <dd v-if="scenario.objectif" class="prose">{{ scenario.objectif }}</dd>
          <dt v-if="scenario.sophistication">Sophistication</dt>
          <dd v-if="scenario.sophistication">{{ scenario.sophistication }}</dd>
        </dl>
        <AttckTtpMatrix :techniques="scenarioTTPs" />
      </section>

      <!-- Engagement (PTES pré-engagement) -->
      <section class="panel">
        <div class="p-head">Engagement
          <span v-if="eng" :class="['pill', eng.autorisation_signee ? 'pill-green' : 'pill-red']">
            {{ eng.autorisation_signee ? 'Autorisation signée' : 'Non signée' }}</span>
          <span class="spacer" />
          <button class="btn slim" @click="engOpen = true">{{ eng ? '✎ Modifier' : "+ Renseigner" }}</button>
        </div>
        <p v-if="!eng" class="faint">Aucun bloc engagement saisi.</p>
        <dl v-else class="dl">
          <dt v-if="engHas('objectifs')">Objectifs</dt>
          <dd v-if="engHas('objectifs')"><ul class="ul"><li v-for="o in eng.objectifs" :key="o">{{ o }}</li></ul></dd>
          <dt v-if="engHas('perimetre_inclus') || engHas('perimetre_exclus')">Périmètre</dt>
          <dd v-if="engHas('perimetre_inclus') || engHas('perimetre_exclus')">
            <span v-for="p in (eng.perimetre_inclus || [])" :key="'i'+p" class="chip in">{{ p }}</span>
            <span v-for="p in (eng.perimetre_exclus || [])" :key="'e'+p" class="chip out">{{ p }}</span></dd>
          <dt v-if="eng.regles_engagement">Règles (RoE)</dt>
          <dd v-if="eng.regles_engagement" class="prose">{{ eng.regles_engagement }}</dd>
          <dt v-if="engHas('fenetres_test')">Fenêtres</dt>
          <dd v-if="engHas('fenetres_test')"><ul class="ul"><li v-for="w in eng.fenetres_test" :key="w">{{ w }}</li></ul></dd>
          <dt v-if="engHas('contacts_autorisation') || engHas('contacts_urgence')">Contacts</dt>
          <dd v-if="engHas('contacts_autorisation') || engHas('contacts_urgence')"><ul class="ul">
            <li v-for="c in (eng.contacts_autorisation || [])" :key="'a'+c">{{ c }} (autorisation)</li>
            <li v-for="c in (eng.contacts_urgence || [])" :key="'u'+c">{{ c }} (urgence)</li></ul></dd>
          <dt v-if="eng.sow || eng.ref_nda">SOW / NDA</dt>
          <dd v-if="eng.sow || eng.ref_nda">{{ eng.sow || '—' }} · {{ eng.ref_nda || '—' }}</dd>
          <dt v-if="engHas('livrables_attendus')">Livrables attendus</dt>
          <dd v-if="engHas('livrables_attendus')">
            <span v-for="l in eng.livrables_attendus" :key="l" class="chip">{{ l }}</span></dd>
          <dt v-if="eng.niveau_intensite">Intensité</dt><dd v-if="eng.niveau_intensite">{{ eng.niveau_intensite }}</dd>
          <dt v-if="eng.nda_objet || eng.nda_traitement">NDA</dt>
          <dd v-if="eng.nda_objet || eng.nda_traitement" class="prose">{{ eng.nda_objet || '' }}
            <template v-if="eng.nda_duree"> · durée : {{ eng.nda_duree }}</template>
            <template v-if="eng.nda_droit"> · {{ eng.nda_droit }}</template></dd>
        </dl>
      </section>

      <!-- Jalons PTES (bande de phases — clic = faire avancer le jalon) -->
      <section class="panel">
        <div class="p-head">Phases PTES <span class="count">cliquer pour faire avancer</span></div>
        <p v-if="jalonMsg" class="err">{{ jalonMsg }}</p>
        <div class="ptes">
          <button v-for="j in jalonsByPhase" :key="j.phase" type="button"
                  :class="['ptes-step', ptesStepClass(j.jalon), { busy: jalonBusy === j.phase }]"
                  :disabled="jalonBusy !== null"
                  :title="j.jalon ? 'Faire avancer le jalon' : 'Planifier la phase (en cours)'"
                  @click="cycleJalon(j)">
            <span class="ph">{{ enumLabel(j.phase) }}</span>
            <span class="pm">{{ j.jalon ? enumLabel(j.jalon.statut) + (j.jalon.date_reelle ? ' · ' + j.jalon.date_reelle : '') : 'non planifié' }}</span>
          </button>
        </div>
      </section>

      <!-- Actions de test -->
      <section class="panel">
        <div class="p-head">Actions de test <span class="count">{{ actions.length }}</span>
          <span class="spacer" />
          <button class="btn slim" @click="actionOpen = true">+ Ajouter une action</button>
        </div>
        <table v-if="actions.length" class="dense">
          <thead><tr><th>Phase</th><th>Titre</th><th>ATT&amp;CK</th><th>Résultat</th><th class="act-col"></th></tr></thead>
          <tbody>
            <tr v-for="a in actions" :key="a.id">
              <td><span class="pill pill-violet">{{ enumLabel(a.ptes_phase) }}</span></td>
              <td>{{ a.titre }}</td>
              <td class="mono">{{ a.technique_attack ? refLabel('attack', a.technique_attack) : '—' }}</td>
              <td><span v-if="a.resultat" :class="['pill','pill-'+statutPill(a.resultat)]">{{ enumLabel(a.resultat) }}</span>
                <span v-else class="faint">—</span></td>
              <td class="row-act">
                <button class="btn slim" title="Modifier" @click="editAction(a)">✎</button>
                <button class="btn slim danger" title="Supprimer" @click="delAction(a)">Suppr.</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="faint">Aucune action.</p>
      </section>

      <!-- Vulnérabilités liées à l'audit -->
      <section class="panel">
        <div class="p-head">Vulnérabilités <span class="count">{{ vulns.length }}</span>
          <span class="spacer" />
          <button class="btn slim" @click="vulnOpen = true">+ Ajouter une vulnérabilité</button>
        </div>
        <table v-if="vulns.length" class="dense">
          <thead><tr><th>Titre</th><th>Sévérité</th><th>Statut</th><th>CVE</th></tr></thead>
          <tbody>
            <tr v-for="v in vulns" :key="v.id">
              <td>{{ v.titre || '—' }}</td>
              <td><span v-if="v.severite" :class="['pill','pill-'+sevPill(v.severite)]">{{ enumLabel(v.severite) }}</span>
                <span v-else class="faint">—</span></td>
              <td><span :class="['pill','pill-'+statutPill(v.statut)]">{{ enumLabel(v.statut) }}</span></td>
              <td class="mono">{{ v.cve || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="faint">Aucune vulnérabilité liée.</p>
      </section>

      <!-- Exercices Purple -->
      <section class="panel">
        <div class="p-head">Exercices Purple <span class="count">{{ exercices.length }}</span></div>
        <table v-if="exercices.length" class="dense">
          <tbody>
            <tr v-for="ex in exercices" :key="ex.id">
              <td>{{ ex.nom }}</td><td>{{ ex.date || '—' }}</td>
              <td><span :class="['pill','pill-'+statutPill(ex.statut)]">{{ enumLabel(ex.statut) }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-else class="faint">Aucun exercice rattaché.</p>
      </section>

      <!-- Livrables -->
      <section class="panel">
        <div class="p-head">Livrables <span class="count">{{ deliverables.length }}</span>
          <span class="spacer" />
          <div class="gen-btns">
            <select v-model="genLangue" class="lang-sel" :disabled="genBusy !== null" title="Langue du livrable">
              <option value="fr">FR</option>
              <option value="en">EN</option>
            </select>
            <button v-for="ty in DELIVERABLE_TYPES" :key="ty.v" class="btn slim"
                    :disabled="genBusy !== null" @click="generateDeliverable(ty.v)">
              {{ genBusy === ty.v ? 'Génération…' : '+ ' + ty.label }}
            </button>
          </div>
        </div>
        <p v-if="genMsg" :class="['msg', genMsg.kind]">{{ genMsg.text }}</p>
        <table v-if="deliverables.length" class="dense">
          <tbody>
            <tr v-for="d in deliverables" :key="d.id">
              <td>{{ DELIVERABLE_LABELS[d.type] || d.type }}</td>
              <td>{{ fmtDate(d.created_at) }}</td>
              <td><span :class="['pill', 'pill-' + (TLP_TONE[d.tlp] || 'gray')]">TLP:{{ d.tlp }}</span></td>
              <td class="ta"><button class="btn slim" @click="downloadDeliverable(d)">Télécharger</button></td>
            </tr>
          </tbody>
        </table>
        <p v-else class="faint">Aucun livrable généré.</p>
      </section>

    </div>

    <EngagementForm v-if="engOpen" :audit="audit" :defaults="engagementDefaults"
                    @saved="onEngSaved" @close="engOpen = false" />

    <EntityForm
      v-if="actionOpen"
      entity="audit_actions"
      :fields="ENTITY_FIELDS.audit_actions"
      :prefill="{ audit_id: audit.id, client_id: audit.client_id }"
      :hidden="['audit_id', 'client_id']"
      title="Nouvelle action de test"
      @saved="onActionSaved"
      @close="actionOpen = false"
    />

    <EntityForm
      v-if="editingAction"
      entity="audit_actions"
      :fields="ENTITY_FIELDS.audit_actions"
      :record="editingAction"
      :hidden="['audit_id', 'client_id']"
      title="Modifier l'action de test"
      @saved="onActionSaved"
      @close="editingAction = null"
    />

    <EntityForm
      v-if="vulnOpen"
      entity="vulnerabilities"
      :fields="ENTITY_FIELDS.vulnerabilities"
      :prefill="{ audit_id: audit.id, client_id: audit.client_id }"
      :hidden="['audit_id', 'client_id']"
      evidence-upload
      title="Nouvelle vulnérabilité"
      @saved="onVulnSaved"
      @close="vulnOpen = false"
    />
  </DetailDrawer>
</template>

<style scoped>
.stack{display:flex;flex-direction:column;gap:14px}
.slim{padding:3px 9px;font-size:11.5px}
.danger{color:var(--red);border-color:var(--c-red-bd)}
.act-col{width:1%}
.row-act{white-space:nowrap;display:flex;gap:6px;justify-content:flex-end}
.muted{color:var(--muted);font-size:13px}
.faint{color:var(--faint);font-size:12.5px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px}
.kpi{border:1px solid var(--border);border-radius:var(--r-mini);background:var(--surface-2);padding:10px 12px}
.k-label{font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--faint)}
.k-value{font-family:var(--font-display);font-size:22px;color:var(--heading);margin:2px 0}
.k-value.sm{font-size:14px}
.k-foot{font-size:11.5px;color:var(--muted)}
.panel{border:1px solid var(--border);border-radius:var(--r-mini);background:var(--surface);padding:12px 14px}
.p-head{display:flex;align-items:center;gap:8px;font-family:var(--font-display);font-size:13.5px;color:var(--heading);margin-bottom:10px}
.count{color:var(--faint);font-size:12px;font-weight:normal}
.spacer{flex:1}
.gen-btns{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.lang-sel{border:1px solid var(--border);border-radius:var(--r-mini);background:var(--surface-2);
  color:var(--text);font-size:11.5px;padding:3px 6px}
.msg{padding:7px 11px;border-radius:var(--r-mini);font-size:12.5px;margin:0 0 10px}
.msg.ok{background:var(--c-green-bg);color:var(--c-green-tx)}
.msg.ko{background:var(--c-red-bg);color:var(--c-red-tx)}
.dl{display:grid;grid-template-columns:130px 1fr;gap:8px 14px;margin:0;font-size:13px}
.dl dt{color:var(--muted)} .dl dd{margin:0;color:var(--text);word-break:break-word}
.chip{display:inline-block;background:var(--surface-3);border:1px solid var(--border-2);border-radius:var(--r-pill);
  padding:1px 8px;font-size:11.5px;margin:0 4px 4px 0}
.chip.in{border-color:var(--c-green-bd);color:var(--c-green-tx);background:var(--c-green-bg)}
.chip.out{border-color:var(--c-red-bd);color:var(--c-red-tx);background:var(--c-red-bg)}
.ul{margin:0;padding-left:16px}
.prose{white-space:pre-wrap;line-height:1.5}
.ptes{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:6px}
.ptes-step{border:1px solid var(--border);border-radius:var(--r-mini);padding:7px 8px;background:var(--surface-2);
  text-align:left;cursor:pointer;font:inherit;color:inherit;transition:border-color .12s ease, transform .12s ease}
.ptes-step:hover:not(:disabled){border-color:var(--violet, var(--border-2));transform:translateY(-1px)}
.ptes-step:disabled{cursor:default}
.ptes-step.busy{opacity:.6}
.err{color:var(--c-red-tx);font-size:12.5px;margin:0 0 8px}
.ptes-step .ph{display:block;font-size:11px;color:var(--heading)}
.ptes-step .pm{display:block;font-size:10.5px;color:var(--faint);margin-top:2px}
.ptes-step.done{border-color:var(--c-green-bd);background:var(--c-green-bg)}
.ptes-step.run{border-color:var(--c-cyan-bd);background:var(--c-cyan-bg)}
.ptes-step.skip{opacity:.55}
.ttps{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
table.dense{width:100%;border-collapse:collapse;font-size:12.5px}
table.dense th{color:var(--faint);text-align:left;font-weight:normal;font-size:11px;text-transform:uppercase;
  letter-spacing:.04em;padding:4px 8px;border-bottom:1px solid var(--border-2)}
table.dense td{padding:6px 8px;border-bottom:1px solid var(--border-2)}
.mono{font-family:var(--font-mono, monospace);font-size:11.5px}
.ta{text-align:right}
</style>
