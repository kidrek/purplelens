# Deployment Guide — Purple Team Steering Cockpit

🇫🇷 [Version française](../deploiement.md)

This guide describes a production deployment **from scratch**. It complements the
`README.md` (overview) and the operating runbooks ([operations.md](operations.md),
[runbook-vault.md](runbook-vault.md)).

Audience: the team installing and operating the platform. Prerequisites: Docker Engine
24+, Docker Compose v2, a domain name, and a TLS certificate (or the dev self-signed
one).

---

## 1. Topology and least-exposure principle

Only one service publishes ports to the outside: the **`frontend`** service (nginx), a
reverse proxy that terminates TLS, serves the SPA and routes to the BFF (it is the only
service attached to the `edge` Docker network). All data services (PostgreSQL, MinIO,
Vault, Redis, ClamAV, Keycloak) live on the **`internal`** Docker network with no
published port. This invariant is verified automatically (`test_network_exposure.py`,
`make config` target): a deployment that exposed a database would fail acceptance.

```
Internet ──443──▶ frontend (nginx, TLS, SPA)
                     └──▶ api (FastAPI/BFF) ──▶ postgres · minio · vault · redis · clamav
                                           └──▶ keycloak (OIDC)
```

Consequence: never publish a database port "for debugging". Use
`docker compose exec` on the internal network instead.

---

## 2. Secrets — generate them first

The `.env` file (copied from `.env.example`) carries the configuration. **No
`change-me-*` value may remain in production.** Generation is tooled:

```bash
cp .env.example .env
make secrets        # replaces every "change-me-*" value with strong secrets
```

`make secrets` (idempotent, re-run automatically by `make up`/`migrate`/`test*`) covers
JWT_SIGNING_KEY, TOTP_ENC_KEY and the service passwords. Two remain manual because they
are provisioned elsewhere: `VAULT_TOKEN` (from `make init-vault`) and
`OIDC_CLIENT_SECRET` (client secret of the Keycloak realm).

Points of attention:

- **`ENVIRONMENT=production`** — indispensable in production. This variable enables
  rejection of weak/default secrets at API startup and **disables Swagger/OpenAPI**
  (`/api/docs`). Without it, the platform runs in development mode.
- **`APP_MIGRATOR_PASSWORD` vs `APP_API_PASSWORD`.** Two distinct SQL roles.
  `app_migrator` owns the schema and is only used by Alembic. `app_api` is the service
  role, **`NOBYPASSRLS`**: it is the keystone of tenant isolation (layer 2). Never
  confuse them.
- **`JWT_SIGNING_KEY`.** Rotating it invalidates every active session — plan for it.
- **`VAULT_TOKEN`.** Restrict it to a *wrap/unwrap only* policy (see
  [runbook-vault.md](runbook-vault.md)). It must not be able to read keys in the clear.
- **Exposed ports (`EDGE_HTTPS_PORT`, etc.).** Freely customizable: the public host
  embedded in presigned download URLs (deliverables/evidence) is derived from the
  incoming request (`X-Forwarded-Host` header, set by nginx on `/api/`), never frozen
  in a variable — nothing to resynchronize when you change a port. Only
  `MINIO_PUBLIC_PATH_PREFIX` (default `/storage`) must stay consistent with the
  matching `location` in `nginx.conf`.
- **`LOCAL_ACCOUNTS_ENABLED`.** Leave it `false` in production: authentication goes
  through the IdP (Keycloak/OIDC). Local (password) accounts are for dev and
  acceptance only.

---

## 3. Installation order

Order matters: data before the application, secrets before encrypted data.

```bash
make bootstrap      # starts the stack (up), waits for PostgreSQL, then migrate + seed
make init-vault     # Vault init, unseal, transit engine, wrap/unwrap policy
make seed-demo      # OPTIONAL: rich demo dataset (audits, exercises, vulns…)
```

Key steps in detail:

1. **`make bootstrap`** = `make up` (which regenerates the secrets via `make secrets`),
   waiting for PostgreSQL, `make migrate` (alembic upgrade head under `app_migrator`)
   then `make seed` (reference catalogs + organizations + demo accounts; MinIO buckets
   **with Object Lock**, COMPLIANCE mode — WORM cannot be disabled afterwards). The SQL
   roles `app_migrator`/`app_api` are created by the Postgres entrypoint
   (`00-roles.sh`) and the Keycloak realm (`deploy/keycloak/realm-purple.json`) is
   imported at container startup.
2. **`make init-vault`** is **interactive** (threshold unsealing: 5 shares, 3
   required). Keep the unseal shares offline, distributed among several holders.
   Without an unsealed Vault, no evidence can be encrypted or read.
3. **`make migrate`** applies the schema under `app_migrator`. Re-run on every upgrade.
4. **`make seed-demo`** (optional, more demo/acceptance than production) adds a
   complete business dataset: multi-category audits, multi-run Purple exercises,
   vulnerabilities, tickets, CTI scenarios, deliverables. Idempotent, to run after
   `make seed`. Variant **`make seed-demo-fresh`**: first purges all business data
   (including pollution left by the tests, which share the database) while preserving
   reference catalogs, corpus, accounts, seed organizations and journal, then
   re-seeds.

Then check the network exposure:

```bash
make config         # shows the resolved config AND refuses if more than one service publishes ports
```

---

## 4. External integrations

The platform relies on three upstream integrations, all following the same pattern:
**configurable URL + graceful fallback + isolation**. None blocks startup.

### 4.1 Vulnerability enrichment (CIRCL Vulnerability-Lookup)

- `ENRICHMENT_BASE_URL` (default `https://vulnerability.circl.lu`),
  `ENRICHMENT_TIMEOUT_SECONDS`.
- Provides CVSS (priority 4.0 > 3.1 > 3.0 > 2.0), CWE, description, products, CPE,
  and — when the source aggregates them — **EPSS and KEV status**, from which the SSVC
  decision is derived.
- Offline: enrichment switches to "deferred" status, the application stays functional.
  An internal mirror can be pointed to via `ENRICHMENT_BASE_URL`.

### 4.2 MITRE / MISP reference catalogs

- `ATTACK_STIX_URL` (+ `ATTACK_MOBILE_STIX_URL`, `ATTACK_ICS_STIX_URL`),
  `D3FEND_ONTOLOGY_URL`, `CAPEC_XML_URL`, `CWE_XML_ZIP_URL`, `MISP_THREAT_ACTOR_URL`,
  `REFERENCE_SYNC_TIMEOUT_SECONDS` (default 90 s).
- Online synchronization fetches the **complete** catalogs: multi-domain ATT&CK
  (Enterprise + Mobile + ICS merged), D3FEND, the entire CWE and CAPEC dictionaries,
  ATT&CK groups and MISP Galaxy actors. The cumulative download weighs ~50 MB: prefer
  the **initial sync via CLI** (`make sync-reference`) over a web request.
- Fallback: if a source is unreachable, the embedded baseline (curated catalog) is
  loaded and the event is journaled (`fallback` status). For an air-gapped
  environment, point every URL at an internal mirror (and/or `SEED_SYNC_ONLINE=false`
  for the first seed).

### 4.3 Identity (Keycloak / OIDC)

- `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`.
- *Confidential* client with PKCE S256. The IdP **authenticates**; the product
  **authorizes** (the RBAC matrix is internal, never delegated to the IdP). The
  reference realm is provided.

---

## 5. TLS and reverse proxy

In development, `make tls` generates a self-signed certificate. In production:

- Terminate TLS on the `frontend` service (nginx) with a valid certificate (Let's
  Encrypt or internal PKI), dropped into `deploy/nginx/tls/`.
- `nginx.conf` sets hardening headers: a strict **Content-Security-Policy** and
  **HSTS**. Only enable HSTS (already present in the provided config) once TLS is
  stable — the header commits browsers over time.
- `MINIO_SECURE=false` is correct **if** TLS is terminated at the upstream proxy;
  MinIO stays in cleartext on the internal network. If MinIO must serve TLS directly,
  switch `MINIO_SECURE=true`.
- `EDGE_BIND_ADDRESS=127.0.0.1` if an upstream firewall / load-balancer already
  terminates TLS.
- `EXPOSE_ADMIN_CONSOLES=false`: the MinIO/Keycloak consoles are not routed by
  default.

---

## 6. Post-deployment verification (smoke test)

```bash
make test-security     # blocking security families (fast) — pass before opening
curl -kfsS https://$PUBLIC_HOST/api/health   # the BFF answers
```

Recommended manual checks once the stack is open:

1. **Sign-in** via the IdP with a test account, MFA required for sensitive roles.
2. **Isolation.** An account scoped to one client only sees that client (lists AND
   aggregates).
3. **Evidence.** Deposit a file → check it goes through the sandbox (ClamAV), is
   encrypted (Vault unsealed) and lands in MinIO with Object Lock.
4. **Journal.** `make verify-journal` (or the admin action) recomputes the chain: no
   break.
5. **Catalogs.** Run `make sync-reference`; confirm the per-catalog counts
   (multi-domain ATT&CK, D3FEND, CWE, CAPEC, groups, actors) and the journal entry.

---

## 7. Upgrading

```bash
make down
git pull && docker compose build
make migrate        # applies the new migrations under app_migrator
make up
make test-security  # re-checks the invariants before reopening
```

Migrations are additive and idempotent; back up beforehand (`make backup` — see
[operations.md](operations.md)). For a rollback, restore the pg snapshot + MinIO + the
sealed Vault export.

---

## 8. Frequent deployment errors

| Symptom | Probable cause | Fix |
|---|---|---|
| `make config` fails (ports) | a data service publishes a port | remove the `ports:` — go through the internal network |
| No row visible in the database | application context not established / `app_api` misconfigured | that is the expected *fail-closed* behavior; access goes through the API |
| Evidence: encryption failure | Vault sealed or policy too restrictive | unseal Vault ([runbook-vault.md](runbook-vault.md)); check the wrap/unwrap policy |
| Broken deliverable download | `X-Forwarded-Host` not forwarded by an upstream proxy, or `MINIO_PUBLIC_PATH_PREFIX` misaligned with nginx.conf | check that `/api/` forwards `X-Forwarded-Host` (see nginx.conf) |
| `.local` login returns 422 | e-mail validation too strict | already covered by the e2e acceptance; check the deployed version |
| ATT&CK sync always in `fallback` | outbound network to GitHub blocked | open the egress or point at an internal mirror |
