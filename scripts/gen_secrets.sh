#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# gen_secrets.sh — génère des secrets ROBUSTES dans .env (idempotent).
#
# Motivation : config.py refuse au démarrage tout secret « de gabarit »
# (change/example/default/dev-) — garde-fou volontaire « aucun secret faible,
# jamais ». Ce script matérialise ce garde-fou : au bootstrap (ou à la demande),
# il remplace les valeurs faibles/vides du .env par des secrets forts.
#
# IDEMPOTENT : une valeur déjà forte n'est jamais réécrite (un secret hexadécimal
# ne contient aucun des motifs faibles → stable d'un run à l'autre).
#
# EXCLUS volontairement (provisionnés par un système externe, pas choisis par nous) :
#   - VAULT_TOKEN        : issu de `vault operator init` (cf. make init-vault) ;
#   - OIDC_CLIENT_SECRET : doit correspondre au secret client de la realm Keycloak.
#
# ATTENTION (déploiement EXISTANT) : les mots de passe Postgres/MinIO ne sont posés
# qu'à la PREMIÈRE initialisation des volumes. Si un volume a déjà été initialisé
# avec des valeurs faibles, régénérer le .env crée un DÉCALAGE. Pour resynchroniser
# les rôles Postgres sur le nouveau .env :
#   docker compose exec postgres bash /docker-entrypoint-initdb.d/00-roles.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ENV_FILE="${1:-.env}"
EXAMPLE_FILE="$(dirname "$0")/../.env.example"

if ! command -v openssl >/dev/null 2>&1; then
  echo "!! openssl introuvable — requis pour générer les secrets." >&2
  exit 1
fi

# Crée .env depuis l'exemple si absent.
if [ ! -f "$ENV_FILE" ]; then
  cp "$EXAMPLE_FILE" "$ENV_FILE"
  echo ">> $ENV_FILE créé depuis .env.example"
fi

# Clés à secret fort choisies par nous, consommées au premier boot.
SECRET_KEYS=(
  JWT_SIGNING_KEY
  TOTP_ENC_KEY
  POSTGRES_SUPERPASSWORD
  APP_MIGRATOR_PASSWORD
  APP_API_PASSWORD
  MINIO_ROOT_PASSWORD
  KC_ADMIN_PASSWORD
  SEED_DEFAULT_PASSWORD
)

# Une valeur est « faible » (à régénérer) si elle est vide ou porte un motif de gabarit.
is_weak() {
  local v="$1"
  [ -z "$v" ] && return 0
  printf '%s' "$v" | grep -qiE 'change|example|default|dev-|changeme' && return 0
  return 1
}

gen_secret() { openssl rand -hex 32; }

current_value() {
  grep -E "^${1}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'
}

set_value() {
  local key="$1" val="$2"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    # Remplace la ligne (portable macOS/Linux via fichier temporaire ; val littérale).
    awk -v k="$key" -v val="$val" \
      'BEGIN{FS="="} $1==k {print k"="val; next} {print}' "$ENV_FILE" > "$ENV_FILE.tmp"
    mv "$ENV_FILE.tmp" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
}

changed=0
for key in "${SECRET_KEYS[@]}"; do
  if is_weak "$(current_value "$key")"; then
    set_value "$key" "$(gen_secret)"
    echo ">> $key : secret fort généré"
    changed=$((changed + 1))
  fi
done

if [ "$changed" -eq 0 ]; then
  echo ">> Tous les secrets ciblés sont déjà robustes — rien à changer."
else
  echo ">> $changed secret(s) généré(s) dans $ENV_FILE."
fi
echo ">> Restent à renseigner manuellement (provisionnés hors périmètre) :"
echo "   VAULT_TOKEN (make init-vault) · OIDC_CLIENT_SECRET (realm Keycloak)."
