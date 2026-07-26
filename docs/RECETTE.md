# Recette & durcissement — Cockpit Purple Team (DAT Phase 6)

🇬🇧 [English version](en/ACCEPTANCE.md)

Ce document consolide la procédure de recette et les runbooks d'exploitation. Il
complète les critères du cahier des charges (v2) §7 et les invariants de sécurité du DAT.

## 1. Recette automatisée

La recette repose sur trois familles de tests, reproductibles localement (base migrée
requise ; tout est conteneurisé via les cibles `make`) :

| Cible | Portée | Bloquant |
|-------|--------|----------|
| `make test` | Suite complète (35 fichiers, ~200 tests) | oui |
| `make test-security` | Familles de sécurité §6 : RLS, matrice RBAC, journal, crypto, sas, exposition réseau | oui |
| `make test-e2e` | Bout-en-bout HTTP : login, CRUD, auto-nommage, SLA, coercition de dates, RLS via l'API, export STIX | oui |

Le test e2e (`tests/test_e2e_http.py`) pilote l'application réelle via httpx en
in-process et exerce le cycle de requête complet (middleware de contexte, cookies de
session, `can()`, RLS). Il verrouille les défauts d'INTÉGRATION que les tests à session
directe ne voient pas — la classe de bugs la plus coûteuse en déploiement.

## 2. Invariants de sécurité — vérification

À valider à chaque recette (automatisé sauf mention) :

1. **Le serveur décide seul** — aucune autorisation côté client. Vérifié par la matrice
   exhaustive (`test_matrix`) et les refus HTTP (`test_e2e_http::test_rbac_*`).
2. **Cloisonnement multi-clients** — RLS PostgreSQL forcée, `app_api` en `NOBYPASSRLS`.
   Vérifié par `test_rls_isolation` (base) et `test_e2e_http::test_rls_isolation_over_http`
   (via l'API).
3. **Journal infalsifiable** — append-only tamper-evident. Vérifié par `test_journal_chain`.
4. **Binaires jamais servis par l'API — à une exception documentée près** — dépôt et
   téléchargement chiffré par URL présignées ≤ 5 min (preuves, livrables). Exception
   délibérée : `GET /api/evidence/{id}/content` diffuse les octets **déchiffrés** via
   l'API (seule détentrice de la DEK — D8 diffère le déchiffrement client) ; accès
   contrôlé sur la même requête, tracé dans `evidence_access`, jamais en clair pour les
   preuves `contains_secrets`.
5. **Un seul service publie des ports** — `make config` + `scripts/check_ports.py`
   (`test_network_exposure`).
6. **Step-up sur actions à haut risque** — gestion de comptes, legal hold, crypto-shredding,
   export, rotation KEK. Vérifié par `test_rbac_gates`.

## 3. Runbook — Sauvegarde / restauration

```bash
make backup                 # pg_dump + miroir MinIO → ./backups/<horodatage> (KEK Vault à part)
make restore DIR=backups/<horodatage>
```

**Test de restauration (obligatoire en recette)** : sur un environnement vierge,
restaurer la dernière sauvegarde, puis rejouer `make test-e2e` — la connexion et la
lecture cloisonnée doivent fonctionner à l'identique.

## 4. Runbook — Vault (descellement)

Vault démarre scellé. Après tout redémarrage :

```bash
make unseal                 # saisir le quorum de clés de descellement
make init-vault             # (première fois) moteur transit + KEK par client
```

⚠ La perte des clés Vault = perte définitive des preuves (chiffrement enveloppe). Les
clés de descellement et la clé racine sont conservées hors-ligne, en quorum réparti.

## 5. Runbook — Premier déploiement

```bash
cp .env.example .env        # puis `make secrets` remplace les valeurs « change-me-* »
                            # (VAULT_TOKEN et OIDC_CLIENT_SECRET restent manuels ;
                            #  en production, poser aussi ENVIRONMENT=production)
make bootstrap              # stack + schéma + comptes de démo (lance make secrets)
make init-vault             # transit + KEK
make seed-demo              # optionnel : jeu de démonstration riche
```

Puis connexion sur `https://localhost:${EDGE_HTTPS_PORT}/` avec `admin@purple.local`
(mot de passe = `SEED_DEFAULT_PASSWORD`), et enrôlement TOTP immédiat via « Mon compte ».

## 6. Bascule — requalification de la maquette

Une fois la recette prononcée, la maquette HTML est officiellement requalifiée
« démo / formation » et n'est plus une référence fonctionnelle : l'application en tient lieu.
