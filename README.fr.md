# Cockpit de Pilotage Purple Team

🇬🇧 [English version](README.md)

Plateforme multi-clients de pilotage d'une équipe Purple Team (cybersécurité offensive
et défensive coordonnées). Elle gère le cycle complet : organisations, applications,
ressources, scénarios de menace, audits, exercices Purple, chaînes d'attaque,
observations défensives, vulnérabilités, tickets de détection, livrables — et un
**sous-système de preuves chiffrées** de bout en bout.

Ce dépôt implémente les documents normatifs du projet : cahier des charges v5.0,
architecture technique (DAT) v1.1, spécification Auth & RBAC v2.0 et direction
artistique v2.7.

## Visite guidée

Tour complet de la plateforme, écran par écran, dans l'ordre de la navigation. Captures en
thème SOC sombre (thème B), prises sur le jeu de démonstration. Les parcours détaillés par
rôle sont dans le [guide utilisateur](docs/guide-utilisateur.md).

### Connexion & compte

![Page de connexion](docs/img/login.png)

*Connexion : SSO d'organisation (Keycloak, OIDC + PKCE) ou repli local e-mail / mot de
passe / TOTP. Une fois connecté, la session est **renouvelée silencieusement** tant que
vous êtes actif — pas de redéconnexion intempestive.*

![Mon compte](docs/img/account.png)

*Mon compte : identité et rôle, **enrôlement TOTP** (obligatoire pour les rôles
opérationnels et le step-up), et « fiche auditeur » qui vous rend sélectionnable comme
auditeur des audits de votre périmètre.*

### Pilotage

![Cockpit — tableau de bord Purple Team](docs/img/cockpit.png)

*Cockpit : taux de détection, angles morts, criticals hors SLA, couverture par tactique
MITRE, posture agrégée et derniers événements du journal — limités à votre périmètre.*

![Exercices Purple — boucle Red → Blue → Détection](docs/img/exercices.png)

*Exercices Purple : la boucle Red → Blue → Détection en un écran — KPIs du run (couverture,
étapes jouées, détections, angles morts), décomposition de la posture, timeline des étapes
d'attaque avec verdict défensif (prévenu / alerté / journalisé / sans télémétrie) et création
de tickets de remédiation à la volée.*

![Fiche d'audit — engagement de pentest](docs/img/audit-drawer.png)

*Audits : fiche d'un engagement (ouverte depuis la liste) — avancement PTES, actions de
test, scénario CTI émulé (FIN7) et couverture TTPs ATT&CK de l'audit.*

| | |
|---|---|
| ![Vulnérabilités](docs/img/vulnerabilities.png) | ![Tickets de détection](docs/img/tickets.png) |
| Vulnérabilités & écarts : sévérité, CVSS, SLA calculés, validation CISO/Manager, enrichissement CVE/EPSS. | Tickets de détection : issus des angles morts des exercices, avec technique ATT&CK, contre-mesure D3FEND et règle Sigma. |

![Fiche vulnérabilité](docs/img/vuln-drawer.png)

*Fiche vulnérabilité : identité (client, audit lié, application, SLA), analyse, classification
OWASP Top 10 / CWE / CVSS, et **enrichissement VOC** en ligne via CIRCL — EPSS, CISA KEV,
SSVC, VEX — avec dégradation gracieuse hors-ligne.*

![Fiche ticket de détection](docs/img/ticket-drawer.png)

*Fiche ticket : technique ATT&CK et contre-mesure D3FEND résolues en clair (« T1608.004 —
Drive-by Target », « D3-NTA — Network Traffic Analysis »), description de l'angle mort,
priorité et statut de remédiation.*

### Connaissance

![Matrice ATT&CK — couverture par tactique](docs/img/attack-matrix.png)

*Matrice ATT&CK : tactiques en colonnes (couvertes / total), techniques teintées par statut,
sous-techniques dépliables, badges d'activité, et 4 couches de lecture — Couverture /
Détection / Écart / couche ATT&CK Navigator importée.*

![Scénarios de menace](docs/img/scenarios.png)

*Scénarios de menace : bibliothèque CTI transverse (acteurs émulés, sophistication,
crédibilité Admiralty), import / export **STIX 2.1**.*

![Fiche scénario FIN7](docs/img/scenario-drawer.png)

*Fiche d'un scénario : acteur émulé (FIN7), 50 TTPs et leur couverture ATT&CK par tactique,
contre-mesures D3FEND, angles morts restants et audits liés — le pont entre le renseignement
et l'exercice.*

| | |
|---|---|
| ![Organisations](docs/img/organisations.png) | ![Applications](docs/img/applications.png) |
| Organisations : clients et prestataires, secteur, TLP par défaut — la base du cloisonnement. | Applications : inventaire du périmètre testé, rattaché aux audits et vulnérabilités. |

| | |
|---|---|
| ![Fiche organisation](docs/img/organisation-drawer.png) | ![Fiche application](docs/img/application-drawer.png) |
| Fiche organisation : référent, TLP par défaut et rattachements (applications, audits, ressources). | Fiche application : criticité, environnement et liens vers audits et vulnérabilités du périmètre. |

![Ressources](docs/img/ressources.png)

*Ressources : auditeurs et moyens, rattachés aux organisations et sélectionnables dans les
engagements.*

### Livrables & traçabilité

![Générateur de livrables](docs/img/deliverables.png)

*Livrables : lettres d'engagement, NDA et rapports PTES générés en PDF (headless Chromium)
avec **bandeau de classification TLP**, scellés en stockage verrouillé et tracés au journal.*

![Fiche livrable](docs/img/deliverable-drawer.png)

*Fiche d'un livrable produit : type, client, langue, marquage TLP et téléchargement — chaque
consultation est tracée au journal.*

![Coffre de preuves](docs/img/evidence.png)

*Coffre de preuves : dépôt par URL présignée (les binaires ne transitent jamais par l'API),
sas d'ingestion (antivirus, type réel, chiffrement enveloppe AES-256-GCM), stockage **WORM**
et marquage TLP. Nécessite `make init-vault` pour les premiers dépôts.*

![Journal inviolable](docs/img/journal.png)

*Journal : chaîné par hachage, consultable par tous en lecture seule, modifiable par
personne — le bouton « Vérifier l'intégrité » recalcule la chaîne côté serveur.*

### Système

![Bibliothèque méthodologique](docs/img/bibliotheque.png)

*Bibliothèque : corpus de 38 articles (procédures, processus, articles métier) filtrables
par profil — auditeur, VOC, CTI, Manager Purple — avec renvois ISO 27002 et gabarits
exportables.*

![Article de la bibliothèque — processus](docs/img/bibliotheque-article.png)

*Lecture d'un processus (« La boucle d'ingénierie de détection ») : déroulement pas à pas
avec points de décision, encadré « à retenir », profils concernés et renvoi ISO 27002
(A.8.16) — la méthodologie au plus près de l'outil.*

![Référentiels de sécurité](docs/img/parametres.png)

*Paramètres — référentiels : catalogue local ATT&CK / ATT&CK Groups / D3FEND / OWASP /
CWE / CAPEC / MISP Threat Actors, synchronisable depuis les sources en ligne (repli sur le
socle embarqué hors-ligne).*

![Administration](docs/img/admin.png)

*Administration (rôle `admin`) : comptes, rôles et **périmètre client** de chaque
utilisateur (sécurité « fail-closed » : périmètre vide = aucun accès pour les rôles
non-manager), création de comptes et désactivation.*

## Doctrine de sécurité — défense en profondeur (4 couches)

Aucune autorisation n'est décidée côté client : **le serveur décide, toujours**.
Les binaires ne transitent jamais par l'API. Quatre couches indépendantes se
superposent, de sorte que la défaillance d'une seule ne compromet pas l'ensemble :

1. **`can()` applicatif** — un moteur à 5 portes (authentification, MFA/step-up,
   matrice RBAC, cloisonnement client, TLP/PAP) évalué à chaque appel, refus par défaut.
2. **RLS PostgreSQL** — Row-Level Security *forcée* (`FORCE ROW LEVEL SECURITY`) sur
   toutes les tables cloisonnées. Le rôle applicatif (`app_api`) est `NOBYPASSRLS` :
   même une requête qui échapperait à la couche 1 ne voit que les clients de son
   périmètre. Sans contexte applicatif établi, **aucune ligne n'est visible**.
3. **Chiffrement enveloppe** — chaque preuve est chiffrée par une clé de données (DEK)
   AES-256-GCM propre à l'audit ; la DEK est elle-même enveloppée par une clé maître
   (KEK) par client, gérée dans Vault (moteur *transit*). Détruire la KEK/DEK rend les
   données irrécupérables (*crypto-shredding*).
4. **Stockage WORM + journal inviolable** — les objets chiffrés sont déposés en MinIO
   avec *Object Lock* (write-once-read-many) ; le journal d'audit est chaîné par hachage
   (tamper-evident) et **immuable applicativement** : aucun rôle, pas même `admin`, ne
   peut le modifier ou le supprimer.

Le déploiement respecte la **règle d'un seul point d'entrée** (DAT §4.1bis) : seul le
reverse proxy `frontend` publie des ports ; tous les autres services ne communiquent
que sur les réseaux Docker internes. Un test de CI (`scripts/check_ports.py`) échoue si
un autre service expose un port.

## Pile technique

| Couche      | Technologie |
|-------------|-------------|
| Backend/BFF | Python 3.11+ (validé sur 3.12) · FastAPI · SQLAlchemy 2 (async) · Alembic |
| Tâches      | Celery + Redis (files `ingest` / `jobs`) |
| Données     | PostgreSQL 15+ (validé sur 16, RLS forcée) |
| Secrets/KEK | HashiCorp Vault (moteur transit) |
| Objets      | MinIO (S3, Object Lock COMPLIANCE) |
| Antivirus   | ClamAV (sas d'ingestion) |
| Identité    | Keycloak (OIDC + PKCE S256) — l'IdP authentifie, le produit autorise |
| Frontend    | Vue 3 · Vite · Pinia · vue-i18n (FR/EN) — thèmes A (clair) / B (SOC sombre) |
| Déploiement | Docker Compose + Makefile |

## Démarrage rapide

Prérequis : Docker, Docker Compose, Make.

```bash
cp .env.example .env          # ajuster les secrets (SEED_DEFAULT_PASSWORD, APP_*_PASSWORD…)
make bootstrap                # premier démarrage complet : stack + schéma + comptes de démo
make init-vault               # (avant le dépôt de preuves) descellement + transit + KEK
```

`make bootstrap` enchaîne `up` (certificat TLS dev généré au besoin), l'attente de la
disponibilité de PostgreSQL, `migrate` (schéma Alembic) et `seed` (référentiels +
comptes de démonstration). Idempotent : peut être relancé sans dommage.

Équivalent manuel, étape par étape :

```bash
make up                       # démarre toute la pile
make migrate                  # applique le schéma (rôle app_migrator)
make seed                     # référentiels + organisations démo + comptes
make seed-demo                # (optionnel) jeu de démo riche — audits, exercices Purple,
                              # vulnérabilités, tickets, scénarios (fait vivre tous les KPIs)
```

`make seed-demo` est idempotent (UUID déterministes) et séparé de `seed`, pour qu'une
instance de production reste exempte de données fictives.

Accès : `https://localhost/` (certificat auto-signé en dev — accepter l'avertissement).
Comptes de démonstration : `admin@purple.local`, `auditeur@purple.local`,
`ciso@purple.local`, `operateur@purple.local` (rôle prestataire multi-clients, scopé aux
deux clients démo). Le mot de passe est la valeur de `SEED_DEFAULT_PASSWORD` dans `.env` ;
le MFA n'étant pas enrôlé sur les comptes de démo, **laissez le champ TOTP vide** à la
connexion (l'enrôlement se fait ensuite via « Mon compte »).

Import de la maquette de démonstration :

```bash
make import-maquette FILE=export.json
```

## Tests

```bash
make test            # suite complète (unitaires + sécurité)
make test-security   # familles bloquantes : isolation RLS, matrice RBAC, sas,
                     # immuabilité du journal, crypto-shredding, exposition réseau
```

Les tests d'isolation RLS s'exécutent contre une vraie base PostgreSQL migrée
(`TEST_DATABASE_URL`), et prouvent notamment qu'une connexion sans contexte ne voit
aucune ligne et qu'une écriture hors périmètre est rejetée par la clause `WITH CHECK`.

## Structure

```
backend/            API FastAPI, workers Celery, migrations, tests
  app/
    security/       matrice RBAC, moteur can() 5 portes, contexte, jetons, OIDC, MFA
    journal/        journal chaîné (tamper-evident)
    storage/        chiffrement enveloppe, Vault, MinIO (WORM)
    models/         ORM (métier + sécurité + preuves)
    api/routes/     auth, entités (CRUD générique), preuves, livrables, admin
    workers/        sas d'ingestion (antivirus, type réel, chiffrement, WORM), jobs
    deliverables/   génération de livrables HTML→PDF (bandeaux TLP)
  sql/              roles.sql (rôles PG) + schema_evidence.sql (DDL preuves + RLS)
  migrations/       Alembic (schéma initial complet)
frontend/           Vue 3 + Vite (tokens DA repris verbatim)
deploy/             nginx (reverse proxy unique), keycloak (realm), vault
scripts/            check_ports.py, backup.sh, restore.sh
docs/               guide utilisateur, déploiement, exploitation, runbook Vault, captures (img/)
```

## Décisions d'architecture (DAT)

D1 Python/FastAPI/SQLAlchemy async · D2 Vue 3 + réemploi des tokens DA ·
D3 Docker Compose (Kubernetes hors périmètre) · D4 rôle géré dans le produit (l'IdP
authentifie seulement) · D5 MFA globale pour les rôles opérationnels + step-up sur les
actions à haut risque · D6 droits Manager en lecture seule sur Ressources/Applications/
Actions · D7 Keycloak embarqué (OIDC + PKCE) · D8 sur-chiffrement côté client reporté.

## Documentation

| Document | Objet |
|---|---|
| `docs/deploiement.md` | Déploiement en production (secrets, ordre d'installation, intégrations, TLS, montée de version) |
| `docs/exploitation.md` | Exploitation courante (synchro référentiels, sauvegarde, vérification du journal, réponse à incident, crypto-shredding) |
| `docs/runbook-vault.md` | Vault en détail (descellement, rotation KEK, crypto-shredding) |
| `docs/guide-utilisateur.md` | Prise en main par rôle et parcours métier |
| `docs/validation.md` | Preuves d'exécution — couverture des tests |
| `docs/RECETTE.md` | Recette et durcissement |

## Licence

Projet interne. Voir les conditions du contrat de prestation.
