# PurpleLens — Plateforme de validation Purple Team

> La source de vérité des exercices Purple Team.
> Relie la chaîne complète : **CTI → Scénario → Audit → Vulnérabilité → Détection → Réaction → Couverture MITRE ATT&CK → Risque applicatif.**

PurpleLens ne remplace pas vos outils (XSIAM, Defender, Splunk, Jira, Kenna). Il consolide leurs résultats par application pour répondre à une seule question métier :

**« Sommes-nous capables de détecter et réagir aux scénarios de menace qui ciblent réellement nos applications critiques ? »**

---

## Périmètre du MVP v1

Les 7 modules de la spécification sont implémentés au niveau du modèle de données et de l'API. L'effort produit (UI) se concentre sur le **Dashboard Purple Team** et le **moteur de scores**, qui constituent la valeur visible.

| # | Module | Modèle | API | UI |
|---|--------|:------:|:---:|:--:|
| 1 | Référentiel des applications | ✅ | ✅ | ✅ |
| 2 | Base CTI (scénarios + MITRE) | ✅ | ✅ | ✅ liste |
| 3 | Gestion des audits | ✅ | ✅ | ✅ liste |
| 4 | Exécution ATT&CK (détection/réaction) | ✅ | ✅ | ✅ saisie |
| 5 | Gestion des vulnérabilités | ✅ | ✅ | ✅ liste |
| 6 | Evidence Vault | ✅ | ✅ | — (v2 UI) |
| 7 | Dashboard Purple Team | ✅ | ✅ | ✅ **focus** |

## Les 5 KPIs

1. **Coverage ATT&CK** — techniques testées / techniques pertinentes
2. **Detection Coverage** — techniques détectées / techniques testées
3. **Response Coverage** — techniques avec réaction / techniques testées
4. **MTTD** — Mean Time To Detect
5. **MTTR** — Mean Time To Respond

---

## Stack

- **Backend** : FastAPI + SQLAlchemy + Pydantic
- **Base de données** : PostgreSQL (SQLite par défaut en dev, zéro config)
- **Frontend** : React (Vite) + Recharts
- **Stockage preuves** : abstraction S3/MinIO (métadonnées en MVP)

## Démarrage rapide — Docker (recommandé)

Tout est piloté par le `Makefile`. Deux modes selon le contexte.

**Développement** — ports d'administration ouverts sur `127.0.0.1` (base, API directe, console MinIO) pour faciliter le debug :

```bash
make up
```

**Production / cloisonné** — un seul port exposé sur l'hôte, le frontend. La base, MinIO et l'API ne sont joignables que depuis l'intérieur du réseau Docker :

```bash
make up-prod
```

### Architecture réseau

Deux réseaux Docker isolent les services :

- `internal` (marqué `internal: true`, sans accès externe) porte **PostgreSQL**, **MinIO** et le **backend**. Les conteneurs s'y parlent par leur nom DNS, mais rien n'y est routable depuis l'extérieur.
- `web` relie le **frontend** au **backend**. Seul le frontend y publie un port sur l'hôte.

Le backend n'a donc aucun port exposé : il est atteint uniquement via le proxy Nginx du frontend, qui relaie `/api` vers `backend:8000`. La doc interactive de l'API reste accessible derrière ce proxy.

| Service | Dev (`make up`) | Prod (`make up-prod`) |
|---------|-----------------|------------------------|
| Frontend (cockpit) | http://localhost:8080 | http://localhost:8080 |
| Doc API (via proxy) | http://localhost:8080/docs | http://localhost:8080/docs |
| API directe | http://localhost:8000/docs | non exposée |
| Console MinIO | http://localhost:9001 | non exposée |
| PostgreSQL | 127.0.0.1:5432 | non exposée |

> Le mode dev charge automatiquement `docker-compose.override.yml`, qui rouvre les ports d'admin (bindés sur `127.0.0.1`, donc inaccessibles depuis le réseau). Le mode prod ignore cet override.

Cibles utiles :

```bash
make help      # liste toutes les commandes
make logs      # suit les logs en direct
make health    # teste frontend + API + doc à travers le proxy
make ps        # état des conteneurs
make seed      # re-peuple les données de démo
make psql      # session psql sur la base
make down      # arrête (conserve les données)
make clean     # arrête et supprime les volumes
```

> Avant un déploiement réel, éditez `.env` pour changer les mots de passe PostgreSQL et MinIO, et passez `SEED_ON_START=0`.

## Démarrage manuel (dev sans Docker)

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed          # peuple des données de démo (SQLite)
uvicorn app.main:app --reload
```
API sur http://localhost:8000 — doc interactive sur http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev
```
UI sur http://localhost:5173 (proxy /api vers le backend en 8000)

---

## Architecture cible (production)

```
Frontend (React) ── Backend (FastAPI) ── PostgreSQL
                              │
                              ├── MinIO (S3) ........ Evidence Vault
                              ├── Keycloak .......... AuthN/AuthZ
                              ├── Celery / Redis .... jobs async
                              └── Grafana ........... reporting
```

## Évolutions v2 (préparées dans le code)

- Import automatique du framework ATT&CK depuis MITRE
- Connecteurs Jira / ServiceNow / SIEM / BAS (Picus, AttackIQ)
- Heatmap ATT&CK par application
- Couverture par groupe de menaces (APT29, FIN7, Scattered Spider…)
- Génération de rapports PDF
