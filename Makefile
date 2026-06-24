# PurpleLens — pilotage du déploiement Docker
# Usage : make <cible>. Lancez `make help` pour la liste.

# Détecte `docker compose` (v2) ou `docker-compose` (v1)
COMPOSE := $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; else echo "docker-compose"; fi)

WEB_PORT ?= 8080

.DEFAULT_GOAL := help
# En production, on n'utilise QUE le compose de base (pas l'override dev),
# donc seul le frontend est exposé.
COMPOSE_PROD := $(COMPOSE) -f docker-compose.yml

.PHONY: help init build up up-prod down restart logs logs-backend ps status \
        seed reset-db shell-backend shell-db psql clean prune health open

## help: Affiche cette aide
help:
	@echo "PurpleLens — cibles disponibles :"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sed -e 's/## //' | awk -F': ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Orchestrateur détecté : $(COMPOSE)"

## init: Crée le fichier .env depuis .env.example s'il n'existe pas
init:
	@if [ ! -f .env ]; then cp .env.example .env && echo ".env créé depuis .env.example — pensez à changer les secrets."; else echo ".env existe déjà."; fi

## build: Construit les images backend et frontend
build:
	$(COMPOSE) build

## up: Démarre la stack en mode DEV (ports d'admin ouverts sur 127.0.0.1)
up: init
	$(COMPOSE) up -d
	@echo ""
	@echo "  Frontend  : http://localhost:$(WEB_PORT)"
	@echo "  API (dev) : http://localhost:8000/docs   ·  via proxy : http://localhost:$(WEB_PORT)/docs"
	@echo "  MinIO     : http://localhost:9001"
	@echo ""
	@echo "Mode dev : db, API et MinIO joignables depuis cette machine uniquement."
	@echo "Suivez le démarrage avec : make logs"

## up-prod: Démarre la stack CLOISONNÉE (seul le frontend est exposé)
up-prod: init
	$(COMPOSE_PROD) up -d
	@echo ""
	@echo "  Frontend  : http://localhost:$(WEB_PORT)"
	@echo "  API docs  : http://localhost:$(WEB_PORT)/docs   (via le proxy)"
	@echo ""
	@echo "Mode cloisonné : db, API et MinIO ne sont PAS exposés sur l'hôte."

## down: Arrête et supprime les conteneurs (conserve les données)
down:
	$(COMPOSE) down

## restart: Redémarre la stack
restart: down up

## logs: Suit les logs de tous les services
logs:
	$(COMPOSE) logs -f

## logs-backend: Suit uniquement les logs du backend
logs-backend:
	$(COMPOSE) logs -f backend

## ps: Liste les conteneurs de la stack
ps:
	$(COMPOSE) ps

## status: Alias de ps avec état de santé
status: ps

## health: Teste les endpoints clés à travers le frontend (dev et prod)
health:
	@echo "Frontend : $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:$(WEB_PORT)/ || echo KO)"
	@echo "API      : $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:$(WEB_PORT)/api/dashboard/portfolio || echo KO)"
	@echo "API docs : $$(curl -s -o /dev/null -w '%{http_code}' http://localhost:$(WEB_PORT)/docs || echo KO)"

## seed: Force le (re)peuplement des données de démo
seed:
	$(COMPOSE) exec backend python -c "from app.seed import run; run()"

## reset-db: ATTENTION — détruit la base et la repeuple à neuf
reset-db:
	$(COMPOSE) exec backend python -c "from app.startup import init_schema; from app.seed import run; run()"
	@echo "Base réinitialisée."

## shell-backend: Ouvre un shell dans le conteneur backend
shell-backend:
	$(COMPOSE) exec backend /bin/bash

## shell-db: Ouvre une session psql sur la base
psql:
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-purplelens} -d $${POSTGRES_DB:-purplelens}

## open: Ouvre le frontend dans le navigateur (macOS/Linux)
open:
	@(command -v xdg-open >/dev/null && xdg-open http://localhost:$(WEB_PORT)) || \
	 (command -v open >/dev/null && open http://localhost:$(WEB_PORT)) || \
	 echo "Ouvrez http://localhost:$(WEB_PORT)"

## clean: Arrête tout et SUPPRIME les volumes (données perdues)
clean:
	$(COMPOSE) down -v
	@echo "Conteneurs et volumes supprimés."

## prune: Nettoie aussi les images du projet
prune: clean
	$(COMPOSE) down --rmi local 2>/dev/null || true
	@echo "Images locales du projet supprimées."
