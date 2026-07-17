# Purple Cockpit — Cahier des charges v2
 
*Plateforme de pilotage d'une Purple Team en cybersécurité.*
 
*Document de référence unique. Il décrit le système tel qu'il est réellement implémenté (backend FastAPI / PostgreSQL, frontend Vue 3) et la direction artistique de la maquette normative. Il ne contient pas d'historique de versions : il spécifie ce que le produit fait aujourd'hui. Les URLs de toutes les sources externes réellement utilisées par le code sont recensées en Annexe A.*
 
---
 
## Sommaire
 
1. Objet et périmètre
2. Architecture générale
3. Sécurité et gouvernance des accès
4. Modèle de données
5. Fonctionnalités par domaine
6. Règles métier dérivées serveur
7. Traitements asynchrones
8. Intégrations externes
9. Direction artistique — thème UI/UX et CSS
10. Organisation du frontend
11. API — conventions
12. Limites connues et dette assumée
- Annexe A — Sources externes (URLs)
- Annexe B — Glossaire
---
 
## 1. Objet et périmètre
 
Purple Cockpit centralise le pilotage d'audits de sécurité et d'exercices Purple Team. Il couvre : le référentiel client (organisations, applications, ressources), le cadrage et le suivi des audits, la gestion des vulnérabilités avec enrichissement décisionnel (VOC), une bibliothèque de scénarios de menace (CTI), des exercices Purple documentant une chaîne d'attaque technique par technique, la mesure de couverture MITRE ATT&CK, la génération de livrables et la conservation de preuves probantes chiffrées.
 
Le système sert sept profils d'utilisateurs (administrateur, manager, RSSI, auditeur, VOC, CERT/CTI, opérateur), chacun avec un périmètre de droits propre, et cloisonne strictement les données par organisation cliente.
 
**Principe directeur** : le serveur est l'unique autorité de décision. Le frontend n'applique aucune règle de sécurité — il ne fait qu'afficher ou masquer par confort ce que le serveur a déjà autorisé, et chaque action est revalidée côté API.
 
---
 
## 2. Architecture générale
 
### 2.1 Vue d'ensemble
 
```
Navigateur ──(OIDC + PKCE via Keycloak)──► Frontend Vue 3 (build statique, Nginx)
                                                     │ /api (cookies HttpOnly)
                                                     ▼
                                     API FastAPI — BFF (Backend-For-Frontend) :
                                     point unique de décision (RBAC serveur,
                                     contexte RLS, URLs présignées, journalisation)
                                     │        │        │        │
                              PostgreSQL   Vault    MinIO    Keycloak (IdP)
                              (RLS forcée) (transit) (objets  (OIDC)
                                     ▲                chiffrés)
                              Workers Celery (Redis) + pdf-renderer + ClamAV
```
 
### 2.2 Services (déploiement `docker-compose`)
 
| Service | Rôle |
|---|---|
| `frontend` | SPA Vue 3 statique servie par Nginx |
| `api` | FastAPI (BFF), point d'entrée unique `/api` |
| `worker` | Celery — tâches asynchrones (sas de preuves, rétention, intégrité) |
| `beat` | Ordonnanceur Celery (tâches planifiées nocturnes) |
| `pdf-renderer` | Micro-service Chromium headless, rendu HTML → PDF des livrables |
| `postgres` | PostgreSQL 15 — RLS forcée, rôle applicatif `app_api` sans bypass RLS |
| `redis` | File de messages Celery |
| `minio` | Stockage objet chiffré des preuves, avec Object Lock |
| `vault` | Moteur *transit* — chiffrement d'enveloppe (KEK par client) |
| `keycloak` | Fournisseur d'identité OIDC |
| `clamav` | Scan antivirus du sas d'ingestion des preuves |
 
### 2.3 Pile technique
 
- **Backend** — Python / FastAPI, SQLAlchemy 2 asynchrone (`asyncpg`), Alembic (migrations), Celery (asynchrone), `pydantic-settings` (configuration typée, aucun secret en dur).
- **Frontend** — Vue 3 (Composition API), Vite, Pinia, vue-router, vue-i18n (FR/EN). Aucun framework de composants tiers : le design system est celui de la direction artistique (§9), son CSS étant versionné avec le produit.
- **Base de données** — PostgreSQL 15 avec Row-Level Security **forcée** sur toutes les tables cloisonnées par client.
### 2.4 Séparation des rôles base de données
 
Deux rôles PostgreSQL distincts : `app_migrator` (applique les migrations, DDL) et `app_api` (rôle applicatif runtime, **sans** privilège de contournement RLS — `NOBYPASSRLS`). La RLS s'applique donc même au code applicatif ; aucune requête ne peut voir des lignes hors périmètre par erreur de programmation.
 
---
 
## 3. Sécurité et gouvernance des accès
 
Défense en profondeur à quatre portes indépendantes, chacune devant autoriser explicitement :
 
1. **Authentification** — l'appelant est-il qui il prétend être ?
2. **Matrice RBAC** — son rôle peut-il agir sur cette entité (L/C/E/S/V) ?
3. **RLS PostgreSQL** — la ligne appartient-elle à un client de son périmètre ?
4. **Capacités serveur** — les droits calculés sont renvoyés au client, qui affiche/masque en conséquence ; toute action reste revalidée côté serveur.
### 3.1 Authentification
 
- **OIDC + PKCE via Keycloak** (flux nominal). Jeton d'accès court (10 min), jeton de rafraîchissement rotatif (14 jours) organisé en familles révocables en bloc si une réutilisation est détectée.
- **Step-up MFA (TOTP)** exigé pour les actions sensibles, avec fraîcheur maximale de 5 minutes.
- **Comptes locaux de repli** (email + Argon2id + TOTP) : désactivés par défaut, activables par configuration.
- Aucun jeton lisible côté JavaScript (cookies `HttpOnly`) — protection contre le vol de jeton par XSS.
### 3.2 Rôles et matrice RBAC
 
Sept rôles interactifs (**admin, manager, ciso, auditeur, voc, cert, operateur**) et des rôles de service non interactifs à périmètre minimal (`report_render`, `job_retention`, `job_integrity`, `admin_service`).
 
La matrice `{rôle → entité → actions}` est une **donnée unique**, chargée au démarrage et testée exhaustivement : chaque couple rôle × entité doit être défini, aucun trou silencieux n'est possible. Actions : **L** lecture · **C** création · **E** édition · **S** suppression · **V** validation.
 
| Entité | admin | manager | ciso | auditeur | voc | cert | operateur |
|---|---|---|---|---|---|---|---|
| organisations | LCES | L | L | LC | L | L | LCES |
| applications | LCES | L | L | LC | L | L | LCES |
| ressources | LCES | L | L | LC | L | LCES | LCES |
| audits | LCESV | LCES | L | LCES | L | L | LCESV |
| audit_actions | LCESV | LV | L | LCES | L | L | LCESV |
| audit_milestones | LCESV | LV | L | LCES | L | L | LCESV |
| attack_steps | LCES | LCES | L | LCES | L | L | LCES |
| exercices | LCES | LCES | L | LCES | L | L | LCES |
| observations | LCES | L | L | LCES | L | LCES | LCES |
| vulnerabilities | LCESV | LV | LV | LCES | LCES | L | LCESV |
| tickets | LCESV | LV | LV | LCES | L | LCES | LCESV |
| scenarios | LCES | LCES | L | L | L | LCES | LCES |
| scenario_steps | LCES | LCES | L | L | L | LCES | LCES |
| corpus | LCES | LCES | L | L | L | LCES | L |
| deliverables | LCES | LCES | L | LC | L | L | LCES |
| journal | L | L | L | L | L | L | L |
| evidence | L E¹ S² | L E¹ | L | L C E¹ | L | L | L C E¹ |
| evidence_access | L | L | L | — | — | — | — |
| audit_dek | — | — | — | — | — | — | — |
 
¹ édition limitée aux métadonnées (TLP/PAP, légende) — jamais le contenu chiffré.
² suppression = crypto-shredding (destruction de la clé), jamais une suppression physique silencieuse.
`audit_dek` (clé d'enveloppe par audit) n'est accessible à **aucun rôle humain** ; seuls les workers de service la manipulent.
 
Points structurants :
- Le **manager** est en lecture seule sur Ressources / Applications / Actions d'audit.
- Le **journal** est en lecture seule pour tous, admin compris (immuabilité applicative).
- Le **CERT** porte le catalogue CTI (scénarios, étapes, corpus) en écriture complète ; l'**auditeur** n'y a qu'un accès en lecture.
- Le **VOC** possède le cycle de vie complet des vulnérabilités mais reste en lecture sur les audits et exercices.
- L'**operateur** est le profil *prestataire multi-clients « super-utilisateur métier »* : il cumule le CRUD complet sur l'inventaire (organisations, applications, ressources), les scénarios et les livrables, et valide (V) ses propres audits, vulnérabilités et tickets. Il reste **strictement cloisonné** à sa liste de clients (`client_scope`) — jamais multi-client de droit : un scope vide ne lui donne aucun accès. Il n'a **aucun** accès au journal d'accès aux preuves ni aux clés d'audit.
### 3.3 Cloisonnement (RLS)
 
Toute table portant un `client_id` (ou équivalent : `organisation.id`, `ressource.organisation_id`) reçoit une politique RLS **forcée** (`FORCE ROW LEVEL SECURITY`). Seules les tables de connaissance globale (scénarios, étapes de scénario, corpus, référentiels de sécurité) et les tables techniques (comptes, jetons, journal) échappent au cloisonnement client — elles ne portent structurellement pas de `client_id`.
 
### 3.4 Journal d'audit (tamper-evident)
 
Table `journal`, **append-only** : un trigger PostgreSQL interdit toute mise à jour ou suppression, y compris pour l'administrateur. Chaque entrée chaîne un `prev_hash`/`curr_hash` (intégrité vérifiable de bout en bout). Toute création/modification/suppression d'entité, tout accès à une preuve et toute action d'administration y sont consignés. Une tâche planifiée vérifie quotidiennement l'intégrité de la chaîne (§7).
 
---
 
## 4. Modèle de données
 
Six familles d'entités. Toutes portent un identifiant `UUID` et des horodatages `created_at`/`updated_at` ; sauf mention contraire, elles utilisent une suppression non destructive (`deleted_at`).
 
### 4.1 Référentiel client
 
- **Organisation** — `nom`, `code` (court, dérivé du nom si omis), `role` (client/prestataire/interne), `secteur`, `contacts`, `tlp_defaut`, `referent_interne`, `siren`, `statut`, `tags`, `commentaires`.
- **Application** (→ organisation) — `nom`, `code`, `version`, `type`, `criticite`, `stack`, `url`, `contact_metier`, `statut`, `exposition` (interne/externe/partenaire), `valeur_metier` (1-5), `tags`, `tlp`.
- **Ressource** (→ organisation) — `nom`, `type` (humaine/matérielle/logicielle/documentaire), `role` (auditeur/cert/soc/ciso/voc), `competences`, `contact`, `description`, `tags`.
### 4.2 Activité d'audit
 
- **Audit** — `nom` auto-généré et figé, `categorie` (Red/Purple/Pentest/BAS), `type_test` (black-box/grey-box/white-box), `scenario_id` (rattachement CTI optionnel), `applications`, `auditeurs` (ressources humaines), `environnement`, `source`, dates, `statut`, `budget`, `priorite` (P1-P4), `notes`, `tlp`, `engagement` (bloc PTES + NDA), `jalons`, `referentiels_methodo`.
- **AuditAction** — action de test datée : `ptes_phase`, `titre`, `description`, `application_id`, `auditeur_id`, `technique_attack`, `outil`, horodatages, `resultat`, `vulnerabilite_id`, `statut`, `attack_chain_step_id`.
- **AuditMilestone** — jalon PTES : `ptes_phase`, `statut`, dates prévue/réelle, `livrable`, `notes`.
Phases PTES : *pre-engagement, reconnaissance, threat-modeling, vulnerability-analysis, exploitation, post-exploitation, reporting*.
 
### 4.3 Cycle Purple
 
- **PurpleExercise** (→ audit) — `nom` auto-généré, `equipe`, `date`, `statut`, `tlp`, `notes`, `run_number` (itérations sur le même audit).
- **AttackStep** — étape de chaîne d'attaque : `ordre`, `technique`, `titre`, horodatages (jouée/détectée/répondue), `verdict` (`prevented` · `alerted` · `logged` · `no_telemetry` · `not_tested`). Chargeable automatiquement depuis le scénario CTI de l'audit, puis réordonnable.
- **DefenseObservation** — observation Blue liée à une étape : `source`, `resultat`, `description`.
- **DetectionTicket** — angle mort : `source_attack_step_id`, `technique_attack`, `mesure_d3fend`, `description`, `priorite`, `statut`, `regle_sigma`, validation, `gap_decouvert_le`.
### 4.4 Vulnérabilités & VOC
 
- **Vulnerability** — `titre` auto-généré, `audit_id` (lien optionnel — applications dérivées), `cve`/`cwe`, `severite`, `cvss_score`/`cvss_vector`, `statut` (**ouverte · en_cours · corrigee · acceptee · faux_positif**), `decouvreur_id` (ressource auditeur/voc), `description`, `recommandation`, `applications`, `techniques` (ATT&CK), `d3fend` (**dérivé serveur**), `owasp_top10`, `phase_decouverte`, `exploitabilite`, `preuve_exploitation`, `impact_metier`, `sla_niveau`/`sla_echeance` (**dérivés serveur**), `tlp` (défaut RED).
- **VulnerabilityEnrichment** — `epss_score`/`epss_percentile`/`epss_date`, `kev`/`kev_date_added`/`kev_due_date`/`kev_ransomware`, `ssvc_decision`, `vex_status`, `enrichment_status`, `enriched_at`, `enrichment_source`, `raw` (cache CIRCL : CPE, CAPEC, références, produits).
- **RemediationTicket** — `statut`, `echeance`, `notes`.
- **SlaRule** — barème paramétrable par client : `niveau` (P1-P4), `condition`, `delai_jours` (90 par défaut).
### 4.5 Connaissance CTI (catalogue global, hors RLS client)
 
- **Scenario** — `nom`, `objectif`, `acteur_emule`, `type_engagement` (red-team/purple-team/tabletop/assumed-breach), `sophistication`, `ioc`/`ioa`/`references`, `source_id`, `credibilite` (Admiralty 1-6), `techniques` et `d3fend` (**dérivés serveur** des étapes), `tlp`/`pap`, `notes`. Rattachement à un client **transitif**, via l'audit qui le référence.
- **ScenarioStep** — chaîne offensive : `ordre`, `technique` (ATT&CK, sous-techniques incluses), `tactique`, `commande`, `description`.
### 4.6 Référentiels de sécurité
 
Cinq catalogues, synchronisables depuis les sources amont ou repliés sur un socle embarqué hors-ligne : **OWASP Top 10**, **CWE**, **CAPEC**, **MITRE ATT&CK** (technique/sous-technique/tactique), **MITRE D3FEND** (technique/catégorie). Clé naturelle `ext_id` (T1566, D3-NTA…) unique par table, rendant la synchronisation idempotente.
 
### 4.7 Livrables & corpus
 
- **Deliverable** — `type` (engagement/nda/rapport), `titre`, `langue`, `tlp`, `statut`, `storage_key`, `meta`.
- **CorpusArticle** — bibliothèque méthodologique : `slug`, `nature`, `profils`, titres FR/EN, `contenu` bilingue, `controles_iso`, `gabarit`.
### 4.8 Sous-système de preuves
 
Chiffrement d'enveloppe systématique (Vault *transit*, une DEK par audit enveloppée par un KEK client) :
- **AuditDek** — clé d'enveloppe (jamais accessible humainement), avec statut de destruction (crypto-shredding).
- **Evidence** — empreintes plaintext/ciphertext, type déclaré vs détecté, statut d'ingestion (`quarantined → scanning → stored`/`rejected`), TLP/PAP, indicateurs PII/secrets, verdict antivirus, rétention, *legal hold*, verrouillage objet.
- **EvidenceAccess** — traçabilité nominative de chaque consultation/téléchargement (motif, accordé/refusé, IP, expiration de l'URL présignée).
### 4.9 Sécurité applicative
 
- **AppUser** — `email`, `role`, `client_scope` (`[]` = tous les clients autorisés), statut, enrôlement MFA, repli mot de passe local.
- **RefreshToken** — rotation par famille, révocable en bloc.
- **Journal** — cf. §3.4.
---
 
## 5. Fonctionnalités par domaine
 
### 5.1 Organisations
Liste + tiroir de détail (60 % de la largeur). En lecture, le tiroir affiche : métadonnées, ressources rattachées, 10 derniers audits (les plus récents), 10 dernières vulnérabilités (avec renvoi vers la page dédiée).
 
### 5.2 Applications
Liste filtrable (recherche + filtres avancés repliables), tiroir accessible en un clic sur une ligne. Contact métier suggéré par autocomplétion depuis les ressources de l'organisation (saisie libre conservée).
 
### 5.3 Ressources
Rôle en autocomplétion sur liste prédéfinie (auditeur/cert/soc/ciso/voc) ; compétences en saisie libre avec suggestions contextuelles (top 10 par rôle, cliquables).
 
### 5.4 Audits
Cadrage complet (client, catégorie, type de test, scénario CTI rattaché, applications/auditeurs), timeline PTES (jalons + actions), bloc engagement (lettre + NDA). Nom et séquence annuelle auto-générés et figés.
 
### 5.5 Exercices Purple
Rattaché à un audit (client/applications/scénario dérivés). Éditeur de chaîne d'attaque : ajout manuel ou **chargement automatique depuis le scénario CTI** (une étape par technique), réordonnancement libre, verdict de détection à 5 valeurs par étape, observation Blue associée, génération de tickets sur les angles morts.
 
### 5.6 Vulnérabilités & VOC
Liste avec filtres repliables (CVE ; clients et applications en autocomplétion multi-valeurs ; sévérité/SLA/statut en puces multi-sélection). Tiroir de détail (60 %) ordonné : identité (client, audit lié, statut, sévérité, découvreur, phase, application(s) dérivées de l'audit, SLA) → analyse → classification (OWASP, CVE avec lien CIRCL, CWE, CVSS) → **carte Enrichissement VOC** (statut, bouton « Enrichir via CIRCL », EPSS/CISA KEV/SSVC/VEX, CPE) → techniques ATT&CK (liens cliquables) → recommandations (texte + D3FEND dérivé, non éditable) → rappel des référentiels.
 
L'enrichissement CIRCL, déclenchable à la demande (CVE requis), pré-remplit CVSS/CWE/description sans écraser une saisie existante, met en cache EPSS/KEV/CPE/CAPEC, recalcule la décision SSVC. Dégradation gracieuse si la source est injoignable.
 
### 5.7 Scénarios de menace (CTI)
Bibliothèque partagée. Un scénario est une **chaîne d'étapes offensives** (technique + tactique + outil/commande + description), pas une liste plate de techniques. Tiroir (60 %) : KPI (acteur, TTPs, couverture mesurée sur les audits liés, audits liés) → identité → **TTPs ATT&CK en tableau matriciel** (tactiques en en-tête de colonnes, techniques en lignes, lecture seule, cliquable) → étapes offensives détaillées → **D3FEND dérivé** (badge de catégorie, cliquable) → contexte d'utilisation (clients, applications, audits, exercices) → export/aperçu STIX 2.1. Import/export STIX 2.1 pour l'interopérabilité TIP.
 
### 5.8 Matrice ATT&CK (globale)
Vue multi-couches (couverture / détection / écart / couche importée) sur le périmètre visible : tactiques en colonnes (ordre kill-chain), techniques en cellules, compteurs (étapes, vulnérabilités, tickets, scénarios), import d'une couche ATT&CK Navigator externe pour comparaison.
 
### 5.9 Cockpit
Tableau de bord d'accueil : KPI résultat-d'abord, posture agrégée par verdict, angles morts par tactique, couverture dans le temps, répartition des vulnérabilités, journal récent. Filtres type/statut/période recalculant l'ensemble des panneaux.
 
### 5.10 Livrables
Génération serveur (HTML → PDF headless) : lettre d'engagement, NDA, rapport PTES avec preuves déchiffrées à la volée et marquages TLP appliqués. Téléchargement par URL présignée de courte durée.

**Langue du livrable (fr/en).** Les trois gabarits sont bilingues : la structure fixe (titres, libellés, en-têtes de tableaux, clauses juridiques types de la lettre d'engagement et du NDA) est traduite selon la langue choisie à la génération. Le **contenu libre** saisi par l'auditeur (objectifs, clauses rédigées à la main, descriptions de vulnérabilités) est rendu tel quel, dans la langue de saisie — un livrable EN peut donc mêler ossature anglaise et clauses rédigées en français.

**Rapport PTES enrichi.** Outre la synthèse et le tableau récapitulatif des vulnérabilités, le rapport comporte :
- un **registre des preuves** façon investigation numérique (une ligne par preuve : horodatage de dépôt, nom de fichier, type MIME détecté, empreinte SHA-256 du clair, taille, déposant) ;
- une **fiche détaillée par vulnérabilité** reprenant toutes les métadonnées saisies par l'auditeur (CVSS score/vecteur, OWASP, statut, exploitabilité, phase de découverte, découvreur, SLA, EPSS/KEV/SSVC/VEX, techniques ATT&CK, mesures D3FEND, description, impact métier, preuve d'exploitation, recommandation), suivie du **tableau des preuves associées** (liées par `finding_id`, référencées par la même empreinte SHA-256 que le registre) ;
- pour les preuves **image non secrètes** sous une limite de taille, un **aperçu inline** déchiffré (data URI), afin que le client constate la preuve à la lecture. Les preuves `contains_secrets` ne sont jamais affichées en clair (nom masqué, aperçu masqué) ; chaque preuve effectivement déchiffrée pour inclusion est tracée nominativement dans `evidence_access` (custody).
 
### 5.11 Preuves
Dépôt par glisser-déposer (depuis la galerie, mais aussi lors de la création d'une vulnérabilité et depuis la section « Preuves » du détail d'une vulnérabilité), sas d'ingestion asynchrone (détection de type réel, scan antivirus, chiffrement, stockage verrouillé), galerie par entité porteuse, chaîne de custody consultable, rétention et crypto-shredding pilotés par job planifié. **Consultation du contenu en clair** : le téléchargement renvoie le fichier **déchiffré par le serveur** (le binaire au repos reste chiffré et illisible sans la DEK) ; le clair ne vit qu'en mémoire, chaque accès (accordé ou refusé) est tracé dans `evidence_access`, et les preuves `contains_secrets` ne sont jamais servies en clair par cette voie.
 
### 5.12 Paramètres — référentiels de sécurité
Page dédiée à l'alimentation et à l'actualisation des cinq catalogues locaux (ATT&CK, D3FEND, OWASP, CWE, CAPEC) qui peuplent les tables `ref_*` consommées par les formulaires et l'analytique. Les catalogues sont regroupés par thème (vulnérabilités & faiblesses / techniques adverses / défense). Chaque catalogue affiche son état : importé ou non, date de dernière mise à jour, source, et un compteur `entrées chargées / entrées disponibles`.
 
Deux actions distinctes, réservées à l'administrateur (les autres rôles sont en consultation seule) :
 
- **Importer / Réimporter** — charge le catalogue depuis le **socle embarqué** livré avec le produit. Fonctionne hors-ligne, idempotent (aucun doublon en cas de réimport). Disponible pour les cinq catalogues.
- **Sync en ligne** — récupère le **catalogue complet depuis la source amont MITRE** (bundle STIX ATT&CK, ontologie D3FEND). Réservé aux deux catalogues MITRE (ATT&CK, D3FEND). **Dégradation gracieuse** : si la source amont est injoignable, repli automatique sur le socle embarqué avec message d'avertissement explicite — l'opération n'échoue jamais brutalement.
Un bouton **« Tout synchroniser »** actualise l'ensemble des catalogues depuis le socle embarqué en une action. Le périmètre exact des catalogues (complets vs sous-ensembles curés) est rappelé sur la page et détaillé au §12.
 
### 5.13 Bibliothèque, journal, administration
Bibliothèque méthodologique consultable par nature/profil (corpus). Journal consultable et vérifiable (intégrité de la chaîne de hachage). Administration des comptes (création, changement de rôle, désactivation) réservée à l'admin.
 
---
 
## 6. Règles métier dérivées serveur
 
Le client ne fixe jamais une valeur que le serveur peut calculer de façon fiable ; ces champs sont exclus de la liste blanche d'écriture et recalculés à chaque opération pertinente.
 
- **6.1 Identifiants auto-générés** — `Audit.nom`, `Vulnerability.titre`, `PurpleExercise.nom` sous forme `{PRÉFIXE}_{AAAAMM}-{NN}_{CLIENT}`, `period`/`seq` figés à la création (séquence mensuelle par client).
- **6.2 Techniques & D3FEND dérivés** — `Scenario.techniques` = techniques dédupliquées des étapes ; `Scenario.d3fend` et `Vulnerability.d3fend` = D3FEND suggéré depuis les techniques (§6.5), recalculés à chaque écriture. Les étapes d'un scénario sont synchronisées transactionnellement (remplacement intégral à chaque sauvegarde).
- **6.3 SLA des vulnérabilités** — `sla_niveau`/`sla_echeance` dérivés du CVSS à la création ; un statut clos (corrigee/acceptee/faux_positif) sort la vulnérabilité du calcul de dépassement.
- **6.4 Intégrité référentielle applicative** — applications ∈ client de l'audit ; auditeurs = ressources humaines ; audit lié à une vulnérabilité ∈ même client. Toute violation renvoie une erreur 422 explicite (jamais un 500 de contrainte brute).
- **6.5 Correspondance ATT&CK → D3FEND** — table curée embarquée couvrant les techniques/sous-techniques du socle vers dix techniques D3FEND (tactique *Detect*). **Ce n'est pas la correspondance officielle MITRE** ; socle de départ ajustable, également exposé via un endpoint de suggestion à la volée.
- **6.6 Décision SSVC** — arbre déterministe (simplifié, inspiré CISA) à partir de : exploitation active (KEV), probabilité (EPSS), gravité (CVSS) → *Track / Track\* / Attend / Act*.
---
 
## 7. Traitements asynchrones
 
Workers Celery (file Redis) et ordonnanceur `beat` :
 
| Tâche | Déclenchement | Rôle |
|---|---|---|
| `ingest_evidence` | À la demande (dépôt d'une preuve) | Détection du type réel, scan ClamAV, chiffrement (DEK/Vault), stockage MinIO verrouillé, scellement au journal ; rejet en quarantaine si échec |
| `retention_sweep` | Planifié — chaque nuit (02:00) | Application des politiques de rétention, crypto-shredding des preuves échues (hors *legal hold*) |
| `integrity_check` | Planifié — chaque nuit (03:00) | Contrôle d'intégrité des objets stockés (empreintes) |
| `journal_verify` | Planifié — chaque nuit (03:30) | Vérification de la chaîne de hachage du journal (détection d'altération) |
 
Le rendu des livrables PDF est délégué au micro-service `pdf-renderer` (Chromium headless).
 
---
 
## 8. Intégrations externes
 
Toutes les intégrations réseau sont *best-effort* : une source injoignable ne bloque jamais une opération utilisateur, elle dégrade proprement (statut explicite, saisie manuelle de repli). Les URLs précises figurent en **Annexe A**.
 
| Source | Usage | Dégradation |
|---|---|---|
| **CIRCL Vulnerability-Lookup** | Enrichissement CVE : CVSS, CWE, description, CAPEC, CPE, références | Statut « différé », saisie manuelle |
| **CIRCL EPSS (endpoint dédié)** | Score/percentile EPSS (source prioritaire) | Repli sur l'EPSS de l'agrégat principal s'il est présent |
| **MITRE ATT&CK (bundle STIX)** | Synchronisation optionnelle du catalogue complet (admin) | Repli sur le socle embarqué |
| **MITRE D3FEND (ontologie JSON)** | Synchronisation optionnelle du catalogue (admin) | Repli sur le socle embarqué |
| **Liens de référence** (attack.mitre.org, d3fend.mitre.org, cve.circl.lu) | Ouverture de la fiche officielle depuis un badge cliquable | — (navigation externe) |
| **STIX 2.1** | Import/export de scénarios | — (local, sans dépendance réseau) |
 
---
 
## 9. Direction artistique — thème UI/UX et CSS
 
Le design system reprend intégralement la maquette de référence (aucun framework de composants tiers ; CSS versionné avec le produit). Deux thèmes commutables au niveau `body[data-theme]`. Tokens exprimés en variables CSS (`:root` + surcharge par thème).
 
### 9.1 Tokens de structure (communs)
 
```
--r-panel:14px; --r-card:9px; --r-pill:7px; --r-mini:6px;    /* rayons */
--gap:12px; --gap-lg:16px; --pad-panel:18px;                 /* espacements */
--topbar-h:56px; --sidebar-w:188px;                          /* gabarit */
--t-fast:120ms; --t:200ms; --ease:cubic-bezier(.4,0,.2,1);   /* transitions */
```
 
### 9.2 Thème A — Material clair / violet
 
Fond `#F4F2F9`, surfaces `#FFFFFF`/`#FBFAFD`, texte `#211C32`, muté `#6B6480`. Accent violet `#7C3AED` (CTA `#A855F7`, accent `#6D28D9`). Vert `#2FA84F`, ambre `#F5A623`, cyan `#0E9BB5`, rouge `#E5484D`, bleu `#3B82F6`. Ombre `0 2px 14px rgba(60,40,100,.08)`.
Typographies : **Poppins** (titres), **Inter** (corps, données, eyebrows).
 
### 9.3 Thème B — SOC sombre / opérationnel
 
Fond `#0E0B16`, surfaces `#17131F`/`#15111E`/`#181322` (élévations subtiles), champ `#1A1526`, bordures `#271F38`/`#241E33`. Texte `#C9C2DE`, titres `#F1EEFA`, muté `#8B82A0`, estompé `#6A6280`. Accent violet `#8B5CF6`/`#A78BFA`. Vert `#34C759`, ambre `#FFB020`, cyan `#22D3EE`, rouge `#FF5A60`, bleu `#5B8DEF`. Ombre `0 2px 14px rgba(0,0,0,.45)`.
Typographies : **Space Grotesk** (titres), **IBM Plex Mono** (données, eyebrows) — esthétique « terminal ops » assumée.
 
### 9.4 Système de puces (« soft chips »)
 
Chaque famille sémantique déclare un triplet fond/bordure/texte (`--c-{famille}-bg` / `-bd` / `-tx`) : violet, rouge, ambre, vert, cyan, bleu, gris. Une pastille catégorielle est **toujours** ce motif (fond teinté + bordure + texte de la même famille), jamais un aplat plein — réservé aux seuls CTA primaires.
Marquages **TLP** : pastilles dédiées (`--tlp-red/amber/green/clear` + encre `--tlp-ink`).
 
### 9.5 Sémantique des couleurs (constante entre thèmes)
 
Violet = accent produit / sélection · Vert = détecté / couvert / sain · Ambre = partiel / attention · Rouge = angle mort / critique · Cyan = information neutre · Bleu = catégorie *Detect* (D3FEND).
 
### 9.6 Motif transversal : liste + tiroir
 
Les entités de connaissance (Applications, Audits, Vulnérabilités, Scénarios, Organisations, Ressources) sont présentées en **liste dense** ; un clic sur une ligne ouvre un **tiroir de détail à 60 % de la largeur**, avec navigation inter-tiroirs. Un seul mécanisme « voir le détail » par entité.
 
### 9.7 Composants récurrents
 
- **Cartes KPI** — eyebrow en majuscules, valeur en gros caractères mono, pastille de contexte dessous.
- **Panneaux à en-tête badgé** — badge coloré (`ATT&CK` rouge, `D3FEND` vert) + titre + méta alignée à droite.
- **Filtres repliables** — recherche visible par défaut ; bouton « Filtres » (avec compteur d'actifs) dépliant sélecteurs multi-valeurs à autocomplétion et puces multi-sélection pour les énumérations courtes.
- **Autocomplétion à puces** — sélection simple (encart réinitialisable) ou multiple (puces retirables), recherche instantanée id/libellé, exclusion des éléments déjà choisis.
- **Tableau matriciel ATT&CK** — tactique en en-tête de colonne, techniques en lignes ; motif unique pour toute vue « matrice », globale ou locale (mini-matrice d'un scénario).
- **Contraste des cartes imbriquées** — une carte sur un panneau se détache par `--border` (+ `--shadow`), les tokens de surface adjacents étant volontairement proches en valeur.
### 9.8 Accessibilité
 
Contrastes WCAG AA, navigation clavier des autocomplétions (flèches, Entrée, Échap), fermeture des tiroirs au clic extérieur ou à Échap.
 
---
 
## 10. Organisation du frontend
 
### 10.1 Vues
Cockpit (accueil), Organisations, Applications, Ressources, Audits (+ détail), Exercices Purple (+ détail), Vulnérabilités, Tickets, Scénarios, Matrice ATT&CK, Livrables, Preuves, Bibliothèque, Journal, Paramètres, Compte, Administration.
 
### 10.2 Composants transverses notables
`EntityTable` / `EntityForm` / `EntityDrawer` (liste, formulaire et tiroir génériques pilotés par un schéma de champs déclaratif), `RefPicker` / `RefacSelect` (autocomplétion référentiel ou entité liée), `StepsEditor` (chaîne d'étapes offensives + aperçu live de la mini-matrice), `AttckTtpMatrix` (mini-matrice ATT&CK lecture seule, réutilisée entre tiroir Scénario et aperçu de formulaire), `TlpSelect`, palette de commandes (⌘K).
 
### 10.3 État et données
Stores Pinia par domaine (authentification, périmètre client actif). Aucune donnée sensible en `localStorage`/`sessionStorage`. Client API générique consommant les capacités (`can`) renvoyées par le serveur pour l'affichage conditionnel des actions.
 
---
 
## 11. API — conventions
 
- Préfixe unique `/api`, sessions par cookies `HttpOnly`.
- **CRUD générique piloté par un registre d'entités** (`EntitySpec` : modèle ORM, colonne de cloisonnement, liste blanche d'écriture, champs auto, colonnes filtrables, tri) : `GET/POST/PUT/DELETE /api/{entité}` généré par entité, avec permission RBAC + session RLS systématiques.
- **Filtrage** — uniquement sur les colonnes déclarées `filterable` (liste blanche stricte).
- **Endpoints spécifiques** — authentification (`/api/auth/*`), vulnérabilités (`/api/vulnerabilities-enriched`, `/enrich`, `/enrichment`), analytique (`/api/analytics/attack-matrix`, `/cockpit`, `/applications-coverage`, `/scenario-usage/{id}`), référentiels (`/api/reference/catalogs`, `/{catalog}/entries`, `/{catalog}/import`, `/{catalog}/sync`, `/import-all`, `/d3fend/suggest`), STIX (`/api/stix/*`), preuves (`/api/evidence/*`), livrables (`/api/deliverables/*`), exercices (`/api/exercices/{id}/load-scenario`, `/reorder`), journal & administration (`/api/journal*`, `/api/admin/*`).
---
 
## 12. Limites connues et dette assumée
 
- **Correspondance ATT&CK → D3FEND** — socle curé, dix techniques D3FEND (tactique Detect uniquement), pas la correspondance officielle MITRE.
- **Catalogues ATT&CK / CAPEC / D3FEND embarqués** — sous-ensembles curés hors synchronisation en ligne, pas les référentiels MITRE intégraux (la synchro admin rapatrie le catalogue ATT&CK complet).
- **Scénarios antérieurs aux étapes offensives** — conservent leurs `techniques`/`d3fend` figés tant qu'ils ne sont pas réédités (pas de migration rétroactive automatique).
- **`Vulnerability.decouvreur`** (texte libre historique) — conservé pour compatibilité, non alimenté par le formulaire actuel, remplacé par `decouvreur_id`.
---
 
## Annexe A — Sources externes (URLs)
 
*Recensement exhaustif des URLs externes réellement présentes dans le code (hors services internes du `docker-compose` : postgres, redis, vault, minio, keycloak, clamav, pdf-renderer, qui sont des hôtes de déploiement configurables). Toutes sont surchargées par variable d'environnement.*
 
### A.1 Enrichissement des vulnérabilités (appels serveur)
 
| Usage | URL | Variable d'env. |
|---|---|---|
| Enrichissement CVE (agrégat CIRCL) | `https://vulnerability.circl.lu` → `…/api/vulnerability/{cve}` | `ENRICHMENT_BASE_URL` |
| Score EPSS (endpoint CIRCL dédié) | `https://cve.circl.lu` → `…/api/epss/{cve}` | `ENRICHMENT_EPSS_URL` |
 
### A.2 Synchronisation des référentiels (appels serveur, admin)
 
| Usage | URL | Variable d'env. |
|---|---|---|
| Catalogue MITRE ATT&CK (bundle STIX Enterprise) | `https://raw.githubusercontent.com/mitre-attack/attack-stix-data/refs/heads/master/enterprise-attack/enterprise-attack.json` | `ATTACK_STIX_URL` |
| Ontologie MITRE D3FEND (JSON) | `https://raw.githubusercontent.com/d3fend/d3fend/refs/heads/gh-pages/ontologies/d3fend.json` | `D3FEND_ONTOLOGY_URL` |
 
### A.3 Liens de référence (navigation utilisateur / métadonnées STIX)
 
| Usage | Modèle d'URL |
|---|---|
| Fiche technique ATT&CK (chip cliquable + `external_references` STIX) | `https://attack.mitre.org/techniques/{Txxxx}/` (sous-technique : `…/{Txxxx}/{nnn}/`) |
| Fiche contre-mesure D3FEND (chip cliquable) | `https://d3fend.mitre.org/technique/d3f:{SlugCamelCase}/` |
| Fiche CVE CIRCL (chip cliquable) | `https://cve.circl.lu/vuln/{cve-en-minuscules}` |
 
### A.4 Standards et formats de référence (implémentés, sans dépendance réseau directe)
 
| Standard | Rôle dans le produit |
|---|---|
| STIX 2.1 (OASIS) | Format d'import/export des scénarios de menace |
| MITRE ATT&CK | Taxonomie des techniques offensives |
| MITRE D3FEND | Taxonomie des contre-mesures défensives |
| OWASP Top 10 / CWE / CAPEC | Classification des vulnérabilités et schémas d'attaque |
| EPSS (FIRST) / CISA KEV / SSVC / CVSS / VEX | Enrichissement décisionnel et priorisation |
| PTES | Phases méthodologiques d'audit |
| TLP / PAP | Marquages de diffusion et d'action |
 
---
 
## Annexe B — Glossaire
 
| Terme | Définition |
|---|---|
| **BFF** | Backend-For-Frontend — l'API est le point de décision unique entre le navigateur et les services internes |
| **RLS** | Row-Level Security — cloisonnement des lignes par client, appliqué par PostgreSQL |
| **RBAC** | Contrôle d'accès par rôle (matrice rôle × entité × action) |
| **VOC** | Vulnerability Operations Center — gestion et priorisation des vulnérabilités |
| **CTI** | Cyber Threat Intelligence — renseignement sur la menace (scénarios) |
| **TTP** | Tactiques, Techniques et Procédures (MITRE ATT&CK) |
| **KEV** | Known Exploited Vulnerabilities (catalogue CISA) |
| **EPSS** | Exploit Prediction Scoring System — probabilité d'exploitation à 30 jours |
| **SSVC** | Stakeholder-Specific Vulnerability Categorization — aide à la décision de remédiation |
| **VEX** | Vulnerability Exploitability eXchange — statut d'exploitabilité d'un produit |
| **DEK / KEK** | Data / Key Encryption Key — chiffrement d'enveloppe des preuves |
| **Crypto-shredding** | Destruction d'une donnée par destruction irréversible de sa clé de chiffrement |
| **TLP / PAP** | Traffic Light Protocol / Permissible Actions Protocol — marquages de diffusion et d'action |
| **PTES** | Penetration Testing Execution Standard — phases méthodologiques d'un test |
 
---
 
*Fin du document.*