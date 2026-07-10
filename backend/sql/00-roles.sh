#!/bin/bash
# Rôles PostgreSQL applicatifs (DAT §2.2 / spec backend v2 §3.3).
# Exécuté par l'entrypoint Postgres à la PREMIÈRE initialisation du volume.
#
#   app_migrator : propriétaire du schéma, utilisé UNIQUEMENT par Alembic (make migrate).
#   app_api      : rôle de service NON-superuser, NON-owner, NOBYPASSRLS.
#                  Seul rôle utilisé par l'API et les workers — la RLS s'applique à lui.
#
# Les mots de passe viennent des variables d'environnement APP_MIGRATOR_PASSWORD /
# APP_API_PASSWORD (transmises par docker-compose depuis le .env). Un script .sh est
# nécessaire : l'entrypoint Postgres n'expose PAS l'environnement aux fichiers .sql.
#
# Point d'attention (spec v2 §3.3) : la connexion de l'API ne doit JAMAIS être
# SUPERUSER ni BYPASSRLS, sinon la RLS est court-circuitée.
set -euo pipefail

: "${APP_MIGRATOR_PASSWORD:?APP_MIGRATOR_PASSWORD manquant (le définir dans .env)}"
: "${APP_API_PASSWORD:?APP_API_PASSWORD manquant (le définir dans .env)}"

psql -v ON_ERROR_STOP=1 \
     -v migrator_pw="${APP_MIGRATOR_PASSWORD}" \
     -v api_pw="${APP_API_PASSWORD}" \
     --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<'SQL'
-- pgcrypto (gen_random_uuid) exige le superutilisateur : créé ici par l'entrypoint,
-- PAS par la migration (app_migrator n'est pas superuser).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Création idempotente, puis ALTER systématique : le mot de passe effectif est
-- TOUJOURS celui du .env (jamais une valeur figée dans le code).
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_migrator') THEN
    CREATE ROLE app_migrator LOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_api') THEN
    CREATE ROLE app_api LOGIN NOBYPASSRLS;
  END IF;
END $$;

ALTER ROLE app_migrator WITH LOGIN PASSWORD :'migrator_pw';
ALTER ROLE app_api      WITH LOGIN NOBYPASSRLS PASSWORD :'api_pw';

-- app_migrator possède le schéma public et peut tout créer.
GRANT ALL ON SCHEMA public TO app_migrator;
ALTER SCHEMA public OWNER TO app_migrator;

-- app_api : accès données uniquement (DML), jamais DDL. Les GRANTs fins sont posés
-- par la migration initiale une fois les tables créées.
GRANT USAGE ON SCHEMA public TO app_api;

ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_api;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app_api;
SQL

echo ">> rôles app_migrator / app_api synchronisés avec le .env"
