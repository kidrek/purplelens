# Document d'Architecture Technique (DAT) — v1.0
## Cockpit de Pilotage Purple Team (multi-clients) — passage maquette → produit
 
**Statut :** document de référence d'implémentation de la **première version fonctionnelle** (frontend + backend + RBAC réel + stockage des preuves).
**Rattachement :** Cahier des charges **v5.0** (fonctionnel, §6quater preuves) · DA **v2.7** (visuel, §5 preuves) · Spécification Backend Auth & RBAC **v2.0** · DDL `schema_evidence.sql` · Maquette `audit-tracker.html` phase 45 (référence de démonstration et spécification UX vivante).
**Doctrine :** ce DAT **ne respécifie pas** ce que les documents amont établissent — il **consolide**, **tranche** les options d'implémentation restées ouvertes, et **complète** ce qui manquait pour construire (stack, DDL métier, déploiement, plan). En cas de divergence apparente, le cahier des charges reste maître sur le *quoi*, la spec backend v2.0 sur le *modèle de sécurité*, le présent DAT sur le *comment construire*.
 
---
 
## 0. Décisions structurantes
 
| # | Décision | Choix retenu | Statut |
|---|----------|--------------|--------|
| D1 | Stack API & workers | **Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Celery + Redis** | ✅ Tranché |
| D2 | Stratégie frontend | **Refonte buildée : Vue 3 + Vite + Pinia**, réemploi intégral des tokens CSS de la DA v2.7 ; la maquette Alpine reste l'outil de démo et la spec UX de référence | ✅ Tranché |
| D3 | Déploiement v1 | **Docker Compose auto-hébergé, piloté par Makefile** (Kubernetes hors périmètre v1) | ✅ Tranché |
| D4 | Source du rôle | 100 % géré dans le produit ; l'IdP authentifie seulement (défaut spec v2 §8 confirmé) | ✅ Tranché |
| D5 | Granularité MFA | MFA globale pour les rôles opérationnels + step-up sur actions à haut risque (défaut spec v2 §8 confirmé) | ✅ Tranché |
| D6 | Droits Manager (3 ambiguïtés v1) | Reprise des valeurs par défaut v1 §3, désormais **figées** (droits réels) | ✅ Tranché |
| D7 | IdP de la v1 | **Keycloak** embarqué dans le compose (OIDC + PKCE) ; Entra/Okta = configuration, pas développement | ✅ Tranché |
| D8 | Mode « client ultra-sensible » (sur-chiffrement client) | Hors périmètre v1 (roadmap, conformément au cahier §6quater.9) | ⏸ Reporté |
 
### Note de décision — D1 (FastAPI + Celery)
FastAPI : typage Pydantic v2 natif (schémas d'API = contrats), async natif (asyncpg, appels Vault/MinIO non bloquants), OpenAPI généré (contrat frontend). Celery + Redis pour le **sas d'ingestion** et les **jobs** (rétention, crypto-shredding, contrôle d'intégrité) : tâches longues, retries, files séparées, supervision mature — le sas est explicitement asynchrone dans le cahier (§6quater.10). Alternative écartée : `arq` (plus léger mais moins outillé pour la supervision d'une file de sécurité). Réversible.
 
### Note de décision — D2 (Vue 3)
Alpine.js est syntaxiquement calqué sur Vue : la migration des templates de la maquette est mécanique (`x-data`→`setup()`, `x-for`→`v-for`, `x-show`→`v-show`). L'intégralité du CSS de la maquette (thèmes A/B, tokens §0 de la DA, familles `.evi-*`, `.corp-*`, puces douces) est du CSS pur, **repris tel quel** comme design system. Le single-file Alpine ne peut pas porter proprement l'auth OIDC (redirections, refresh, 403 RLS) ni les états d'ingestion asynchrones — précisément le cœur de la valeur backend. Écarté : portage de la maquette (mur à la phase Preuves) ; « A puis B » (double coût). La maquette **n'est pas jetée** : elle reste la démo offline et la référence pixel du produit. Réversible en théorie, coûteux en pratique — décision considérée engageante.
 
---
 
## 1. Vue d'ensemble
 
```
                          ┌────────────────────────────────────────────┐
   Navigateur ────────────►  Frontend Vue 3 (build statique, Nginx)    │
   (OIDC + PKCE via ──┐   └───────────────┬────────────────────────────┘
    Keycloak)         │                   │ /api (cookies HttpOnly)
                      │   ┌───────────────▼────────────────────────────┐
                      └───►  API FastAPI (BFF — point unique de        │
                          │  décision : can() serveur, contexte RLS,   │
                          │  émission URL présignées, journalisation)  │
                          └──┬──────────┬──────────┬──────────┬────────┘
                             │          │          │          │
                     PostgreSQL 15   Vault      MinIO      Keycloak (IdP)
                     (RLS, métadonnées, (transit :  (objets     │
                      app_user, journal) KEK/client) chiffrés,  │
                             ▲          ▲        Object Lock)   │
                             │          │          ▲            │
                          ┌──┴──────────┴──────────┴──┐         │
                          │  Workers Celery (Redis)   │◄────────┘
                          │  · sas d'ingestion        │  ClamAV (scan AV)
                          │  · rétention / shredding  │
                          │  · intégrité périodique   │
                          └───────────────────────────┘
```
 
Invariants repris de la spec v2.0 (non renégociables ici) :
- **Aucune décision d'autorisation dans le client** ; le frontend masque, le serveur décide.
- **Aucun binaire via l'API — une exception assumée pour la consultation en clair.** L'**upload** vers la quarantaine passe par URL présignée (l'API ne voit jamais le clair). La **consultation du fichier déchiffré** (`GET /evidence/{id}/content`) fait exception : elle **streame le clair déchiffré à travers l'API**, car seul le serveur peut déballer la DEK (D8 diffère le déchiffrement côté client). Justification sécurité : le clair ne vit qu'en mémoire (aucun plaintext au repos, aucune URL présignée capable de fuiter), le contrôle d'accès est appliqué **sur la requête même** qui délivre les octets, et l'accès est tracé dans `evidence_access`. Le triple contrôle (RBAC + cloisonnement + TLP/PAP) reste appliqué ; les preuves `contains_secrets` ne sont **jamais** servies en clair par cette voie (masquage réservé au rendu de livrable). Le déchiffrement en masse pour un livrable suit le même chemin (unwrap DEK, accès tracés, aperçus image inline dans le rapport PTES).
- **Défense en profondeur à quatre couches** : `can()` API → RLS PostgreSQL → chiffrement d'enveloppe (DEK/audit ← KEK/client Vault) → Object Lock + journal tamper-evident.
- **Journal** : aucun rôle n'a C/E/S, Admin compris ; `evidence_access` trace chaque consultation, refus inclus.
---
 
## 2. Backend — implémentation
 
### 2.1 Stack et bibliothèques
 
| Besoin | Choix | Rôle |
|--------|-------|------|
| Framework API | **FastAPI** + Uvicorn | Routes, dépendances (injection du contexte de sécurité), OpenAPI |
| ORM / accès base | **SQLAlchemy 2.0 async** + asyncpg · **Alembic** | Modèles, migrations versionnées |
| Validation / contrats | **Pydantic v2** | Schémas request/response, config typée (`pydantic-settings`) |
| OIDC / JWT | **Authlib** (flux Authorization Code + PKCE) · **PyJWT** | Auth Keycloak, vérification/émission des jetons |
| Mots de passe locaux | **argon2-cffi** | Comptes de repli (désactivés par défaut) |
| Vault | **hvac** | wrap/unwrap des DEK via le transit engine — l'API ne voit jamais une KEK |
| Object storage | **minio** (SDK) | PUT quarantaine, Object Lock, presign |
| Tâches asynchrones | **Celery** + Redis | Files `ingest` (sas) et `jobs` (rétention, intégrité) séparées |
| Antivirus | **ClamAV** (clamd, via `clamd`/socket) | Verdict + version moteur/base tracés dans `evidence` |
| Crypto objet | **cryptography** (AES-256-GCM) | Nonce 96 bits unique, AAD = `id + audit_id + sha256_plaintext` |
| Tests | **pytest** + httpx + testcontainers | Dont tests d'isolation RLS et tests du sas (cf. §6) |
 
### 2.2 Application de la RLS — le patron obligatoire
 
Deux rôles PostgreSQL distincts :
- `app_migrator` — propriétaire du schéma, utilisé uniquement par Alembic (`make migrate`) ;
- `app_api` — rôle de service **non-superuser, non-owner**, `FORCE ROW LEVEL SECURITY` s'appliquant à lui, seul rôle utilisé par l'API et les workers.
À chaque requête HTTP, une dépendance FastAPI ouvre la transaction et pose le contexte :
 
```sql
BEGIN;
SET LOCAL app.user_id     = '<uuid>';
SET LOCAL app.role        = 'auditeur';
SET LOCAL app.client_scope = '{uuid1,uuid2}';   -- vide = tous (selon rôle)
-- ... requêtes métier ...
COMMIT;
```
 
Les politiques RLS lisent `current_setting('app.client_scope')`. Règles :
1. **Toute table portant `client_id` a une politique RLS** — pas d'exception « temporaire ».
2. Le scope vide signifie *tous clients dans la limite du rôle* (sémantique v1 conservée) ; la politique l'implémente explicitement, jamais par absence de politique.
3. Les **comptes de service** (générateur de livrables `report_render`, jobs) ont leur propre `app_user` et passent par le même mécanisme — périmètre minimal, apparition nominative dans `evidence_access`.
4. Les tests d'isolation (§6) échouent la CI si une table à `client_id` n'a pas de politique (test introspectif sur `pg_policies`).
5. **Cas `organisation` (cloisonnée par sa propre clé)** : sa colonne de scope est son `id`, or l'`id` d'une organisation neuve ne peut par construction figurer dans aucun `client_scope`. Sa politique est donc **scindée par commande** (migration `0009`) : `SELECT/UPDATE/DELETE` exigent l'appartenance au scope (`app_client_visible(id)`), tandis que l'`INSERT` n'exige qu'un **contexte de sécurité établi** (`app_authenticated()`) — le *qui a le droit de créer* reste porté par la matrice RBAC (couche 1). À la création, l'`id` est ajouté au `client_scope` du créateur (visible à sa prochaine connexion). Le SELECT après INSERT (`RETURNING`) impose aussi de satisfaire la politique de lecture ; les modèles ORM posent donc un défaut Python pour `created_at`/`updated_at` afin d'éviter tout `RETURNING` implicite sur cette table.
### 2.3 Modèle de données — DDL métier à produire (livrable du chantier)
 
`schema_evidence.sql` couvre `evidence`, `audit_dek`, `evidence_access`. Le DAT commande la production du **DDL des entités métier**, transposition du modèle IndexedDB de la maquette (cahier §2/§6) :
 
| Groupe | Tables | Points d'attention |
|--------|--------|--------------------|
| Référentiel client | `organisation`, `application`, `ressource` | `organisation.role` (client/prestataire/interne) ; codes courts ; `application.client_id` → RLS |
| Activité d'audit | `audit`, `audit_action`, `audit_milestone` | 7 phases PTES ; catégorie obligatoire ; `audit.scenario_id` (lien transitif v4.1) ; nommage auto figé (`period`/`seq`) |
| Purple / cycle | `purple_exercise`, `attack_step`, `run`, `observation`, `detection_ticket` | KPI mesurés depuis les horodatages (⚖️ v4.6) ; verdicts ; dérivation client/applications depuis l'audit |
| Vulnérabilités / VOC | `vulnerability`, `vulnerability_enrichment`, `remediation_ticket`, `sla_rule` | CVSS 3.1/4.0, EPSS, KEV, SSVC, VEX stockés avec la vuln ; SLA P1–P4 dérivé multi-signaux (§6ter) |
| Connaissance CTI | `scenario`, `scenario_step` | **Sans `client_id`** (catalogue global v4.1) — seule famille hors RLS client, en lecture ; l'écriture reste soumise à la matrice |
| Référentiels | `ref_attack_technique`, `ref_d3fend`, `ref_owasp`, `ref_cwe`, `ref_capec` | Synchronisation serveur depuis `attack-stix-data` / `d3fend-ontology` (reprend le rôle de la page Paramètres de la maquette) |
| Livrables & corpus | `deliverable`, `corpus_article` | Livrables générés côté serveur (§2.5) ; corpus bilingue v4.9 |
| Sécurité | `app_user`, `refresh_token`, `journal`, + tables `schema_evidence.sql` | `journal` : chaîne de hachage, triggers d'immutabilité (INSERT only) |
 
Convention : UUID partout, `created_at/updated_at`, soft delete (`deleted_at`) sur les entités métier — suppression non destructive (cahier v3.2), suppression réelle réservée au crypto-shredding des preuves.
 
### 2.4 API — organisation
 
- **Périmètre v1 des routes** : auth (`/auth/login`, `/auth/callback`, `/auth/refresh`, `/auth/logout`, `/auth/step-up`) ; CRUD des entités du §2.3 ; preuves (`POST /evidence` → URL d'upload quarantaine, `POST /evidence/{id}/ingest` → sas, `GET /evidence?audit_id=&finding_id=` → liste filtrable, `GET /evidence/{id}/content` → **contenu déchiffré streamé** (triple contrôle + trace), `GET /evidence/{id}/download` → URL présignée de l'objet chiffré, `GET /evidence/{id}/custody`) ; livrables ; journal (lecture seule) ; administration (`/admin/users`, journalisée + step-up).
- **La matrice L/C/E/S/V est une donnée, pas du code** : dictionnaire `{role → entité → actions}` unique, chargé au démarrage, appliqué par une dépendance `require(entity, action)` sur chaque route. Le fichier source de la matrice est **généré depuis la spec v2 §3** et testé exhaustivement (§6) — aucune divergence silencieuse possible.
- **`Validation` (V)** est une action distincte : routes dédiées (`POST /vulnerabilities/{id}/validate`) — un rôle peut valider sans pouvoir éditer, conformément à la v4.8.
- Réponses d'erreur : 403 **sans détail exploitable** (la raison précise part au journal, pas au client) — aligné DA §5.4.
### 2.5 Sas d'ingestion et jobs (workers)
 
Implémentation directe du pipeline du cahier §6quater.4, en tâches Celery idempotentes :
 
1. `POST /evidence` : l'API vérifie RBAC + quota, crée la ligne `evidence` à `quarantined`, émet une URL présignée **d'upload vers le préfixe de quarantaine** (non servi), enfile `ingest_evidence(evidence_id)`.
2. Worker : magic bytes (`detected_mime` vs liste blanche) → ClamAV → `sha256_plaintext` → unwrap DEK (Vault, en mémoire uniquement, jamais journalisée) → AES-256-GCM (nonce neuf, AAD) → `sha256_ciphertext` → `PUT` MinIO avec Object Lock → vignette chiffrée (images) → scellement `{evidence_id, sha256_plaintext}` dans le journal → `stored`.
3. Échec d'une étape → `rejected` + raison + purge de la quarantaine, ligne conservée.
4. L'UI suit la progression par polling léger (`GET /evidence/{id}` → `ingest_status`) — suffisant en v1, SSE en option ultérieure.
Jobs planifiés (Celery beat) : **rétention/crypto-shredding** (échéance `retention_until`, respect prioritaire de `legal_hold`, destruction de la DEK = action à step-up quand manuelle), **contrôle d'intégrité** (`sha256_ciphertext` vs relecture MinIO, sans déchiffrement), **vérification de chaîne** du journal.
 
### 2.6 Générateur de livrables (côté serveur)
 
Compte de service `report_render` (rôle dédié, périmètre minimal). Rendu **HTML → PDF** via navigateur headless (Playwright/Chromium dans un conteneur dédié) pour conserver la filière « HTML print » de la maquette et les gabarits de la DA. Le déchiffrement en masse des preuves d'un audit passe par le chemin normal (unwrap DEK, accès tracés nominativement dans `evidence_access`). Marquages TLP/PAP et masquage `contains_secrets` appliqués avant inclusion.
 
---
 
## 3. Frontend — implémentation
 
### 3.1 Stack
 
**Vue 3 (Composition API) + Vite + Pinia + vue-router + vue-i18n.** Pas de framework UI tiers : **le design system est la DA v2.7**, dont le CSS est extrait de la maquette phase 45 et versionné dans `frontend/src/styles/` (tokens §0, thèmes A/B, composants partagés). Fonts : mêmes familles, auto-hébergées (déploiement offline — plus de dépendance Google Fonts, conformément à l'esprit du build offline de la maquette).
 
### 3.2 Règles de portage depuis la maquette
 
- La maquette est la **référence fonctionnelle et pixel** : chaque page portée est recettée par comparaison visuelle avec elle (thème A et B).
- Correspondance : store Alpine → **stores Pinia par domaine** (auth, organisations, audits, exercices, vulnérabilités, scénarios, preuves, référentiels, ui) ; wrapper IndexedDB → **client API généré depuis l'OpenAPI** de FastAPI (types synchronisés).
- **Aucune logique d'autorisation** : le frontend consomme les capacités retournées par l'API (`can` calculé serveur, embarqué dans les réponses) pour masquer les actions — confort, pas sécurité (couche 1 de la défense en profondeur).
- i18n FR/EN structurelle conservée (`vue-i18n`), identifiants normatifs invariants (TLP/PAP, contrôles ISO) — règle DA v2.6.
- Nouveaux écrans backend : **login OIDC**, gestion de session/expiration, **section Preuves** (DA §5 : sas avec progression, galerie, drawer de custody, marquages WORM/legal hold/crypto-shredded, pastilles PII/secrets), **administration des comptes**.
---
 
## 4. Déploiement — Docker Compose + Makefile
 
### 4.1 Services du `docker-compose.yml`
 
| Service | Image | Rôle | Notes |
|---------|-------|------|-------|
| `frontend` | nginx + build Vite | Statique + reverse proxy `/api` | Seul port exposé (443/80) |
| `api` | build FastAPI | BFF | Non exposé directement |
| `worker` | même image, commande Celery | Sas + jobs | Files `ingest` / `jobs` |
| `beat` | même image | Planification | Rétention, intégrité |
| `postgres` | postgres:15 | Métadonnées, RLS | Volume ; init des deux rôles SQL |
| `redis` | redis:7 | Broker Celery | |
| `minio` | minio/minio | Objets chiffrés | **Object Lock activé à la création des buckets** (impératif : ne s'active pas a posteriori) |
| `vault` | hashicorp/vault | KEK/client (transit) | Mode serveur + stockage fichier ; **jamais `-dev` hors développement** |
| `keycloak` | keycloak | IdP OIDC | Realm importé au démarrage |
| `clamav` | clamav/clamav | Scan AV | Mise à jour des définitions au boot |
| `pdf-renderer` | Chromium headless | Livrables | Réseau interne uniquement |
 
Deux réseaux : `edge` (frontend↔api) et `internal` (le reste) ; PostgreSQL/Vault/MinIO/Redis **jamais** sur `edge`. Secrets de dev en `.env` (gitignoré, `.env.example` versionné) ; en production auto-hébergée, secrets injectés hors dépôt et Vault initialisé avec quorum (§4.3).
 
### 4.1bis — Exposition réseau : point d'entrée unique et ports paramétrables
 
**Règle d'or : un seul service publie des ports — le reverse proxy Nginx.** Aucun autre service du compose ne comporte de directive `ports:` ; la communication inter-services passe exclusivement par les réseaux Docker internes (`expose` implicite). Cette règle est **testée en CI** : un contrôle sur `docker compose config` échoue si un service autre que `frontend` publie un port (même mécanique que le test introspectif RLS — l'exposition est traitée comme du code de sécurité).
 
**Paramétrage des ports** — variables `.env`, consommées par le compose et documentées dans `.env.example` :
 
```
EDGE_BIND_ADDRESS=0.0.0.0    # 127.0.0.1 si un proxy/pare-feu amont termine le TLS
EDGE_HTTP_PORT=80            # redirection → HTTPS uniquement
EDGE_HTTPS_PORT=443
```
 
Soit dans le compose : `"${EDGE_BIND_ADDRESS}:${EDGE_HTTPS_PORT}:443"`. Le binding sur `127.0.0.1` permet le déploiement derrière un reverse proxy hôte ou un bastion sans qu'aucun port ne soit joignable depuis le réseau. `make config` affiche la configuration résolue pour vérification avant `make up`.
 
**Cas des services que le navigateur doit atteindre** — deux services sortiraient naturellement du modèle si on ne les traitait pas : MinIO (URL présignées d'upload/download, cahier §6quater.2) et Keycloak (redirections OIDC). Décision : **tous deux passent derrière le même Nginx**, en routage par chemin sur l'unique port exposé :
 
| Route | Cible interne | Condition de cohérence |
|-------|---------------|------------------------|
| `/` | frontend (statique) | — |
| `/api/` | `api:8000` | — |
| `/storage/` | `minio:9000` | `MINIO_SERVER_URL=https://{hôte}/storage` — les signatures présignées incluent l'hôte : l'API doit signer avec l'URL publique, pas l'URL interne |
| `/idp/` | `keycloak:8080` | `KC_HOSTNAME`/`KC_HTTP_RELATIVE_PATH=/idp` pour des redirections OIDC cohérentes |
 
La console d'administration MinIO et l'interface admin Keycloak ne sont **pas** routées par défaut (accès par tunnel SSH ou `docker compose exec` uniquement) ; une variable d'activation explicite (`EXPOSE_ADMIN_CONSOLES=false`) est prévue pour les environnements de développement.
 
> **Note de décision — routage par chemin plutôt que par sous-domaine.** Le sous-domaine (`storage.exemple.fr`, `idp.exemple.fr`) est plus propre pour les cookies et certains durcissements CSP, mais impose DNS + certificats multiples à chaque déploiement auto-hébergé — friction contraire à l'esprit `make init`. Le chemin unique fonctionne avec un seul certificat et une seule entrée DNS. Réversible : les deux cibles internes sont identiques, seul le Nginx et deux variables changent.
 
### 4.2 Cibles Makefile (contrat d'exploitation)
 
```
make up / down / logs      # cycle de vie compose
make config                # affiche la config compose résolue (.env inclus) et
                           #   vérifie qu'aucun service hors frontend ne publie de port
make init                  # première installation : réseaux, buckets MinIO
                           #   (avec Object Lock), realm Keycloak, rôles SQL
make init-vault            # init + unseal interactif, création du transit
                           #   engine et des politiques API (wrap/unwrap only)
make migrate               # alembic upgrade head (rôle app_migrator)
make seed                  # référentiels ATT&CK/D3FEND/OWASP/CWE/CAPEC + données de démo
make import-maquette FILE= # migration §5 : export JSON maquette → API + sas
make test                  # pytest complet (dont isolation RLS, sas, matrice)
make test-security         # sous-ensemble sécurité seul (rapide, pré-commit)
make backup / restore      # pg_dump + snapshot MinIO + export scellé Vault
make unseal                # descellement Vault après redémarrage (quorum)
```
 
### 4.3 Exploitation — points critiques repris du cahier §6quater.10
 
- **Vault est le point de survie** : `make backup` exporte les clés de descellement chiffrées séparément ; procédure de quorum documentée dans `docs/runbook-vault.md`. Perdre les KEK = perdre toutes les preuves (c'est la contrepartie assumée du crypto-shredding).
- Sauvegarde PostgreSQL standard (les DEK enveloppées y sont **inertes** sans Vault) ; MinIO répliqué ou sauvegardé par snapshot.
- Supervision v1 minimale : healthchecks compose, alerte sur file `ingest` bloquée et taux de rejets AV (job → journal), rapport du contrôle d'intégrité périodique.
---
 
## 5. Migration maquette → produit
 
Reprise du chemin spec v2 §7, outillé par `make import-maquette` :
1. Comptes `app_user` créés (Keycloak ou locaux) — les profils simulés deviennent des rôles portés par des comptes.
2. Import de l'export JSON cloisonné existant ; les `client_id` alimentent la RLS.
3. Preuves : ré-ingestion des Blobs **via le sas** (aucune preuve n'entre sans magic bytes + AV + chiffrement) ; horodatages d'origine conservés en métadonnée ; les preuves chiffrées par passphrase sont déchiffrées **par l'utilisateur à l'export** (la plateforme ne demande jamais la passphrase).
4. Nouvelle chaîne de journal côté serveur ; l'entrée de migration fait foi pour la custody.
---
 
## 6. Stratégie de test — la sécurité comme code testé
 
| Famille | Contenu | Bloquant CI |
|---------|---------|-------------|
| **Isolation RLS** | Pour chaque table à `client_id` : un compte scopé client A ne lit/n'écrit jamais une ligne client B, y compris par jointure et par API ; test introspectif `pg_policies` (aucune table oubliée) | ✅ |
| **Matrice RBAC** | Test exhaustif généré : 7 rôles × entités × actions L/C/E/S/V contre la matrice de la spec v2 §3 — toute divergence code/spec échoue | ✅ |
| **Sas d'ingestion** | Fichier EICAR → `rejected` ; MIME menteur → `rejected` ; nominal → `stored` avec double empreinte vérifiée, AAD correcte, entrée de journal chaînée | ✅ |
| **Custody** | Tentative d'UPDATE sur `evidence` (champs custody), sur `journal`, sur objet Object Lock → refus ; `evidence_access` enregistre les refus | ✅ |
| **Crypto-shredding** | Destruction DEK → toutes les preuves de l'audit illisibles, métadonnées et journal intacts | ✅ |
| **Auth** | Rotation refresh, détection de rejeu → invalidation de famille ; step-up exigé sur les 4 actions à haut risque | ✅ |
| **E2E frontend** | Parcours clés (Playwright) : login → cockpit filtré → dépôt de preuve → progression sas → consultation présignée → génération livrable | ✅ (Phase 4+) |
 
---
 
## 7. Plan de réalisation
 
> Estimations en **semaines-personne** indicatives pour 1 à 2 développeurs connaissant le dossier ; chaque phase se conclut par une **recette** dont les critères conditionnent l'ouverture de la suivante. L'ordre reprend la bascule progressive prévue par la spec v2 §7 : le RBAC/RLS d'abord, les preuves sur fondations stables, le frontend contre une API déjà éprouvée.
 
### Phase 0 — Socle (1,5–2 sem)
Compose complet (§4.1) + Makefile ; squelette FastAPI (config, santé, OpenAPI) ; Alembic initialisé avec les deux rôles SQL ; CI (lint, tests, `make test-security`).
**Sortie :** `make init && make up` donne un environnement complet sain ; pipeline CI vert.
 
### Phase 1 — Identité, RBAC, journal (2–3 sem)
`app_user` + OIDC Keycloak (PKCE) + comptes locaux (désactivés par défaut) ; jetons courts + refresh rotatif + révocation ; matrice L/C/E/S/V serveur (donnée générée + testée) ; step-up MFA ; **journal tamper-evident serveur** ; RLS posée sur les premières tables + tests d'isolation en CI.
**Sortie :** tests matrice + isolation + auth verts ; aucune route non protégée (test de couverture des dépendances).
 
### Phase 2 — Entités métier & import (3–4 sem)
DDL complet §2.3 (RLS systématique) ; CRUD API des 13 entités + actions de validation ; sync serveur des référentiels ATT&CK/D3FEND/OWASP/CWE/CAPEC (`make seed`) ; `make import-maquette` (données métier, sans preuves).
**Sortie :** l'export JSON de la maquette s'importe intégralement ; parité de lecture vérifiée par échantillonnage ; isolation RLS verte sur toutes les tables.
 
### Phase 3 — Preuves (3–4 sem) — la brique la plus sensible
Vault transit (KEK/client, politiques minimales) ; `audit_dek` (DEK générée à la création d'audit) ; sas Celery complet (§2.5) ; URL présignées upload/download ; custody + `evidence_access` + WORM deux étages ; jobs rétention/crypto-shredding/intégrité ; ré-ingestion des preuves maquette.
**Sortie :** toute la famille de tests §6 verte ; démonstration : dépôt → rejet EICAR → dépôt nominal → consultation tracée → crypto-shredding démontrable.
 
### Phase 4 — Frontend connecté (4–6 sem)
Design system extrait (tokens DA v2.7) ; shell + auth + navigation ; portage par domaine dans l'ordre de valeur : cockpit 🎛️ → organisations/applications → audits/PTES → exercices Purple/runs → vulnérabilités/VOC → scénarios CTI → **section Preuves (DA §5)** → matrice ATT&CK → bibliothèque → administration.
**Sortie :** parité fonctionnelle avec la maquette (recette visuelle thèmes A/B) + écrans backend ; E2E Playwright verts.
 
### Phase 5 — Livrables & finitions (2–3 sem)
Générateur serveur (§2.6) : lettre d'engagement, NDA, rapport PTES avec preuves inline déchiffrées et marquages TLP/client, masquage secrets ; exports cloisonnés (inclusion transitive des scénarios) ; import/export STIX 2.1 des scénarios.
**Sortie :** livrables conformes aux gabarits de la maquette, générés depuis les données réelles, accès aux preuves tracés au nom du compte de service.
 
### Phase 6 — Recette générale & bascule (1,5–2 sem)
Recette contre les critères §7 du cahier v5.0 ; runbooks (Vault, sauvegarde/restauration testée, incident) ; migration réelle ; la maquette est officiellement requalifiée « démo/formation ».
**Sortie :** restauration complète depuis sauvegarde vérifiée (y compris descellement Vault) ; PV de recette.
 
**Total indicatif : 17 à 24 semaines-personne.** Jalon de démonstration intermédiaire naturel : fin de Phase 3 (le backend complet est démontrable via l'API avant même le frontend).
 
---
 
## 8. Risques et vigilances
 
| Risque | Impact | Parade |
|--------|--------|--------|
| Perte des clés Vault | Perte totale des preuves | Runbook + quorum + sauvegarde testée à chaque `make backup` ; test de restauration en Phase 6 |
| RLS incomplète (table oubliée) | Fuite inter-clients | Test introspectif `pg_policies` bloquant en CI (§6) |
| Object Lock non activé à la création du bucket | WORM inopérant (non rattrapable) | `make init` crée les buckets avec lock ; test de custody en CI |
| Dérive matrice code vs spec | Droits réels divergents du contrat | Matrice = donnée générée depuis la spec + test exhaustif |
| Sous-estimation du portage frontend | Glissement Phase 4 | Portage par domaine avec valeur livrée à chaque incrément ; cockpit en premier |
| Fuite d'une DEK en clair | Crypto-shredding non crédible | Unwrap en mémoire uniquement, jamais journalisé ni sérialisé ; revue dédiée en Phase 3 |
| ClamAV = filet imparfait | Faux sentiment de sécurité | Assumé par le cahier (§6quater.10) : le sas réduit, n'annule pas ; quarantaine jamais servie |
| Dérive d'exposition (port ajouté « temporairement ») | Surface d'attaque élargie silencieusement | Test CI sur `docker compose config` : tout `ports:` hors frontend échoue (§4.1bis) ; consoles admin non routées par défaut |
 
---
 
## 9. Traçabilité documentaire
 
| Sujet | Source normative | Section DAT |
|-------|------------------|-------------|
| Exigences preuves (confidentialité, custody, RGPD…) | Cahier v5.0 §6quater | §2.5, §4.3, §6 |
| Auth, jetons, MFA, comptes | Spec backend v2.0 §1–2 | §2.1, Phase 1 |
| Matrice RBAC & Preuves | Spec v2.0 §3 | §2.4, §6 |
| Défense en profondeur | Spec v2.0 §5.2 | §1 |
| UI Preuves, tokens, accessibilité | DA v2.7 §0, §5, §6 | §3 |
| Migration | Spec v2.0 §7 · Cahier §6quater.11 | §5 |
| Points ouverts tranchés | Spec v2.0 §8 | §0 (D4–D6, D8) |