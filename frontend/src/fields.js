// Schéma des champs éditables par entité — pilote EntityForm.
//
// N'inclut QUE les champs réellement acceptés en écriture par l'API (registry.py,
// liste `writable`), en excluant les champs auto-générés côté serveur (nom/référence,
// period, seq, SLA dérivé…). Le serveur reste l'autorité : ces définitions ne servent
// qu'à présenter des widgets adaptés et un vocabulaire conforme à la DA.
//
// Types : text · textarea · number · date · select · tags (liste CSV) ·
//         client (sélecteur d'organisation cliente) · ref (sélecteur vers une entité).

import { api } from './api/client'

const STATUT_AUDIT = ['planifie', 'en_cours', 'termine', 'suspendu', 'annule']
const STATUT_GEN = ['ouvert', 'en_cours', 'traite', 'clos']
const VERDICT = ['prevented', 'alerted', 'logged', 'no_telemetry', 'not_tested']
const PTES = [
  'pre-engagement', 'reconnaissance', 'threat-modeling', 'vulnerability-analysis',
  'exploitation', 'post-exploitation', 'reporting',
]
const SEVERITE = ['critique', 'haute', 'moyenne', 'basse']
// Vocabulaire de statut des vulnérabilités, aligné sur la maquette (capture d'écran) —
// distinct du STATUT_GEN générique utilisé par d'autres entités (tickets…).
const STATUT_VULN = ['ouverte', 'en_cours', 'corrigee', 'acceptee', 'faux_positif']

// Enrichissement CIRCL déclenché depuis le formulaire (icône à côté du champ CVE).
// N'agit que sur un enregistrement déjà créé (l'API enrichit par id, pas par CVE brut) ;
// exige que le CVE affiché soit bien celui enregistré en base (pas une saisie en cours
// non sauvegardée), pour ne jamais enrichir « à côté » de ce que l'utilisateur regarde.
async function runCirclEnrich({ model, record, isEdit }) {
  if (!isEdit || !record?.id) {
    throw new Error('Enregistrez d’abord la vulnérabilité pour pouvoir l’enrichir via CIRCL.')
  }
  if (!model.cve) throw new Error('Renseignez un identifiant CVE avant enrichissement.')
  if (model.cve !== record.cve) {
    throw new Error('Enregistrez la modification du CVE avant de lancer l’enrichissement.')
  }
  const r = await api.post(`/vulnerabilities/${record.id}/enrich`)
  if (r.status === 'differe' || r.status === 'echec') {
    throw new Error(r.message || 'Enrichissement impossible pour le moment.')
  }
  // Récupère l'enregistrement à jour (CVSS/CWE/description pré-remplis côté serveur,
  // sans écraser une saisie existante — cf. enrich_from_circl) pour compléter le formulaire.
  const full = await api.get(`/vulnerabilities/${record.id}`)
  return {
    cvss_score: full.cvss_score, cvss_vector: full.cvss_vector,
    cwe: full.cwe, description: full.description,
  }
}

// Rôles RH prédéfinis (ressources humaines de la Purple Team) — cahier "constats".
const ROLE_OPTIONS = [
  { value: 'auditeur', label: 'Auditeur' },
  { value: 'cert', label: 'CERT' },
  { value: 'soc', label: 'SOC' },
  { value: 'ciso', label: 'CISO' },
  { value: 'voc', label: 'VOC' },
]

// Top 10 compétences suggérées par rôle — saisie libre conservée, ceci n'est qu'une
// aide à la saisie (cliquer ajoute la compétence à la liste). Ajustable librement.
const COMPETENCES_BY_ROLE = {
  auditeur: [
    'Pentest applicatif', 'Pentest infrastructure', 'Red Team', 'Ingénierie sociale',
    'OWASP Testing Guide', 'Post-exploitation', 'Rédaction de rapport', 'Revue de code',
    'Exploitation Active Directory', 'Sécurité cloud offensive (AWS/Azure/GCP)',
  ],
  cert: [
    'Réponse à incident', 'Forensic', 'Threat hunting', 'Analyse de malware',
    'Rétro-ingénierie', 'Coordination de crise', 'Gestion de vulnérabilités',
    'Threat intelligence', 'EDR/XDR', 'Communication de crise',
  ],
  soc: [
    'Détection SIEM', 'Corrélation d\u2019événements', 'Analyse de logs', 'Triage d\u2019alertes',
    'Règles Sigma/YARA', 'Chasse aux menaces', 'Gestion d\u2019incidents N1/N2',
    'Automatisation SOAR', 'Surveillance réseau', 'Administration EDR',
  ],
  ciso: [
    'Gouvernance SSI', 'Gestion des risques', 'Conformité (ISO 27001, NIS2, DORA)',
    'Pilotage budgétaire sécurité', 'Sensibilisation utilisateurs',
    'Continuité d\u2019activité (PCA/PRA)', 'Relation avec les auditeurs',
    'Reporting direction', 'Politique de sécurité', 'Gestion de crise',
  ],
  voc: [
    'Veille CTI', 'Analyse de vulnérabilités', 'Gestion de correctifs',
    'Scoring CVSS/EPSS', 'Suivi SLA de remédiation', 'Coordination avec les équipes applicatives',
    'Priorisation par le risque', 'Veille CISA KEV', 'Rédaction d\u2019avis de sécurité',
    'Suivi de campagnes de correctifs',
  ],
}

export const ENTITY_FIELDS = {
  organisations: [
    { key: 'nom', label: 'Nom', type: 'text', required: true },
    { key: 'code', label: 'Code court', type: 'text', placeholder: 'auto : slug du nom si vide' },
    { key: 'role', label: 'Rôle', type: 'select', options: ['client', 'prestataire', 'interne'], required: true },
    { key: 'secteur', label: "Secteur d'activité", type: 'text' },
    { key: 'referent_interne', label: 'Référent interne', type: 'text' },
    { key: 'siren', label: 'SIREN', type: 'text' },
    { key: 'tlp_defaut', label: 'TLP par défaut', type: 'tlp' },
    { key: 'statut', label: 'Statut', type: 'select', options: ['actif', 'inactif'] },
    { key: 'tags', label: 'Tags', type: 'tags' },
    { key: 'commentaires', label: 'Commentaires', type: 'textarea' },
  ],
  applications: [
    { key: 'client_id', label: 'Client', type: 'client', required: true },
    { key: 'nom', label: 'Nom', type: 'text', required: true },
    { key: 'code', label: 'Code court', type: 'text', placeholder: 'auto : slug du nom si vide' },
    { key: 'version', label: 'Version', type: 'text' },
    { key: 'type', label: 'Type', type: 'text' },
    { key: 'criticite', label: 'Criticité', type: 'select', options: ['faible', 'moyenne', 'haute', 'critique'] },
    { key: 'stack', label: 'Stack technique', type: 'text' },
    { key: 'url', label: 'URL', type: 'text' },
    { key: 'contact_metier', label: 'Contact métier', type: 'text', dependsOn: 'client_id',
      suggestFrom: { refEntity: 'ressources', refLabel: 'nom', depKey: 'organisation_id' },
      placeholder: 'Nom du contact métier…' },
    { key: 'exposition', label: 'Exposition', type: 'select', options: ['interne', 'externe', 'partenaire'] },
    { key: 'valeur_metier', label: 'Valeur métier', type: 'text' },
    { key: 'statut', label: 'Statut', type: 'select', options: ['actif', 'decommissionne'] },
    { key: 'tlp', label: 'TLP', type: 'tlp' },
    { key: 'tags', label: 'Tags', type: 'tags' },
  ],
  ressources: [
    { key: 'organisation_id', label: 'Organisation', type: 'client', role: null, required: true },
    { key: 'nom', label: 'Nom', type: 'text', required: true },
    { key: 'type', label: 'Type', type: 'select', options: ['humaine', 'materielle', 'logicielle', 'documentaire'] },
    { key: 'role', label: 'Rôle', type: 'refac', options: ROLE_OPTIONS, placeholder: 'Rechercher un rôle…' },
    { key: 'competences', label: 'Compétences', type: 'tags', dependsOn: 'role',
      suggestionsByDep: COMPETENCES_BY_ROLE, placeholder: 'valeurs séparées par des virgules' },
    { key: 'contact', label: 'Contact', type: 'text' },
    { key: 'description', label: 'Description', type: 'textarea' },
    { key: 'tags', label: 'Tags', type: 'tags' },
  ],
  audits: [
    { key: 'client_id', label: 'Client', type: 'client', required: true },
    // Catégorie fermée (cahier §A000.1) — pilote le préfixe de nom et le cockpit.
    // « Purple Team » est volontairement absent : un exercice Purple se greffe sur un
    // audit existant depuis sa propre page ; l'exposer ici induirait l'utilisateur en erreur.
    { key: 'categorie', label: 'Catégorie', type: 'select', required: true,
      options: [
        { value: 'red_team', label: 'Red Team' },
        { value: 'pentest', label: 'Pentest' },
        { value: 'bas', label: 'BAS' },
      ] },
    { key: 'type_test', label: 'Type de test', type: 'select', options: ['black-box', 'grey-box', 'white-box'] },
    { key: 'scenario_id', label: 'Scénario de menace', type: 'ref', refEntity: 'scenarios', refLabel: 'nom' },
    // Cahier §2 (Audits) : application(s) cible(s) — règle d'intégrité : ∈ client de l'audit
    // (le picker se restreint au client choisi ; le serveur revalide).
    { key: 'applications', label: 'Applications cibles', type: 'ref', refEntity: 'applications',
      refLabel: 'nom', multiple: true, dependsOn: 'client_id', placeholder: 'Rechercher une application…' },
    // Auditeurs assignés (ressources humaines) — alimente la lettre d'engagement (§5.A).
    { key: 'auditeurs', label: 'Auditeurs assignés', type: 'ref', refEntity: 'ressources',
      refLabel: 'nom', multiple: true, refFilter: { type: 'humaine' }, placeholder: 'Rechercher un auditeur…' },
    { key: 'environnement', label: 'Environnement', type: 'select', options: ['production', 'pre-production', 'recette', 'laboratoire'] },
    { key: 'source', label: 'Source', type: 'text' },
    { key: 'date_debut', label: 'Date de début', type: 'date' },
    { key: 'date_fin', label: 'Date de fin', type: 'date' },
    { key: 'statut', label: 'Statut', type: 'select', options: STATUT_AUDIT },
    { key: 'priorite', label: 'Priorité', type: 'select', options: ['P1', 'P2', 'P3', 'P4'] },
    { key: 'budget', label: 'Budget (jours-homme)', type: 'number' },
    { key: 'referentiels_methodo', label: 'Référentiels / méthodo', type: 'lines' },
    { key: 'tlp', label: 'TLP', type: 'tlp' },
    { key: 'notes', label: 'Notes', type: 'textarea' },
  ],
  // Bloc engagement (lettre d'engagement / NDA) — édité séparément dans le drawer,
  // écrit dans audit.engagement (JSONB). Calqué sur FIELDS.engagement de la maquette.
  engagement: [
    { key: 'objectifs', label: 'Objectifs', type: 'lines' },
    { key: 'perimetre_inclus', label: 'Périmètre inclus', type: 'lines' },
    { key: 'perimetre_exclus', label: 'Périmètre exclus', type: 'lines' },
    { key: 'regles_engagement', label: "Règles d'engagement", type: 'textarea' },
    { key: 'fenetres_test', label: 'Fenêtres de test', type: 'lines' },
    { key: 'contacts_autorisation', label: 'Contacts autorisation', type: 'lines' },
    { key: 'contacts_urgence', label: 'Contacts urgence', type: 'lines' },
    { key: 'autorisation_signee', label: 'Autorisation signée', type: 'bool', checkboxLabel: 'Signée' },
    { key: 'sow', label: 'SOW', type: 'text' },
    { key: 'ref_nda', label: 'Référence NDA', type: 'text' },
    { key: 'niveau_intensite', label: "Niveau d'intensité", type: 'text' },
    { key: 'livrables_attendus', label: 'Livrables attendus', type: 'lines' },
    { key: 'clauses_legales', label: 'Clauses légales', type: 'textarea' },
    { key: 'nda_objet', label: 'NDA · objet & informations confidentielles', type: 'textarea' },
    { key: 'nda_duree', label: 'NDA · durée', type: 'text' },
    { key: 'nda_traitement', label: 'NDA · traitement & protection', type: 'textarea' },
    { key: 'nda_restitution', label: 'NDA · restitution', type: 'textarea' },
    { key: 'nda_droit', label: 'NDA · droit applicable', type: 'text' },
  ],
  exercices: [
    { key: 'client_id', label: 'Client', type: 'client', required: true },
    { key: 'audit_id', label: 'Audit rattaché', type: 'ref', refEntity: 'audits', refLabel: 'nom' },
    { key: 'equipe', label: 'Équipe', type: 'text' },
    { key: 'date', label: 'Date', type: 'date' },
    { key: 'run_number', label: 'Numéro de run', type: 'number' },
    { key: 'statut', label: 'Statut', type: 'select', options: STATUT_AUDIT },
    { key: 'tlp', label: 'TLP', type: 'tlp' },
    { key: 'notes', label: 'Notes', type: 'textarea' },
  ],
  vulnerabilities: [
    { key: 'client_id', label: 'Client', type: 'client', required: true },
    { key: 'audit_id', label: 'Audit lié', type: 'ref', refEntity: 'audits', refLabel: 'nom',
      dependsOn: 'client_id', placeholder: 'Rechercher un audit…' },
    { key: 'statut', label: 'Statut', type: 'select', options: STATUT_VULN, default: 'ouverte' },
    { key: 'severite', label: 'Sévérité', type: 'select', options: SEVERITE, required: true },
    { key: 'decouvreur_id', label: 'Découvreur', type: 'ref', refEntity: 'ressources', refLabel: 'nom',
      refFilter: { role: ['auditeur', 'voc'] }, placeholder: 'Rechercher un auditeur ou VOC…' },
    { key: 'phase_decouverte', label: 'Phase de découverte', type: 'refac', options: PTES,
      placeholder: 'Rechercher une phase PTES…' },
    { key: 'description', label: 'Description', type: 'textarea', required: true },
    { key: 'impact_metier', label: 'Impact métier', type: 'textarea' },
    { key: 'exploitabilite', label: 'Exploitabilité', type: 'select', options: ['theorique', 'poc', 'exploite'] },
    { key: 'owasp_top10', label: 'OWASP Top 10', type: 'refpick', catalog: 'owasp' },
    { key: 'cve', label: 'CVE', type: 'text', placeholder: 'CVE-2024-XXXXX (enrichissement CIRCL possible ensuite)',
      inlineAction: {
        icon: '🔎', title: 'Enrichir via CIRCL (CVSS, CWE, description, EPSS, KEV, SSVC)',
        enabled: (model, isEdit) => isEdit && !!model.cve,
        run: runCirclEnrich,
      } },
    { key: 'cwe', label: 'CWE', type: 'refpick', catalog: 'cwe' },
    { key: 'cvss_vector', label: 'Vecteur CVSS', type: 'text' },
    { key: 'cvss_score', label: 'Score CVSS', type: 'number', step: '0.1' },
    { key: 'techniques', label: 'Techniques ATT&CK', type: 'refpick', catalog: 'attack', multiple: true },
    { key: 'recommandation', label: 'Recommandations', type: 'textarea' },
    { key: 'tlp', label: 'TLP', type: 'tlp' },
  ],
  scenarios: [
    { key: 'nom', label: 'Nom', type: 'text', required: true },
    { key: 'objectif', label: 'Objectif', type: 'textarea' },
    { key: 'acteur_emule', label: 'Acteur émulé', type: 'text' },
    { key: 'type_engagement', label: "Type d'engagement", type: 'select', options: ['red-team', 'purple-team', 'tabletop', 'assumed-breach'] },
    { key: 'sophistication', label: 'Sophistication', type: 'select', options: ['basique', 'intermediaire', 'avancee', 'apt'] },
    { key: 'credibilite', label: 'Crédibilité (Admiralty)', type: 'select', options: [
      { value: 1, label: '1 — Confirmée par d’autres sources' },
      { value: 2, label: '2 — Probablement vraie' },
      { value: 3, label: '3 — Possiblement vraie' },
      { value: 4, label: '4 — Douteuse' },
      { value: 5, label: '5 — Improbable' },
      { value: 6, label: '6 — Invérifiable' },
    ] },
    { key: 'etapes', label: 'Étapes offensives', type: 'steps', loadFrom: 'scenario_steps', loadKey: 'scenario_id' },
    { key: 'ioc', label: "Indicateurs de compromission", type: 'textarea' },
    { key: 'ioa', label: "Indicateurs d'attaque", type: 'textarea' },
    { key: 'references', label: 'Références', type: 'textarea' },
    { key: 'tlp', label: 'TLP', type: 'tlp' },
    { key: 'pap', label: 'PAP', type: 'tlp', variant: 'pap' },
    { key: 'notes', label: 'Notes', type: 'textarea' },
  ],
  observations: [
    { key: 'client_id', label: 'Client', type: 'client', required: true },
    { key: 'attack_step_id', label: "Étape d'attaque", type: 'ref', refEntity: 'attack_steps', refLabel: 'titre' },
    { key: 'source', label: 'Source (télémétrie)', type: 'text' },
    { key: 'resultat', label: 'Résultat', type: 'select', options: VERDICT },
    { key: 'description', label: 'Description', type: 'textarea' },
  ],
  tickets: [
    { key: 'client_id', label: 'Client', type: 'client', required: true },
    { key: 'technique_attack', label: 'Technique ATT&CK', type: 'refpick', catalog: 'attack' },
    { key: 'mesure_d3fend', label: 'Mesure D3FEND', type: 'refpick', catalog: 'd3fend', multiple: true },
    { key: 'description', label: 'Description', type: 'textarea' },
    { key: 'priorite', label: 'Priorité', type: 'select', options: ['P1', 'P2', 'P3', 'P4'] },
    { key: 'statut', label: 'Statut', type: 'select', options: STATUT_GEN },
    { key: 'regle_sigma', label: 'Règle Sigma', type: 'textarea' },
  ],
  audit_actions: [
    { key: 'client_id', label: 'Client', type: 'client', required: true },
    { key: 'audit_id', label: 'Audit', type: 'ref', refEntity: 'audits', refLabel: 'nom', required: true },
    { key: 'ptes_phase', label: 'Phase PTES', type: 'select', options: PTES, required: true },
    { key: 'titre', label: 'Titre', type: 'text', required: true },
    { key: 'description', label: 'Description', type: 'textarea' },
    { key: 'technique_attack', label: 'Technique ATT&CK', type: 'refpick', catalog: 'attack' },
    { key: 'outil', label: 'Outil', type: 'text' },
    { key: 'resultat', label: 'Résultat', type: 'select',
      options: [
        { value: 'info', label: 'Info' },
        { value: 'succès', label: 'Succès' },
        { value: 'partiel', label: 'Partiel' },
        { value: 'échec', label: 'Échec' },
      ] },
    { key: 'statut', label: 'Statut', type: 'select', options: STATUT_GEN },
  ],
  audit_milestones: [
    { key: 'client_id', label: 'Client', type: 'client', required: true },
    { key: 'audit_id', label: 'Audit', type: 'ref', refEntity: 'audits', refLabel: 'nom', required: true },
    { key: 'ptes_phase', label: 'Phase PTES', type: 'select', options: PTES, required: true },
    { key: 'statut', label: 'Statut', type: 'select', options: ['a_venir', 'en_cours', 'atteint', 'manque'] },
    { key: 'date_prevue', label: 'Date prévue', type: 'date' },
    { key: 'date_reelle', label: 'Date réelle', type: 'date' },
    { key: 'livrable', label: 'Livrable attendu', type: 'text' },
    { key: 'notes', label: 'Notes', type: 'textarea' },
  ],
  attack_steps: [
    { key: 'client_id', label: 'Client', type: 'client', required: true },
    { key: 'exercise_id', label: 'Exercice', type: 'ref', refEntity: 'exercices', refLabel: 'nom', required: true },
    { key: 'ordre', label: 'Ordre', type: 'number' },
    { key: 'technique', label: 'Technique ATT&CK', type: 'text', required: true },
    { key: 'titre', label: 'Titre', type: 'text' },
    { key: 'verdict', label: 'Verdict', type: 'select', options: VERDICT },
    { key: 'horodatage', label: "Exécution de l'attaque", type: 'datetime' },
    { key: 'horodatage_detection', label: 'Détection', type: 'datetime' },
    { key: 'horodatage_reponse', label: 'Réponse', type: 'datetime' },
  ],
}

export function fieldsFor(entity) {
  return ENTITY_FIELDS[entity] || []
}
