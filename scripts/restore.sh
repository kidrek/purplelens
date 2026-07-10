#!/usr/bin/env bash
# Restauration à partir d'une sauvegarde produite par backup.sh.
#
# La restauration remet en place les métadonnées, les DEK enveloppées et les objets
# chiffrés. Les preuves ne redeviennent lisibles QUE si le Vault correspondant est
# restauré et descellé (quorum) — voir docs/runbook-vault.md. La KEK reste la
# frontière : pas de KEK ⇒ pas de déchiffrement.
set -euo pipefail

SRC="${1:?usage: restore.sh <chemin_sauvegarde>}"
[ -f "${SRC}/dump.sql.gz" ] || { echo "dump.sql.gz introuvable dans ${SRC}"; exit 1; }

if [ -f "${SRC}/SHA256SUMS" ]; then
  echo "[restore] vérification d'intégrité"
  ( cd "${SRC}" && sha256sum -c SHA256SUMS )
fi

echo "[restore] base de données ← dump.sql.gz"
gunzip -c "${SRC}/dump.sql.gz" \
  | docker compose exec -T postgres \
      psql -U "${POSTGRES_SUPERUSER:-postgres}" -d "${POSTGRES_DB:-purple}"

if [ -d "${SRC}/objects" ] && command -v mc >/dev/null 2>&1; then
  echo "[restore] objets chiffrés → MinIO"
  mc mirror --quiet "${SRC}/objects/" "${MC_ALIAS:-local}/" || true
fi

echo "[restore] terminé."
echo "IMPORTANT : descellez Vault (quorum) pour rendre les preuves déchiffrables."
echo "            Voir docs/runbook-vault.md."
