#!/usr/bin/env bash
set -euo pipefail

# Prépare la base (attente + schéma + seed si vide), puis lance la commande passée.
# SEED_ON_START=1 (par défaut en compose) peuple les données de démo une seule fois.

SEED_FLAG=""
if [ "${SEED_ON_START:-1}" = "1" ]; then
  SEED_FLAG="--seed"
fi

echo "[entrypoint] Initialisation de la base…"
python -m app.startup ${SEED_FLAG}

echo "[entrypoint] Démarrage : $*"
exec "$@"
