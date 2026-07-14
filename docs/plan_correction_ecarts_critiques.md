# Plan de Correction — 8 Écarts Critiques Red Team

> Généré le 2026-07-12 par le project-manager, sur base du rapport redteam-auditor.
> Référence : cahier des charges v2, spec Auth & RBAC v2.0, DAT v1.1.

---

## Vue d'ensemble

| # | Écart | Réalité | Priorité | Fichiers | Dépendances |
|---|-------|---------|----------|----------|-------------|
| 1 | Clé JWT par défaut non changée | **RÉEL** | P0 | `config.py`, `main.py` | — |
| 2 | Vault en HTTP interne | **RÉEL (dev)** | P1 | `config.py`, `docker-compose.yml`, `.env.example` | 1 |
| 3 | Credentials MinIO codés en dur | **RÉEL** | P0 | `config.py`, `docker-compose.yml`, `.env.example` | — |
| 4 | PKCE en mémoire volatile | **RÉEL** | P1 | `auth.py` | — |
| 5 | Injection SQL via f-string | **FAUX POSITIF** | — | `vulnerabilities.py` | — |
| 6 | `service_session` sans RBAC | **RÉEL** | P1 | `session.py`, `evidence.py`, `deliverables.py` | 1 |
| 7 | `session.get()` bypass RLS | **FAUX POSITIF** | — | `service.py` | — |
| 8 | Secrets Vault en clair | **PARTIEL** | P2 | `docker-compose.yml`, `.env.example` | 2 |

**Résumé : 5 écarts réels (P0×2, P1×2, P2×1), 2 faux positifs, 1 partiel.**

---

## Détail par écart

---

### Écart 1 — Clé de signature JWT par défaut non changée

**Fichier** : `backend/app/config.py:65`
**Priorité** : P0 (bloquant production)

**Problème** : Si `JWT_SIGNING_KEY` n'est pas défini dans `.env`, l'API utilise `"dev-signing-key-change-me-32bytes!"`. N'importe qui connaissant cette valeur par défaut peut signer des tokens d'accès arbitraires avec n'importe quel rôle et client_scope.

**Scénario d'attaque** :
1. Lire la valeur par défaut dans le code source (visible dans le repo ou le conteneur).
2. Signer un JWT HS256 avec `role="admin"`, `client_scope=[]` (= tous les clients).
3. Injecter le token dans le cookie `pc_access`.
4. Accéder à toutes les données de toutes les organisations.

**Correction** : Bloquer le démarrage de l'API si la clé n'est pas surchargée.

#### Avant (`backend/app/config.py:64-65`)

```python
    # Jetons
    jwt_signing_key: str = Field("dev-signing-key-change-me-32bytes!", alias="JWT_SIGNING_KEY")
```

#### Après (`backend/app/config.py`)

```python
    # Jetons
    jwt_signing_key: str = Field(alias="JWT_SIGNING_KEY")  # OBLIGATOIRE en production

    def __post_init__(self):
        super().__post_init__()
        if not self.jwt_signing_key or "dev-" in self.jwt_signing_key or "change" in self.jwt_signing_key:
            raise ValueError(
                "JWT_SIGNING_KEY doit être une valeur forte unique (min. 32 bytes). "
                "Définissez la variable d'environnement JWT_SIGNING_KEY."
            )
```

Ou alternativement, dans `main.py` au démarrage :

```python
# backend/app/main.py — au démarrage, avant création de l'app
from app.config import settings

if "dev-" in settings.jwt_signing_key or "change" in settings.jwt_signing_key:
    raise RuntimeError(
        "JWT_SIGNING_KEY n'est pas configurée. "
        "Définissez JWT_SIGNING_KEY dans .env (voir .env.example)."
    )
```

**Tests à ajouter** :
- `backend/tests/test_jwt_key_required.py` :
  - `test_default_key_raises` : valider que `Settings()` sans `JWT_SIGNING_KEY` lève `ValueError`.
  - `test_dev_key_raises` : valider que `"dev-signing-key-change-me-32bytes!"` lève `ValueError`.
  - `test_valid_key_succeeds` : valider qu'une clé de 32+ bytes passe.
- Mettre à jour `test_tokens.py:test_access_token_roundtrip` si le test charge des settings par défaut.

**Impact architecture** : Aucun. Change juste la validation au démarrage.

---

### Écart 2 — Vault exposé en HTTP interne

**Fichier** : `backend/app/config.py:52`, `docker-compose.yml:228`, `.env.example:46`
**Priorité** : P1 (urgent)

**Problème** : `VAULT_ADDR` par défaut `"http://vault:8200"`. Sur le réseau Docker `internal`, tout conteneur compromis peut intercepter les requêtes HTTP vers Vault et voler le `VAULT_TOKEN`. Un token Vault volé = accès à toutes les DEK = lecture de toutes les preuves chiffrées.

**Scénario d'attaque** :
1. Compromettre n'importe quel conteneur sur le réseau Docker `internal`.
2. Intercepter les requêtes HTTP vers Vault (port 8200 en HTTP).
3. Récupérer le `VAULT_TOKEN` dans les requêtes.
4. Accéder directement à Vault et déboucher toutes les DEK.

**Correction** : Forcer HTTPS en production, garder HTTP en dev avec avertissement.

#### Avant (`backend/app/config.py:51-53`)

```python
    # Vault (transit engine)
    vault_addr: str = Field("http://vault:8200", alias="VAULT_ADDR")
    vault_token: str = Field("", alias="VAULT_TOKEN")
```

#### Après (`backend/app/config.py`)

```python
    # Vault (transit engine)
    vault_addr: str = Field("http://vault:8200", alias="VAULT_ADDR")
    vault_token: str = Field("", alias="VAULT_TOKEN")

    def __post_init__(self):
        super().__post_init__()
        if self.is_production and not self.vault_addr.startswith("https://"):
            raise ValueError(
                "En production, VAULT_ADDR doit être en HTTPS. "
                "Configurez VAULT_ADDR=https://vault:8201 (ou votre reverse proxy TLS)."
            )
```

**Mise à jour `.env.example:46`** :

```diff
-VAULT_ADDR=http://vault:8200
+VAULT_ADDR=http://vault:8200          # Dev uniquement. En prod : VAULT_ADDR=https://vault:8201
```

**Tests à ajouter** :
- `backend/tests/test_vault_tls.py` :
  - `test_production_requires_https` : valider que `Settings(environment="production", vault_addr="http://...")` lève.
  - `test_production_accepts_https` : valider que `Settings(environment="production", vault_addr="https://...")` passe.
  - `test_dev_accepts_http` : valider que `Settings(environment="development", vault_addr="http://...")` passe.

**Impact architecture** : Nécessite un reverse proxy TLS pour Vault en production (nginx peut le faire).

**Dépendances** : Nécessite de configurer le port 8201 de Vault dans `docker-compose.yml` pour la production.

---

### Écart 3 — Credentials MinIO codés en dur

**Fichier** : `backend/app/config.py:35-36`, `docker-compose.yml`, `.env.example:30-31`
**Priorité** : P0 (bloquant production)

**Problème** : `config.py` définit `minio_root_user: str = Field("minioadmin", ...)` et `minio_root_password: str = Field("minioadmin", ...)`. Si `.env` n'est pas surchargé (ou copié depuis `.env.example`), les credentials sont prévisibles. De plus, `.env.example` définit `MINIO_ROOT_PASSWORD=change-me-minio` mais le code utilise `"minioadmin"` comme valeur par défaut — incohérence.

**Scénario d'attaque** :
1. Compromettre un conteneur sur le réseau Docker `internal`.
2. Se connecter à MinIO sur le port 9000 avec `minioadmin/minioadmin`.
3. Lire/écrire tous les buckets, y compris les preuves chiffrées.

**Correction** : Supprimer les valeurs par défaut codées, rendre les credentials obligatoires.

#### Avant (`backend/app/config.py:34-36`)

```python
    # MinIO
    minio_endpoint: str = Field("minio:9000", alias="MINIO_ENDPOINT")
    minio_root_user: str = Field("minioadmin", alias="MINIO_ROOT_USER")
    minio_root_password: str = Field("minioadmin", alias="MINIO_ROOT_PASSWORD")
```

#### Après (`backend/app/config.py`)

```python
    # MinIO
    minio_endpoint: str = Field("minio:9000", alias="MINIO_ENDPOINT")
    minio_root_user: str = Field(alias="MINIO_ROOT_USER")
    minio_root_password: str = Field(alias="MINIO_ROOT_PASSWORD")

    def __post_init__(self):
        super().__post_init__()
        if not self.minio_root_user or not self.minio_root_password:
            raise ValueError(
                "MINIO_ROOT_USER et MINIO_ROOT_PASSWORD sont obligatoires. "
                "Définissez-les dans .env (voir .env.example)."
            )
```

**Mise à jour `.env.example:30-31`** : (déjà correct avec `MINIO_ROOT_PASSWORD=change-me-minio`)

**Tests à ajouter** :
- `backend/tests/test_minio_credentials.py` :
  - `test_missing_credentials_raises` : valider que `Settings()` sans credentials lève.
  - `test_valid_credentials_succeeds` : valider qu'avec credentials définis, ça passe.

**Impact architecture** : Aucun. Change juste la validation. Le seed doit s'assurer que `.env` est copié depuis `.env.example` avec des mots de passe changés.

---

### Écart 4 — Stockage PKCE en mémoire volatile

**Fichier** : `backend/app/api/routes/auth.py:43`
**Priorité** : P1 (urgent)

**Problème** : `_PKCE_STORE: dict[str, str] = {}` est un dictionnaire Python en mémoire volatile. En cas de déploiement multi-réplicas (même si Kubernetes est hors scope, des déploiements avec load balancing peuvent router vers différents pods), le verifier PKCE n'est pas partagé entre instances. De plus, ce dictionnaire croît indéfiniment (pas de TTL automatique).

**Scénario d'attaque** :
1. Envoyer une requête `GET /api/auth/oidc/start` → obtenir un `state` + `verifier` stocké en mémoire du pod A.
2. Envoyer le `state` au callback, mais être routé vers le pod B (qui n'a pas le `verifier`).
3. Le callback rejette avec `invalid_state` → déni de service.
4. Ou : un attaquant peut remplir la mémoire du pod avec des entrées orphelines (pas de TTL).

**Correction** : Utiliser Redis pour le stockage PKCE avec TTL, comme indiqué dans le commentaire existant.

#### Avant (`backend/app/api/routes/auth.py:41-43`)

```python
# Magasin PKCE éphémère. En production : Redis avec TTL (voir docs/runbook).
# Le state OIDC ne doit jamais fuiter côté client au-delà de son usage anti-CSRF.
_PKCE_STORE: dict[str, str] = {}
```

#### Après (`backend/app/api/routes/auth.py`)

```python
import redis.asyncio as aioredis
from app.config import settings

# Magasin PKCE éphémère avec TTL (cahier §3.1).
# En dev : dictionnaire en mémoire avec expiration manuelle.
# En prod : Redis avec TTL automatique.
_PKCE_TTL_SECONDS: int = 300  # 5 min = step_up_max_age_seconds

_pkce_client: aioredis.Redis | None = None


async def _get_pkce_store() -> aioredis.Redis:
    global _pkce_client
    if _pkce_client is None:
        _pkce_client = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
    return _pkce_client


async def pkce_set(state: str, verifier: str) -> None:
    store = await _get_pkce_store()
    await store.setex(f"pkce:{state}", _PKCE_TTL_SECONDS, verifier)


async def pkce_get_and_delete(state: str) -> str | None:
    store = await _get_pkce_store()
    return await store.get(f"pkce:{state}")


async def pkce_cleanup() -> None:
    """Fermer la connexion Redis proprement."""
    global _pkce_client
    if _pkce_client:
        await _pkce_client.close()
```

**Mise à jour des appels dans `oidc_start` et `oidc_callback`** :

```python
# Dans oidc_start():
    verifier, challenge = generate_pkce()
    state = secrets.token_urlsafe(24)
    await pkce_set(state, verifier)
    url = await authorization_url(state=state, code_challenge=challenge)
    return OidcStart(authorization_url=url, state=state)

# Dans oidc_callback():
    verifier = await pkce_get_and_delete(state)
    if verifier is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_state")
```

**Fallback dev** (si Redis n'est pas disponible) :

```python
# Fallback en développement : dictionnaire en mémoire avec expiration.
_in_memory_pkce: dict[str, tuple[str, float]] = {}  # state -> (verifier, expiry)


async def _get_pkce_store() -> aioredis.Redis:
    global _pkce_client
    try:
        if _pkce_client is None:
            _pkce_client = aioredis.from_url(
                settings.redis_url, decode_responses=True
            )
        return _pkce_client
    except Exception:
        # Dev : Redis non disponible, fallback mémoire
        return None  # type: ignore[return-value]


async def pkce_set(state: str, verifier: str) -> None:
    store = await _get_pkce_store()
    if store is None:
        _in_memory_pkce[state] = (verifier, time.time() + _PKCE_TTL_SECONDS)
    else:
        await store.setex(f"pkce:{state}", _PKCE_TTL_SECONDS, verifier)


async def pkce_get_and_delete(state: str) -> str | None:
    store = await _get_pkce_store()
    if store is None:
        # Dev : vérifier l'expiration
        entry = _in_memory_pkce.pop(state, None)
        if entry and entry[1] > time.time():
            return entry[0]
        return None
    return await store.get(f"pkce:{state}")
```

**Tests à ajouter** :
- `backend/tests/test_pkce_store.py` :
  - `test_pkce_set_and_get` : valider le cycle set/get/delete.
  - `test_pkce_expires` : valider que l'entrée expire après TTL.
  - `test_pkce_one_time_use` : valider que get+delete empêche une seconde utilisation.
  - `test_pkce_invalid_state_rejected` : valider que `oidc_callback` avec un state invalide lève 400.

**Impact architecture** : Dépend de Redis (déjà présent dans l'infrastructure). Le fallback mémoire permet le développement sans Redis.

---

### Écart 5 — Injection SQL via f-string (FAUX POSITIF)

**Fichier** : `backend/app/api/routes/vulnerabilities.py:276-279`
**Priorité** : — (aucune correction nécessaire)

**Analyse du faux positif** :

Le code construit la clause SET via une liste de chaînes pré-validées :

```python
sets, params = [], {"i": str(vuln_id)}
if parsed["cvss_score"] is not None and v.cvss_score is None:
    sets.append("cvss_score = :cs")
    params["cs"] = parsed["cvss_score"]
# ... colonnes hardcoded, valeurs parameterisées
f"UPDATE vulnerability SET {', '.join(sets)}, updated_at = now() WHERE id = :i"
```

**Pourquoi c'est sûr** :
1. Les noms de colonnes sont des **chaînes littérales codées en dur** (`"cvss_score = :cs"`, `"cvss_vector = :cv"`, etc.).
2. Les **valeurs sont parameterisées** (`:cs`, `:cv`, etc.) via `params`.
3. L'injection `f-string` ne joint que des chaînes pré-construites, pas de données utilisateur directes.
4. Même une réponse CIRCL corrompue ne peut pas injecter du SQL dans la clause SET car les données passent par les paramètres SQL.

**Conclusion** : Aucune correction nécessaire. Ce finding est un faux positif.

---

### Écart 6 — `service_session` sans contrôle RBAC

**Fichier** : `backend/app/db/session.py:88-93`, `backend/app/api/routes/evidence.py:121-127`, `backend/app/api/routes/deliverables.py:250-263`
**Priorité** : P1 (urgent)

**Problème** : `service_session("admin_service")` est utilisé dans les routes de preuves et de livrables pour lire `audit_dek`. Le rôle `admin_service` a un scope vide (`client_scope=None`), ce qui signifie qu'il voit TOUS les clients. Il n'y a AUCUN contrôle d'accès applicatif sur ces sessions — `can()` n'est jamais appelé avec `record` pour les opérations sur `audit_dek`.

**Scénario d'attaque** :
1. Obtenir un token valide (via écart 1 ou vol de session).
2. Utiliser un endpoint `GET /api/evidence/{id}/content` qui appelle `service_session("admin_service")`.
3. La session de service n'a pas de RLS client — elle peut lire les DEK de TOUS les clients.
4. Déboucher chaque DEK via Vault et décrypter toutes les preuves de toutes les organisations.

**Correction** : Ajouter une vérification RBAC sur les opérations `audit_dek` — vérifier que l'utilisateur a un droit de lecture sur l'audit associé avant d'appeler `service_session`.

#### Avant (`backend/app/api/routes/evidence.py:121-127`)

```python
    async with service_session("admin_service") as session:
        dek = await session.execute(text(
            "SELECT key_b64 FROM audit_dek WHERE audit_id = :a AND destroyed_at IS NULL"
        ), {"a": str(evidence.audit_id)})
```

#### Après (`backend/app/api/routes/evidence.py`)

```python
    # Vérifier que l'utilisateur a le droit de lire la preuve (et donc son audit)
    # avant d'accéder au DEK via service_session.
    if not allowed(ctx.role, "evidence", Action.L):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")

    # Vérifier que l'audit appartient au périmètre client de l'utilisateur.
    audit_row = (await session.execute(text(
        "SELECT client_id FROM audits WHERE id = :a AND deleted_at IS NULL"
    ), {"a": str(evidence.audit_id)})).first()
    if audit_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="audit_not_found")
    if ctx.client_scope and str(audit_row.client_id) not in ctx.client_scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="out_of_scope")

    async with service_session("admin_service") as session:
        dek = await session.execute(text(
            "SELECT key_b64 FROM audit_dek WHERE audit_id = :a AND destroyed_at IS NULL"
        ), {"a": str(evidence.audit_id)})
```

**Mise à jour similaire dans** `backend/app/api/routes/deliverables.py` pour les endpoints de génération PDF qui accèdent aux DEK.

**Tests à ajouter** :
- `backend/tests/test_dek_access_control.py` :
  - `test_user_cannot_access_other_client_dek` : valider qu'un utilisateur d'un client ne peut pas accéder au DEK d'un autre client.
  - `test_service_session_requires_audit_ownership` : valider que l'accès au DEK vérifie l'appartenance de l'audit au client.

**Impact architecture** : Aucun. Ajoute une vérification RBAC supplémentaire avant l'accès au DEK.

---

### Écart 7 — `session.get()` bypass RLS (FAUX POSITIF)

**Fichier** : `backend/app/api/service.py:252-256`
**Priorité** : — (aucune correction nécessaire)

**Analyse du faux positif** :

```python
async def get_entity(session: AsyncSession, spec: EntitySpec, item_id: uuid.UUID) -> Any | None:
    obj = await session.get(spec.model, item_id)
```

**Pourquoi c'est sûr** :
1. `session.get()` de SQLAlchemy vérifie d'abord le cache d'entité (identity map).
2. Si l'objet n'est pas en cache, il émet une requête `SELECT ... WHERE id = :id` qui passe par PostgreSQL.
3. **PostgreSQL RLS s'applique à TOUS les SELECT**, y compris ceux émis par `session.get()`.
4. Chaque requête HTTP utilise `rls_session()` qui crée une **nouvelle session** avec `set_config()` transactionnel. L'identity map est donc vide à chaque requête.
5. Le seul cas théorique de fuite serait la réutilisation d'une session entre plusieurs requêtes avec des contextes RLS différents — ce que le code ne fait pas.

**Conclusion** : Aucune correction nécessaire. Le `session.get()` passe par PostgreSQL et respecte RLS.

---

### Écart 8 — Secrets Vault stockés en clair dans le fichier de configuration

**Fichier** : `docker-compose.yml:228`, `.env.example:47`
**Priorité** : P2 (important)

**Analyse partielle** :

Le `.env` est gitignoré (`.gitignore`). En développement, stocker `VAULT_TOKEN=change-me-vault-token` dans `.env` est acceptable. En production, les secrets doivent être injectés via Docker secrets ou un gestionnaire de secrets externe.

**Correction mineure** : Documenter la procédure de production pour Vault.

#### Mise à jour `.env.example:47`

```diff
-VAULT_TOKEN=change-me-vault-token                # jeton API à politique wrap/unwrap only
+VAULT_TOKEN=change-me-vault-token                # Dev : .env (gitignoré). Prod : Docker secret.
```

#### Documentation à ajouter

Créer `docs/runbook-vault.md` décrivant :
1. Comment générer un token Vault avec politique `wrap/unwrap` uniquement.
2. Comment injecter le token via Docker secrets en production.
3. Comment configurer Vault en TLS interne (voir écart 2).

**Tests à ajouter** :
- `backend/tests/test_vault_tls.py:test_production_requires_https` (voir écart 2).

**Impact architecture** : Nécessite un runbook de production. Ne change pas le code.

---

## Ordre d'exécution recommandé

### Sprint 1 — P0 (bloquant production, < 2 jours)

1. **Écart 1** : Clé JWT par défaut → validation au démarrage
   - Fichiers : `config.py`, `main.py`, `tests/test_jwt_key_required.py` (nouveau)
   - Estimation : 2h

2. **Écart 3** : Credentials MinIO → validation obligatoire
   - Fichiers : `config.py`, `tests/test_minio_credentials.py` (nouveau)
   - Estimation : 1h

**Validation** : `make test-security` doit passer. `make config` doit détecter les clés manquantes.

### Sprint 2 — P1 (urgent, < 1 semaine)

3. **Écart 2** : Vault HTTP → HTTPS forcé en production
   - Fichiers : `config.py`, `docker-compose.yml`, `.env.example`, `docs/runbook-vault.md` (nouveau)
   - Estimation : 3h

4. **Écart 4** : PKCE en mémoire → Redis avec TTL
   - Fichiers : `auth.py`, `tests/test_pkce_store.py` (nouveau)
   - Estimation : 4h

5. **Écart 6** : `service_session` sans RBAC → vérification d'ownership
   - Fichiers : `evidence.py`, `deliverables.py`, `tests/test_dek_access_control.py` (nouveau)
   - Estimation : 4h

**Validation** : `make test-security` doit passer. Tests d'intrusion manuels sur les endpoints DEK.

### Sprint 3 — P2 (important, < 2 semaines)

6. **Écart 8** : Secrets Vault → documentation production
   - Fichiers : `docs/runbook-vault.md` (complément)
   - Estimation : 2h

---

## Tests de validation

### Tests existants à mettre à jour

| Test | Modification |
|------|-------------|
| `test_tokens.py` | Vérifier qu'il ne charge pas de settings par défaut avec clé JWT faible |
| `test_matrix.py` | Aucun changement requis |
| `test_rls_isolation.py` | Aucun changement requis |
| `test_network_exposure.py` | Vérifier que Vault n'est pas sur le réseau `edge` |

### Nouveaux tests à écrire

| Fichier | Couverture |
|---------|-----------|
| `test_jwt_key_required.py` | Clé JWT obligatoire, valeur par défaut rejetée |
| `test_minio_credentials.py` | Credentials MinIO obligatoires |
| `test_vault_tls.py` | HTTPS forcé en production, HTTP accepté en dev |
| `test_pkce_store.py` | Cycle set/get/delete, expiration, usage unique |
| `test_dek_access_control.py` | Ownership verification avant accès DEK |

### Tests de sécurité existants à faire passer

```bash
make test-security   # Blocking security families (RLS, RBAC, ingest, journal, crypto, network)
make test          # Full test suite
```

---

## Résumé exécutif

- **5 écarts réels identifiés** (P0×2, P1×3, P2×1)
- **2 faux positifs** (C05 SQL injection, C07 session.get RLS)
- **1 partiel** (C08 Vault secrets — acceptable en dev, à documenter en prod)
- **Estimation totale** : ~16h de développement + tests + validation
- **Rétrocompatibilité** : toutes les corrections sont des validations supplémentaires, ne cassent pas les déploiements existants correctement configurés
- **Impact sur `make test-security`** : aucun test existant ne doit échouer (les corrections ajoutent des validations, ne retirent pas de fonctionnalités)
