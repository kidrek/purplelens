# Spécification Backend — Authentification & RBAC réel
## Cockpit de Pilotage Purple Team (multi-clients) — v2.0
 
**Statut :** spécification de la **cible backend**. Remplace, pour le produit, le **RBAC simulé** de la v1 (sélecteur de profil côté client, `audit-tracker.html`). La v1 reste la référence de la maquette de démonstration.
**Rattachement :** cahier des charges **v5.0** (§3 profils · §6quater stockage des preuves) · DA **v2.7** (§0.6 barre supérieure · §5 Preuves) · DDL `schema_evidence.sql`.
**Principe directeur :** ce que la v1 *simulait* côté client (rôle + `clients_rattaches[]`, matrice L/C/E/S/V, immutabilité du journal), la v2 le rend **opposable** — porté par le serveur, la base (RLS) et la hiérarchie de clés (Vault). Aucun contrôle de sécurité ne repose plus sur le navigateur.
 
---
 
## 0. Ce qui change entre v1 (simulé) et v2 (réel)
 
| Dimension | v1 — maquette (simulé) | v2 — backend (réel) |
|---|---|---|
| **Identité** | Sélecteur de profil, aucun compte | Comptes authentifiés, secret vérifié, MFA |
| **Décision d'accès** | `can()` côté client, contournable via DevTools | Décision **serveur** à chaque requête, jamais dans le client |
| **Cloisonnement** | `clients_rattaches[]` filtrant l'affichage | **Row Level Security** PostgreSQL — invisible même en cas de bug applicatif |
| **Session** | État Alpine en mémoire | Jetons signés à courte vie + rotation, révocables |
| **Journal** | Chaîne de hachage locale | Idem, mais **côté serveur**, alimenté par toutes les décisions sensibles |
| **Preuves** | Blob IndexedDB, chiffrement optionnel par passphrase | Object storage chiffré (DEK/audit, KEK/client Vault), accès sous contrôle RBAC + RLS + TLP/PAP |
 
> **La v2 conserve intégralement le modèle métier de la v1** : 6 rôles, matrice rôle × entité × action (L/C/E/S/V), validation comme action distincte, cloisonnement par client qui *restreint sans jamais élargir*. Elle en change le **lieu d'application** et lui ajoute l'entité **Preuves**.
 
---
 
## 1. Modèle d'authentification
 
### 1.1 Choix de fond — OIDC en façade, comptes locaux en repli
 
Le produit s'adresse à des **prestataires de cybersécurité** opérant pour plusieurs clients : l'identité doit pouvoir venir du **fournisseur d'identité (IdP) du prestataire** (Entra ID, Keycloak, Okta, Google Workspace…), pas d'un annuaire réinventé. Décision :
 
- **OIDC / OAuth 2.1 (Authorization Code + PKCE)** comme mécanisme principal, contre un IdP configurable. L'IdP porte le **cycle de vie du compte** (arrivée/départ, MFA d'entreprise, politique de mot de passe).
- **Comptes locaux** (Argon2id) en **repli**, pour les déploiements sans IdP ou les comptes de service. Non exposés par défaut ; activables par configuration.
- **Le rôle et les clients rattachés ne viennent PAS de l'IdP** : ils sont gérés **dans le produit** (table `app_user`, cf. §4). L'IdP prouve *qui vous êtes* ; le produit décide *ce que vous pouvez faire*. Une revendication (claim) de groupe IdP peut *proposer* un rôle par défaut, jamais l'imposer — l'attribution reste une action d'administration tracée.
> **Justification.** Coupler les rôles Purple (`manager`, `auditeur`, `cert`…) à des groupes IdP obligerait chaque client-prestataire à modéliser notre RBAC dans son annuaire. Séparer authentification (IdP) et autorisation (produit) garde le modèle métier maître chez nous et portable partout.
 
### 1.2 MFA
 
- **MFA obligatoire** pour tout accès à des données `TLP:RED`/`AMBER` ou à des preuves — c'est-à-dire, en pratique, pour tous les rôles opérationnels. Délégué à l'IdP quand il l'assure ; sinon **TOTP** natif (comptes locaux).
- **Step-up authentication** exigée pour les **actions à haut risque** (cf. §3.4) : levée de `legal_hold`, déclenchement d'un crypto-shredding, export d'archive d'audit, changement de rôle d'un compte. Une réauthentification récente (< 5 min) est requise même en session valide.
### 1.3 Sessions & jetons
 
- **Access token** court (JWT signé, ~10 min) portant `sub`, `role`, `client_scope[]`, `mfa`, `auth_time`. Jamais de secret, jamais de clé de chiffrement dedans.
- **Refresh token** opaque, stocké côté serveur (révocable), **rotation à chaque usage** (détection de rejeu → invalidation de la famille).
- **Cookies** `HttpOnly` + `Secure` + `SameSite=Strict` pour le navigateur ; en-tête `Authorization` pour les comptes de service.
- **Révocation immédiate** : désactivation d'un compte, changement de rôle ou de clients rattachés → invalidation des refresh tokens actifs. L'access token expire seul (< 10 min) ; les décisions sensibles revérifient l'état du compte en base (cf. §3.3).
---
 
## 2. Comptes, rôles et clients rattachés
 
### 2.1 Le compte = { identité, rôle, clients rattachés }
 
La v1 modélisait le compte comme `{ profile, clients_rattaches[] }`. La v2 le persiste :
 
```
app_user
  id            uuid
  external_sub  text        -- 'sub' OIDC (NULL si compte local)
  email         text UNIQUE
  display_name  text
  role          text        -- 'admin'|'manager'|'ciso'|'auditeur'|'voc'|'cert'
  client_scope  uuid[]      -- clients rattachés ; [] = tous (selon droits du rôle)
  status        text        -- 'active'|'suspended'|'disabled'
  mfa_enrolled  boolean
  created_at, updated_at, last_login_at
```
 
- Les **6 rôles** de la v1 sont conservés à l'identique (`admin`, `manager`, `ciso`, `auditeur`, `voc`, `cert`).
- `client_scope` reprend `clients_rattaches[]` : **vide = tous clients** (dans la limite des droits du rôle) ; **renseigné = restriction stricte**. Verrouillé à *tous clients* pour `admin` et `manager` (leur raison d'être multi-client), configurable pour `ciso`/`auditeur`/`voc`/`cert` — inchangé depuis la v1.
- Toute création/modification de compte, de rôle ou de `client_scope` est une **action d'administration journalisée** (acteur, avant/après, horodatage), réservée à `admin` + step-up MFA.
### 2.2 Comptes de service
 
Le **générateur de livrables** et les **jobs** (rétention/crypto-shredding, contrôle d'intégrité) sont des comptes de service à rôle dédié, non interactifs, à périmètre minimal (cf. §5.3). Ils apparaissent nommément dans les journaux d'accès aux preuves (`report_render`, `admin_audit`).
 
---
 
## 3. Modèle d'autorisation (RBAC réel)
 
### 3.1 La matrice v1, portée côté serveur — étendue à `Preuves`
 
La **matrice rôle × entité × action (L/C/E/S/V)** de la v1 §3 est reprise pour les 13 entités existantes — avec **une extension v2 des droits Auditeur** (⁴ ci-dessous) — et **étendue** aux deux entités du sous-système de preuves (cahier §6quater.7) :
 
| Entité | Admin | Manager | RSSI/CISO | Auditeur | VOC | CERT/Blue |
|---|---|---|---|---|---|---|
| **Organisations** | LCES | L | L | **LC** ⁴ | L | L |
| **Applications** | LCES | L | L | **LC** ⁴ | L | L |
| **Ressources** | LCES | L | L | **LC** ⁴ | L | LCES |
| *(… 10 autres entités v1 inchangées : Audits, Actions, Attaques, Exercices, Observations, Vulnérabilités, Tickets, Scénarios, Livrables, Journal …)* | | | | | | |
| **🗄️ Preuves** (`evidence`) | L E¹ S² | L E¹ | L | **L C E¹** | L | L |
| **🗄️ Journal d'accès preuves** (`evidence_access`) | L | L | L | — | — | — |
| **🗄️ Clés d'audit** (`audit_dek`) | — ³ | — | — | — | — | — |
 
¹ **E limité aux champs non-custody** (légende, `tlp`/`pap`, `contains_pii`/`contains_secrets`). L'immutabilité des champs de custody (empreintes, localisation, crypto, auteur, horodatages, scellement) est portée par un **trigger base** (`schema_evidence.sql`), pas par la matrice — défense en profondeur.
² **S = soft delete uniquement** (`deleted_at`), **refusé** si `legal_hold` actif ou Object Lock non échu. La destruction effective du contenu passe par le **crypto-shredding** (§3.4), jamais par un DELETE.
³ **Aucun rôle** n'a d'accès applicatif direct à `audit_dek` : les clés enveloppées ne sont jamais lues par un humain. Seuls les **comptes de service** de déchiffrement les manipulent, via un chemin dédié (unwrap Vault en mémoire), et uniquement pour servir une preuve autorisée.
⁴ **Extension v2** : l'Auditeur obtient **C** (création) sur `organisations`, `applications` et `ressources` — il peut référencer un client, une application ou une ressource découverts pendant l'audit — sans **E/S** (l'édition/suppression du référentiel reste réservée à l'Admin). Conséquence RLS : `organisation` est cloisonnée par sa **propre clé** (`app_client_visible(id)`), or l'`id` d'une organisation neuve ne figure dans aucun scope par construction ; sa politique RLS est donc **scindée** (`SELECT/UPDATE/DELETE` = appartenance au scope ; `INSERT` = simple contexte de sécurité établi, `app_authenticated()`, migration `0009`). À la création, l'`id` de la nouvelle organisation est ajouté au `client_scope` du créateur (effectif à sa prochaine connexion). Applications/Ressources sont cloisonnées par `client_id`/`organisation_id` (déjà dans le scope) : aucun changement RLS.
 
> Cohérence avec l'esprit v1 : de même que **personne, pas même l'Admin, ne peut modifier le journal**, personne ne *lit* une DEK. L'immutabilité et le secret sont portés par la structure, pas par la discipline d'un rôle.
 
### 3.2 Le moteur de décision — `can(action, entity, record?)`, version serveur
 
La signature de la v1 est conservée, mais l'évaluation est **serveur** et suit un ordre strict (deny par défaut) :
 
```
DÉCISION = AUTORISER  ⟺  toutes les portes ci-dessous passent, sinon REFUSER
  ┌─ 1. Authentifié ? (jeton valide, compte 'active')
  ├─ 2. MFA suffisant pour la sensibilité visée ? (step-up si requis)
  ├─ 3. La matrice rôle × entité × action autorise l'action ?
  ├─ 4. Cloisonnement : le client du record ∈ client_scope ? (ou scope vide)
  └─ 5. (preuves) TLP/PAP de l'objet compatible avec le contexte de diffusion ?
```
 
- **Porte 4 — cloisonnement.** Résolution du client d'un record comme en v1 (`_scopeClientOf`) : direct (`client_id`), ou via l'audit/exercice parent. **Le cloisonnement restreint, jamais n'élargit** — invariant v1 préservé.
- **Double barrière.** La porte 4 est vérifiée dans l'application *et* garantie par la **RLS PostgreSQL** (§3.3). L'application donne des messages d'erreur propres ; la RLS est le filet qui tient même si l'application se trompe.
### 3.3 Row Level Security — le cloisonnement devient structurel
 
Là où la v1 filtrait l'affichage, la v2 filtre **la donnée elle-même**. À chaque transaction, l'API pose le contexte de session :
 
```sql
SET LOCAL app.user_role    = 'auditeur';
SET LOCAL app.client_scope = '<uuid>,<uuid>';   -- vide = tous clients
```
 
Les politiques RLS (déjà écrites pour `evidence`, `audit_dek`, `evidence_access` dans `schema_evidence.sql`, à généraliser aux 13 entités métier) garantissent qu'une requête **ne voit jamais** une ligne hors périmètre. Conséquence : même une injection SQL ou un bug de filtre applicatif ne peut pas exfiltrer les données d'un autre client. C'est la **matérialisation en base** du cloisonnement que la v1 ne pouvait que simuler.
 
> **Point d'attention.** La connexion PostgreSQL de l'API ne doit **pas** être `SUPERUSER` ni `BYPASSRLS` — sinon la RLS est court-circuitée. Rôle applicatif dédié, `NOBYPASSRLS`.
 
### 3.4 Actions à haut risque (step-up + double garde)
 
Certaines actions dépassent le CRUD et engagent la custody ou la confidentialité. Elles exigent **MFA récente** et, pour les plus destructrices, une **seconde condition** :
 
| Action | Rôle | Garde supplémentaire |
|---|---|---|
| **Lever un `legal_hold`** | admin | Step-up MFA + motif obligatoire (journalisé) |
| **Déclencher un crypto-shredding** | admin (ou job de rétention) | Preuve que **toutes** les preuves de l'audit sont échues **et** hors legal hold ; step-up MFA si manuel ; irréversible → confirmation explicite |
| **Exporter une archive d'audit** (avec preuves) | admin, manager | Step-up MFA ; l'export produit ses propres entrées `evidence_access` (`purpose='export'`) |
| **Changer le rôle / `client_scope` d'un compte** | admin | Step-up MFA ; avant/après journalisés |
| **Rotation d'une KEK client** | admin (ou automatique) | Opération Vault ; ré-enveloppe les DEK, ne re-chiffre pas les objets |
 
---
 
## 4. Articulation avec le stockage des preuves
 
C'est le cœur de la demande : le RBAC et le stockage des preuves doivent former **un seul système cohérent**. Voici comment les deux s'emboîtent.
 
### 4.1 Séquence de dépôt d'une preuve (upload)
 
```
Auditeur ──(1)──► API: "je veux déposer une preuve sur le finding X"
   API: can('create','evidence', {client_id de X}) ?  ── refus → 403 journalisé
        │ (porte 3 matrice + porte 4 cloisonnement/RLS)
   API ──(2)──► émet une URL présignée d'UPLOAD vers la zone de QUARANTAINE MinIO
Auditeur ──(3)──► PUT direct du binaire vers MinIO (ne transite pas par l'API)
   Worker ──(4)──► magic bytes + antivirus (ClamAV)
              ──(5)──► SHA-256 clair → chiffrement AES-GCM (DEK de l'audit, unwrap Vault)
              ──(6)──► PUT objet chiffré + Object Lock ; SHA-256 chiffré
              ──(7)──► entrée JOURNAL tamper-evident {evidence_id, sha256_plaintext}
              ──(8)──► evidence.ingest_status = 'stored'
```
 
Le RBAC intervient en **(1)** (droit de créer, cloisonnement). Tout le reste (4→8) est le sas du cahier §6quater.4 — l'auditeur n'a jamais accès à la DEK, jamais à Vault.
 
### 4.2 Séquence de consultation (download)
 
```
Utilisateur ──► API: "ouvrir la preuve E"
   API: can('read','evidence', E) ?          (porte 3 + porte 4/RLS)
   API: TLP/PAP de E compatible ?            (porte 5)
   API: MFA suffisante ?                      (porte 2, step-up si RED)
        │  une porte échoue → 403 + evidence_access(granted=false, raison)
   API ──► unwrap DEK via Vault (mémoire serveur) → déchiffre → sert le flux
       ──► OU émet une URL présignée de DOWNLOAD ≤ 5 min
       ──► evidence_access(granted=true, purpose='view', expires_at)
```
 
**Invariant clé :** aucune clé (DEK, KEK) ne descend jamais au navigateur. Le déchiffrement est **serveur**. La v1 chiffrait côté client par passphrase faute de serveur ; la v2 n'a plus cette contrainte et ne doit pas la reproduire (cf. cahier §6quater.9).
 
### 4.3 Le générateur de livrables — consommateur privilégié tracé
 
Le générateur embarque les preuves image dans les rapports (cahier §6bis). Il déchiffre **en masse** sur un audit. Traitement :
 
- Compte de service à rôle dédié, autorisé `read` sur `evidence` **du seul audit** en cours de génération (jeton à périmètre réduit, durée de vie = la génération).
- Chaque preuve embarquée produit une entrée `evidence_access(purpose='report_render')` — la génération d'un rapport laisse une **empreinte d'accès par preuve**.
- Les preuves `contains_secrets = true` **exigent un masquage** avant inclusion (le générateur refuse sinon) — cohérent DA §5.1 / cahier §6quater.7.
### 4.4 Tableau de correspondance RBAC ↔ preuves
 
| Capacité preuve | Qui | Porte(s) RBAC | Mécanisme stockage |
|---|---|---|---|
| Déposer | Auditeur (C) | 3 + 4 | URL présignée upload → sas |
| Consulter une preuve | tous rôles (L), selon scope | 2 + 3 + 4 + 5 | unwrap Vault serveur / URL présignée download |
| Éditer légende, TLP/PAP, flags | Auditeur, Manager, Admin (E¹) | 3 + 4 | UPDATE champs non-custody (trigger garde le reste) |
| Reclasser sensibilité (PII/secrets) | idem E | 3 + 4 | UPDATE `contains_*` |
| Soft delete | Admin (S²) | 3 + 4 + garde legal hold / Object Lock | `deleted_at` |
| Poser / lever legal hold | Admin | 3 + step-up | `legal_hold` |
| Crypto-shredding | Admin / job | 3 + step-up + garde rétention | `audit_dek.status='destroyed'` |
| Rendre un rapport | service `report_render` | jeton à périmètre audit | déchiffrement en masse tracé |
| Lire le journal d'accès | Admin, Manager, RSSI (L) | 3 | lecture `evidence_access` |
 
---
 
## 5. Architecture de déploiement
 
### 5.1 Composants
 
```
                    ┌──────────────┐
   Navigateur ──────►  API (BFF)   ├──► PostgreSQL (RLS, métadonnées, app_user)
   (OIDC+PKCE)      │  décision    ├──► Vault (KEK/client, unwrap DEK)
                    │  RBAC/RLS    ├──► MinIO (objets chiffrés + Object Lock)
                    └──────┬───────┘
                           └──► IdP OIDC (Entra/Keycloak/Okta) — authentification
   Workers (async) ──► sas d'ingestion (AV, hash, chiffrement) · jobs rétention/intégrité
```
 
- **API / BFF** : point unique de décision. Aucune logique d'autorisation dans le client. Pose le contexte RLS, appelle Vault pour l'unwrap, émet les URL présignées.
- **Séparation des plans** : le **binaire** ne transite jamais par l'API (upload/download directs MinIO via URL présignées) ; seules **métadonnées et décisions** passent par l'API.
### 5.2 Défense en profondeur — les couches qui portent le cloisonnement
 
| Couche | Ce qu'elle garantit | Si la couche au-dessus est contournée |
|---|---|---|
| **Client** | Confort (masque les actions interdites) | Aucune sécurité — assumé |
| **API / `can()`** | Décision explicite, messages propres, journalisation | La RLS prend le relais |
| **RLS PostgreSQL** | La donnée hors scope est **invisible** | La séparation cryptographique prend le relais |
| **Chiffrement (DEK/audit, KEK/client)** | Sans la bonne clé, l'octet est illisible | Rien à exfiltrer d'exploitable |
| **Object Lock / journal** | Immutabilité, custody opposable | — |
 
> C'est la traduction concrète de « rendre réel ce que la v1 simulait » : quatre barrières successives, dont trois indépendantes du code applicatif.
 
### 5.3 Vault — le point de survie
 
- **KEK par client** dans le transit engine ; **ne sort jamais**. L'API demande wrap/unwrap, ne détient pas les clés.
- **Politiques Vault** au plus juste : l'API peut *unwrap* une DEK pour servir une preuve autorisée ; elle ne peut ni exporter ni lire une KEK.
- **Sauvegarde/DR** : la sauvegarde des KEK Vault est le point critique — procédure de scellement/quorum documentée. Perdre les KEK = perdre toutes les preuves (ce qui rend le crypto-shredding crédible). Les DEK enveloppées vivent en base (sauvegarde standard) mais sont **inertes sans Vault**.
---
 
## 6. Journalisation & auditabilité
 
- **Journal tamper-evident étendu au serveur** : chaînage de hachage (déjà spécifié pour la maquette) porté côté serveur, alimenté par les décisions sensibles — authentification, changements de rôle/scope, dépôt de preuve (scellement d'empreinte), legal hold, crypto-shredding, exports.
- **`evidence_access`** trace **chaque** consultation de preuve, **refus compris** (`granted=false` + raison). Distinct du journal métier : il répond à *« qui a vu cette preuve, quand, pourquoi »*.
- **Immutabilité** : comme en v1, **aucun rôle n'a C/E/S sur le journal** — l'Admin lui-même n'a que L. Portée par la matrice *et* par les triggers base.
- **Rétention des journaux** distincte de celle des preuves : les entrées de journal survivent au crypto-shredding (elles ne contiennent pas de contenu, seulement des empreintes et des faits).
---
 
## 7. Migration depuis la maquette (v1 → v2)
 
1. **Comptes** : création des `app_user` réels (rattachement IdP ou comptes locaux) ; les « profils » simulés de la maquette deviennent des rôles portés par des comptes authentifiés.
2. **Données métier** : import de l'export JSON cloisonné existant ; les `client_id` alimentent la RLS.
3. **Preuves** : ré-ingestion des Blobs via le **sas** (§4.1) — aucune preuve n'entre sans passer par magic bytes + AV + chiffrement DEK/audit. Les preuves chiffrées par passphrase dans la maquette sont déchiffrées **par l'utilisateur** au moment de l'export (la plateforme ne demande jamais la passphrase).
4. **Journal** : nouvelle chaîne côté serveur ; l'entrée de migration fait foi pour la custody à partir de la bascule.
5. **Bascule progressive possible** : le RBAC réel peut être activé entité par entité (RLS d'abord sur les preuves — les plus sensibles —, puis généralisée), la maquette restant l'outil de démonstration/formation.
---
 
## 8. Points à trancher (comme en v1, tranchés par défaut — à confirmer)
 
- **Source du rôle** : rôle 100 % géré dans le produit (recommandé, §1.1) *ou* proposé par claim de groupe IdP puis validé ? Par défaut : géré dans le produit, l'IdP ne fait qu'authentifier.
- **Granularité MFA** : MFA globale obligatoire *ou* seulement step-up sur actions sensibles ? Par défaut : MFA globale pour les rôles opérationnels + step-up sur le haut risque (§3.4).
- **Modèle « client ultra-sensible »** (cahier §6quater.9, roadmap) : sur-chiffrement côté client par-dessus l'enveloppe serveur pour certains clients ? Hors périmètre v2, réservé si un client l'exige.
- **Rôle « Éditeur de corpus »** (cahier v4.9, backlog) : à intégrer au référentiel de rôles quand la gouvernance d'édition du corpus sera implémentée — non couvert ici.
- **Reprise des trois ambiguïtés v1** (droits Manager sur Ressources / Applications / Actions d'audit) : la v2 reprend les valeurs par défaut de la v1 §3 ; à confirmer une fois pour toutes à ce stade, puisqu'elles deviennent des droits réels et non plus simulés.
---
 
## 9. Ce qui reste inchangé depuis la v1
 
Pour lever toute ambiguïté : la v2 **ne remet pas en cause** le modèle métier. Sont conservés **à l'identique** — les 6 rôles et leurs codes ; la matrice L/C/E/S/V sur les 13 entités existantes ; la **validation** comme action distincte de l'édition (avec `valide_par`/`valide_le`) ; le principe du cloisonnement `{ rôle, clients rattachés }` qui **restreint sans élargir** ; l'**immutabilité du journal** (aucun rôle n'a C/E/S) ; les correctifs v1 (éditeur de scénario sous `can()`, boutons d'édition masqués par droit, palette ⌘K vérifiant la lecture). La v2 **ajoute** : l'authentification réelle, l'application serveur de ces règles, la RLS, l'entité `Preuves` et son articulation avec le chiffrement d'enveloppe.
