# Validation — preuves d'exécution

🇬🇧 [English version](en/validation.md)

Ce document récapitule les vérifications effectuées sur le code livré. Elles ont été
exécutées contre une base **PostgreSQL 16** réelle (migration Alembic appliquée sous le
rôle `app_migrator`, requêtes applicatives sous `app_api` en `NOBYPASSRLS`).

## Couverture automatisée

La suite complète (`make test`) couvre **35 fichiers de tests (~200 tests)**. Familles
principales (liste non exhaustive — le comptage exact évolue avec le code) :

| Famille (DAT §6)            | Fichier                         | Ce qui est prouvé |
|-----------------------------|----------------------------------|-------------------|
| Matrice RBAC (exhaustive)   | `test_matrix.py`                 | Chaque rôle × entité est défini ; journal en lecture seule pour tous (admin inclus) ; aucun accès humain à `audit_dek` ; refus par défaut hors matrice ; droits précis du cahier (VOC, CISO, Manager D6, CERT). |
| Moteur `can()` (5 portes)   | `test_rbac_gates.py`             | Ordre des portes, refus par défaut, cloisonnement client, TLP/PAP. |
| Isolation RLS (base réelle) | `test_rls_isolation.py`          | Fail-closed sans contexte (0 ligne) ; isolation par scope ; scope vide + rôle **transverse** (admin/manager/service) = tous clients, scope vide + rôle scopé = **aucun accès** (fail-closed) ; `WITH CHECK` bloque l'écriture hors périmètre ; journal append-only (trigger). |
| Chiffrement enveloppe       | `test_crypto.py`                 | Aller-retour AES-256-GCM ; liaison AAD (altérer l'audit_id casse le déchiffrement) ; détection d'altération du ciphertext ; DEK de 256 bits exigée. |
| Journal tamper-evident      | `test_journal_chain.py`          | Chaînage déterministe ; toute altération casse la chaîne. |
| Sas d'ingestion             | `test_ingest_detection.py`       | Détection du type réel par signature ; extension menteuse rejetée ; EICAR bloqué même sans ClamAV. |
| Jetons / step-up            | `test_tokens.py`                 | Émission/décodage du jeton d'accès ; fraîcheur step-up ; exigence MFA. |
| Exposition réseau           | `test_network_exposure.py`       | Seul `frontend` publie des ports ; services de données jamais sur `edge`. |

| Enrichissement CVE (CIRCL)  | `test_circl_enrichment.py`       | Parseur défensif sur vrai enregistrement CVE 5.x : priorité CVSS 4.0>3.1>3.0>2.0, CWE, CPE, produits, EPSS/KEV quand présents ; hors-ligne → dégradation gracieuse. |
| Import/export STIX 2.1       | `test_stix_import.py` · `test_stix_export.py` | Aller-retour scénario ↔ bundle (techniques, acteur, TLP, D3FEND) ; bundle sans grouping agrégé ; groupings multiples. |
| Synchro référentiels (MITRE) | `test_reference_sync.py`         | Parseurs ATT&CK (actives, tactique standard préférée) et D3FEND (ext_id + libellé) sur échantillons. |
| Matrice ATT&CK hiérarchique  | `test_attack_matrix.py`          | Agrégation de couverture ; cumul sous-technique → parent (comportement Navigator). |
| Cockpit (agrégats)           | `test_cockpit.py`                | Taux de détection, angles morts, bande kill-chain (états par tactique, ordre), tendance de détection. |
| Éditeur d'étapes d'exercice  | `test_exercise_steps.py`         | Chargement depuis scénario (étapes nommées, ordonnées). |
| Recette e2e — parité (HTTP)  | `test_e2e_features.py`           | Chargement/réordonnancement d'étapes + gardes ; couverture par application + filtre client ; widgets cockpit + filtre ; **usage de scénario cloisonné RLS**. |
| Ancrage WORM du journal      | `test_journal_anchor.py`         | Sérialisation déterministe de l'ancre ; détection d'un écart ancre ↔ base (falsification hors-bande). |
| Filtres/stats/export journal | `test_journal_filters.py`        | Filtres serveur (texte, domaine, résultat, acteur, dates) ; cloisonnement par client ; export sous step-up. |
| Durcissement auth            | `test_totp_ratelimit.py` · `test_secret_box.py` · `test_oidc_state.py` · `test_security_hardening_p0.py` | Anti-rejeu TOTP + limitation de débit ; chiffrement des secrets TOTP au repos ; état OIDC/PKCE à usage unique ; exigences de claims JWT et rejet des secrets faibles. |
| Bucket WORM                  | `test_worm_bucket.py`            | Object Lock (COMPLIANCE) exigé sur les buckets de preuves et d'ancres. |
| Actions d'audit dérivées     | `test_audit_actions.py`          | Dérivation scénario → actions PTES (mapping tactique → phase, dédoublonnage, idempotence). |
| Bloc engagement              | `test_engagement_defaults.py`    | Pré-remplissage serveur des 18 clés (parité avec le drawer). |
| « Ma fiche » (profil)        | `test_profile_resource.py`       | Upsert de la fiche ressource liée au compte ; bornage au périmètre. |
| Analytics par vue            | `test_organisations_analytics.py` · `test_ressources_analytics.py` | Agrégats serveur des bandeaux KPI (organisations, ressources), filtres compris. |

## Preuves manuelles complémentaires

Vérifications faites en direct sur la base migrée :

- **Isolation RLS multi-clients.** Deux clients A et B, un audit chacun. `app_api`
  sans contexte ne voit rien ; avec le scope A il ne voit que l'audit A ; avec un scope
  vide et un rôle posé (admin/manager) il voit les deux. Une tentative d'insertion dans
  le client B depuis un contexte scope A est rejetée par la clause `WITH CHECK`.

- **Correctif fail-closed.** La fonction `app_client_visible` a été durcie pour exiger
  qu'un contexte applicatif (`app.role`) soit établi : une connexion `app_api` brute,
  sans contexte, renvoie **0 ligne** (avant durcissement, un scope vide sans rôle était
  indistinguable d'un rôle multi-clients et laissait tout voir).

- **Journal inviolable.** `UPDATE` et `DELETE` sur `journal` sont rejetés par un trigger
  (`journal is append-only`). La vérification de chaîne recalcule chaque empreinte : une
  altération du **contenu** d'une entrée (même en contournant le trigger au niveau base)
  est détectée et localise la première rupture.

- **Seed applicatif.** Le seed insère les référentiels (ATT&CK multi-domaines / D3FEND /
  OWASP / CWE / CAPEC / groupes / acteurs MISP), trois organisations (deux clientes, une
  prestataire) et les comptes de démonstration (`admin` / `auditeur` / `ciso` /
  `operateur`) — validant les valeurs par défaut côté base. `make seed-demo` ajoute le
  jeu métier riche (idempotent).

- **Frontend.** Build Vite de production réussi (63 modules) ; toutes les vues et le
  système de thèmes A/B (tokens DA repris verbatim) compilent.

## Reproduire

Tout est conteneurisé (aucun Python/Node requis sur l'hôte) :

```bash
make test           # suite complète (profil compose api-test, PostgreSQL migré)
make test-security  # familles de sécurité bloquantes uniquement
make lint           # ruff (backend) + eslint (frontend), conteneurisés
make frontend-build # build Vite de production
```

Ces cibles `make` (`lint`, `test`, `test-security`, `config`, `frontend-build`)
constituent les points d'entrée d'une intégration continue — aucun pipeline CI n'est
livré dans le dépôt à ce jour.
