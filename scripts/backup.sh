#!/usr/bin/env bash
# Sauvegarde cohérente de l'état chiffré.
#
# PRINCIPE (cahier §6quater, DAT §5) : les preuves restent chiffrées de bout en bout.
# La sauvegarde ne déchiffre RIEN — elle copie :
#   1. la base (métadonnées, DEK enveloppées, journal) via pg_dump ;
#   2. les objets MinIO (ciphertext sous Object Lock) via mc mirror ;
#   3. l'état Vault (KEK) est sauvegardé À PART, selon la procédure de quorum
#      (voir docs/runbook-vault.md) — JAMAIS avec les DEK, pour ne pas réunir
#      clé et données au même endroit.
#
# Une sauvegarde sans les KEK Vault correspondantes est, par construction,
# inexploitable : c'est volontaire (crypto-shredding = destruction de KEK).
set -euo pipefail

TS="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_DIR:-./backups}/${TS}"
mkdir -p "${DEST}"

echo "[backup] base de données → dump.sql.gz"
docker compose exec -T postgres \
  pg_dump -U "${POSTGRES_SUPERUSER:-postgres}" -d "${POSTGRES_DB:-purple}" \
  | gzip > "${DEST}/dump.sql.gz"

echo "[backup] objets chiffrés MinIO → objects/ (ciphertext, jamais déchiffré)"
mkdir -p "${DEST}/objects"
if command -v mc >/dev/null 2>&1; then
  mc mirror --quiet "${MC_ALIAS:-local}/" "${DEST}/objects/" || true
else
  echo "  (client 'mc' absent : copier le volume minio_data hors-ligne)"
fi

echo "[backup] empreinte d'intégrité"
( cd "${DEST}" && sha256sum dump.sql.gz > SHA256SUMS 2>/dev/null || true )

cat > "${DEST}/MANIFEST.txt" <<EOF
Sauvegarde Cockpit Purple Team
Horodatage (UTC) : ${TS}
Contenu : base (métadonnées + DEK enveloppées + journal), objets chiffrés MinIO.
NON inclus : KEK Vault (sauvegarde séparée à quorum — docs/runbook-vault.md).
Rappel : sans les KEK, les preuves sont indéchiffrables (comportement attendu).
EOF

echo "[backup] terminé → ${DEST}"
