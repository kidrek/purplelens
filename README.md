# Cockpit de Pilotage Purple Team

Plateforme multi-clients de pilotage d'une équipe Purple Team (cybersécurité offensive
et défensive coordonnées). Elle gère le cycle complet : organisations, applications,
ressources, scénarios de menace, audits, exercices Purple, chaînes d'attaque,
observations défensives, vulnérabilités, tickets de détection, livrables — et un
**sous-système de preuves chiffrées** de bout en bout.

Ce dépôt implémente les documents normatifs du projet : cahier des charges v5.0,
architecture technique (DAT) v1.1, spécification Auth & RBAC v2.0 et direction
artistique v2.7.

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
make seed                     # référentiels + organisation démo + comptes
```

Accès : `https://localhost/` — comptes de démonstration (mot de passe `ChangeMe!2026`,
TOTP à enrôler) : `admin@purple.local`, `auditeur@purple.local`, `ciso@purple.local`.

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
docs/               runbook Vault, guide utilisateur
.github/workflows/  CI (lint, tests, sécurité, exposition réseau)
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
