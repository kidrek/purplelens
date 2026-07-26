# Acceptance & hardening — Purple Team Cockpit (DAT Phase 6)

🇫🇷 [Version française](../RECETTE.md)

This document consolidates the acceptance procedure and the operating runbooks. It
complements the requirements specification (v2) §7 criteria and the DAT's security
invariants.

## 1. Automated acceptance

Acceptance relies on three test families, reproducible locally (migrated database
required; everything is containerized via the `make` targets):

| Target | Scope | Blocking |
|--------|-------|----------|
| `make test` | Full suite (35 files, ~200 tests) | yes |
| `make test-security` | §6 security families: RLS, RBAC matrix, journal, crypto, sandbox, network exposure | yes |
| `make test-e2e` | End-to-end HTTP: login, CRUD, auto-naming, SLA, date coercion, RLS via the API, STIX export | yes |

The e2e test (`tests/test_e2e_http.py`) drives the real application via httpx
in-process and exercises the complete request cycle (context middleware, session
cookies, `can()`, RLS). It locks down the INTEGRATION defects that direct-session
tests cannot see — the most expensive class of bugs in deployment.

## 2. Security invariants — verification

To validate at every acceptance (automated unless noted):

1. **The server decides alone** — no client-side authorization. Verified by the
   exhaustive matrix (`test_matrix`) and the HTTP denials
   (`test_e2e_http::test_rbac_*`).
2. **Multi-client isolation** — forced PostgreSQL RLS, `app_api` with `NOBYPASSRLS`.
   Verified by `test_rls_isolation` (database) and
   `test_e2e_http::test_rls_isolation_over_http` (via the API).
3. **Unfalsifiable journal** — append-only, tamper-evident. Verified by
   `test_journal_chain`.
4. **Binaries never served by the API — with one documented exception** — upload and
   encrypted download via presigned URLs ≤ 5 min (evidence, deliverables). Deliberate
   exception: `GET /api/evidence/{id}/content` streams the **decrypted** bytes through
   the API (sole holder of the DEK — D8 defers client-side decryption); access is
   controlled on the same request, traced in `evidence_access`, and never in the clear
   for `contains_secrets` items.
5. **A single service publishes ports** — `make config` + `scripts/check_ports.py`
   (`test_network_exposure`).
6. **Step-up on high-risk actions** — account management, legal hold,
   crypto-shredding, export, KEK rotation. Verified by `test_rbac_gates`.

## 3. Runbook — Backup / restore

```bash
make backup                 # pg_dump + MinIO mirror → ./backups/<timestamp> (Vault KEKs kept separate)
make restore DIR=backups/<timestamp>
```

**Restore drill (mandatory at acceptance)**: on a pristine environment, restore the
latest backup, then replay `make test-e2e` — sign-in and scoped reads must work
identically.

## 4. Runbook — Vault (unsealing)

Vault starts sealed. After any restart:

```bash
make unseal                 # enter the quorum of unseal keys
make init-vault             # (first time) transit engine + per-client KEKs
```

⚠ Losing the Vault keys = definitive loss of the evidence (envelope encryption). The
unseal keys and the root key are kept offline, in a distributed quorum.

## 5. Runbook — First deployment

```bash
cp .env.example .env        # then `make secrets` replaces the "change-me-*" values
                            # (VAULT_TOKEN and OIDC_CLIENT_SECRET stay manual;
                            #  in production, also set ENVIRONMENT=production)
make bootstrap              # stack + schema + demo accounts (runs make secrets)
make init-vault             # transit + KEKs
make seed-demo              # optional: rich demo dataset
```

Then sign in at `https://localhost:${EDGE_HTTPS_PORT}/` with `admin@purple.local`
(password = `SEED_DEFAULT_PASSWORD`), and enroll TOTP immediately via "My account".

## 6. Switch-over — requalifying the mock-up

Once acceptance is pronounced, the HTML mock-up is officially requalified as
"demo / training" and is no longer a functional reference: the application takes its
place.
