# Cockpit de Pilotage Purple Team — contrat d'exploitation (DAT §4.2)
# Toutes les cibles sont idempotentes autant que possible.

SHELL := /bin/bash
COMPOSE := docker compose
ENV_FILE := .env

.DEFAULT_GOAL := help
.PHONY: help bootstrap init init-vault tls up down logs config migrate seed import-maquette \
        test test-e2e test-security backup restore unseal fmt lint frontend-build

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

$(ENV_FILE):
	@test -f $(ENV_FILE) || (cp .env.example $(ENV_FILE) && \
	  echo ">> .env créé depuis .env.example — RENSEIGNER LES SECRETS avant la prod")

# ── Certificat TLS de développement ─────────────────────────────────────────
# Génère un certificat auto-signé pour le reverse proxy si absent (idempotent).
# En production, monter un vrai certificat dans deploy/nginx/tls/.
tls: ## Génère un certificat TLS auto-signé (dev) si absent
	@mkdir -p deploy/nginx/tls
	@if [ ! -f deploy/nginx/tls/fullchain.pem ]; then \
	  echo ">> Génération d'un certificat auto-signé (dev) pour localhost..." ; \
	  openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
	    -keyout deploy/nginx/tls/privkey.pem \
	    -out deploy/nginx/tls/fullchain.pem \
	    -subj "/CN=localhost/O=Purple Cockpit (dev)" \
	    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null ; \
	  echo ">> Certificat écrit dans deploy/nginx/tls/ (auto-signé — avertissement navigateur attendu)." ; \
	else \
	  echo ">> Certificat déjà présent (deploy/nginx/tls/fullchain.pem) — rien à faire." ; \
	fi

# ── Cycle de vie ────────────────────────────────────────────────────────────
up: $(ENV_FILE) tls ## Démarre la stack (génère le certificat TLS dev au besoin)
	$(COMPOSE) up -d --build

down: ## Arrête la stack
	$(COMPOSE) down

logs: ## Suit les logs
	$(COMPOSE) logs -f --tail=100

config: $(ENV_FILE) ## Affiche la config résolue ET vérifie qu'un seul service publie des ports
	@$(COMPOSE) config >/tmp/compose.resolved.yml
	@python3 scripts/check_ports.py /tmp/compose.resolved.yml
	@echo ">> Exposition réseau conforme (DAT §4.1bis)"

# ── Première installation ───────────────────────────────────────────────────
bootstrap: up ## Premier démarrage complet : stack + schéma + comptes de démo
	@echo ">> Attente de PostgreSQL..."
	@for i in $$(seq 1 30); do \
	  if $(COMPOSE) exec -T postgres pg_isready -q -U "$${POSTGRES_SUPERUSER:-postgres}" -d "$${POSTGRES_DB:-purple}" 2>/dev/null; then \
	    echo ">> PostgreSQL prêt." ; break ; fi ; \
	  if [ $$i -eq 30 ]; then echo "!! PostgreSQL indisponible après 60 s — voir '$(COMPOSE) logs postgres'" ; exit 1 ; fi ; \
	  sleep 2 ; \
	done
	@$(MAKE) migrate
	@$(MAKE) seed
	@echo ""
	@echo ">> Bootstrap terminé."
	@echo ">> Connexion : https://localhost:$${EDGE_HTTPS_PORT:-443}/  —  admin@purple.local"
	@echo ">> Mot de passe : valeur de SEED_DEFAULT_PASSWORD dans .env (champ TOTP vide)."
	@echo ">> Étape suivante (avant le dépôt de preuves) : make init-vault (descellement + KEK)."

init: $(ENV_FILE) ## Réseaux, buckets MinIO (Object Lock), realm Keycloak, rôles SQL
	$(COMPOSE) up -d postgres redis minio vault keycloak clamav
	@echo ">> Attente de la disponibilité des dépendances..."
	@sleep 8
	$(COMPOSE) run --rm api python -m app.storage.bootstrap   # crée buckets + Object Lock
	@echo ">> Rôles SQL initialisés par l'entrypoint Postgres (00-roles.sh)"

init-vault: ## Init Vault + unseal interactif + transit engine + politiques API (wrap/unwrap)
	$(COMPOSE) exec vault sh -c 'vault operator init -key-shares=5 -key-threshold=3 || true'
	@echo ">> Notez les clés de descellement et le root token (docs/runbook-vault.md)"
	$(COMPOSE) run --rm api python -m app.storage.bootstrap   # active transit + KEK clients

# ── Base de données ─────────────────────────────────────────────────────────
migrate: ## alembic upgrade head (rôle app_migrator)
	$(COMPOSE) run --rm api alembic upgrade head

seed: ## Référentiels ATT&CK/D3FEND/OWASP/CWE/CAPEC + données de démo
	$(COMPOSE) run --rm api python -m app.seed

import-maquette: $(ENV_FILE) ## migration §5 : export JSON maquette → API + sas.  FILE=chemin.json
	@test -n "$(FILE)" || (echo "Usage: make import-maquette FILE=export.json" && exit 1)
	$(COMPOSE) run --rm -v $(abspath $(FILE)):/import.json api python -m app.import_maquette /import.json

# ── Tests (la sécurité comme code testé — DAT §6) ───────────────────────────
test: ## pytest complet (isolation RLS, sas, matrice, custody, crypto, auth, réseau)
	$(COMPOSE) --profile test build api-test
	$(COMPOSE) --profile test run --rm api-test
	@echo ">> NB : les tests RLS exigent une base migrée (make migrate au préalable)."

test-e2e: ## recette bout-en-bout HTTP (login, CRUD, RLS, STIX via l'API réelle)
	$(COMPOSE) --profile test build api-test
	$(COMPOSE) --profile test run --rm api-test pytest -q tests/test_e2e_http.py

test-security: ## familles de sécurité bloquantes (DAT §6) — rapide, pré-commit
	$(COMPOSE) --profile test build api-test
	$(COMPOSE) --profile test run --rm api-test pytest -q \
	  tests/test_rls_isolation.py tests/test_matrix.py tests/test_rbac_gates.py \
	  tests/test_journal_chain.py tests/test_crypto.py tests/test_ingest_detection.py \
	  tests/test_network_exposure.py

# ── Sauvegarde / restauration ───────────────────────────────────────────────
backup: ## pg_dump + snapshot MinIO + export scellé Vault
	@bash scripts/backup.sh

restore: ## restauration depuis une sauvegarde.  DIR=chemin
	@test -n "$(DIR)" || (echo "Usage: make restore DIR=backups/2026-07-04" && exit 1)
	@bash scripts/restore.sh "$(DIR)"

unseal: ## Descellement Vault après redémarrage (quorum)
	$(COMPOSE) exec vault vault operator unseal

# ── Qualité ─────────────────────────────────────────────────────────────────
fmt: ## Formatage (ruff + prettier)
	$(COMPOSE) run --rm api ruff format app tests
	cd frontend && npm run format || true

lint: ## Lint (ruff + eslint)
	$(COMPOSE) run --rm api ruff check app tests
	cd frontend && npm run lint || true

frontend-build: ## Build de production du frontend
	cd frontend && npm ci && npm run build

verify-journal: ## Vérifie l'intégrité de la chaîne du journal d'audit
	$(COMPOSE) run --rm api python -m scripts.verify_journal

sync-reference: ## Synchronise les référentiels ATT&CK/D3FEND depuis MITRE
	$(COMPOSE) run --rm api python -m scripts.sync_reference
