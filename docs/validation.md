# Validation — preuves d'exécution

Ce document récapitule les vérifications effectuées sur le code livré. Elles ont été
exécutées contre une base **PostgreSQL 16** réelle (migration Alembic appliquée sous le
rôle `app_migrator`, requêtes applicatives sous `app_api` en `NOBYPASSRLS`).

## Couverture automatisée

`89 tests` passent (`make test`). Familles couvertes :

| Famille (DAT §6)            | Fichier                         | Ce qui est prouvé |
|-----------------------------|----------------------------------|-------------------|
| Matrice RBAC (exhaustive)   | `test_matrix.py`                 | Chaque rôle × entité est défini ; journal en lecture seule pour tous (admin inclus) ; aucun accès humain à `audit_dek` ; refus par défaut hors matrice ; droits précis du cahier (VOC, CISO, Manager D6, CERT). |
| Moteur `can()` (5 portes)   | `test_rbac_gates.py`             | Ordre des portes, refus par défaut, cloisonnement client, TLP/PAP. |
| Isolation RLS (base réelle) | `test_rls_isolation.py`          | Fail-closed sans contexte (0 ligne) ; isolation par scope ; scope vide + rôle = tous clients ; `WITH CHECK` bloque l'écriture hors périmètre ; journal append-only (trigger). |
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

- **Seed applicatif.** Le seed insère les référentiels (ATT&CK/D3FEND/OWASP), une
  organisation cliente et une prestataire, et les comptes de démonstration
  (`admin` / `auditeur` / `ciso`) via le chemin ORM — validant les valeurs par défaut
  côté base.

- **Frontend.** Build Vite de production réussi (63 modules) ; toutes les vues et le
  système de thèmes A/B (tokens DA repris verbatim) compilent.

## Reproduire

```bash
# Backend (nécessite un PostgreSQL migré + TEST_DATABASE_URL)
cd backend
pip install .[dev]
alembic upgrade head
TEST_DATABASE_URL=postgresql://app_api:api@localhost:5432/purple pytest -v

# Frontend
cd frontend && npm install && npm run build
```

En intégration continue, `.github/workflows/ci.yml` orchestre l'ensemble (lint,
migration, tests unitaires + sécurité, invariant d'exposition réseau, build frontend).
