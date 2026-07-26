# Operations Guide — Purple Team Steering Cockpit

🇫🇷 [Version française](../exploitation.md)

Day-2 operating procedures once the platform is in production. For the initial
installation, see [deployment.md](deployment.md); for Vault in detail,
[runbook-vault.md](runbook-vault.md).

---

## 1. Recurring tasks

### 1.1 Reference catalog synchronization

The synchronized catalogs cover **multi-domain** ATT&CK (Enterprise + Mobile + ICS
merged), D3FEND, the full **CWE** and **CAPEC** dictionaries, ATT&CK groups and **MISP
Galaxy** actors (which back the "emulate an actor" picker in scenarios). To keep
everything up to date:

```bash
# CLI (recommended — the cumulative download is ~50 MB):
make sync-reference                                               # every catalog
docker compose exec api python -m scripts.sync_reference attack   # a single catalog
```

Or from the interface (**Settings → Online sync**, administrators only). The operation
is idempotent (upsert by identifier), journaled (`reference.synced`), and falls back to
the embedded baseline when the source is unreachable (`fallback` status). Recommended
cadence: monthly, or on each major ATT&CK release.

Impact: the ATT&CK matrix and the cockpit kill-chain band immediately reflect the
enriched catalog (parent techniques + sub-techniques, with coverage roll-up).

### 1.2 Vulnerability enrichment

CIRCL enrichment is triggered on demand (per-vulnerability button) and caches
CVSS/CWE/EPSS/KEV/SSVC/CPE. No scheduled task is required, but recent CVEs can be
re-enriched periodically (EPSS and KEV evolve after publication). To check that the
source is reachable:

```bash
docker compose exec api python -c \
  "import httpx,os;print(httpx.get(os.environ['ENRICHMENT_BASE_URL']+'/api/vulnerability/CVE-2021-44228',timeout=8).status_code)"
```

### 1.3 Backup

A consistent backup covers **three** interdependent systems — the database, the
encrypted objects, and the decryption material. Backing up one without the others is
useless.

```bash
make backup    # pg_dump + MinIO mirror, timestamped (Vault KEKs are backed up SEPARATELY)
```

- **PostgreSQL**: `pg_dump` (schema + data, including the hash-chained journal and the
  wrapped DEKs).
- **MinIO**: mirror of the buckets (ciphertext, Object Lock preserved).
- **Vault**: backed up **separately**, under quorum (sealed archive of the volume —
  procedure in [runbook-vault.md](runbook-vault.md) §5), never in the same place as the
  database and objects. **Without the KEKs, the evidence is unrecoverable** (that is
  the crypto-shredding property — see §3.2).

Test restoration regularly (see §4). Keep the Vault unseal shares separate from the
data backups.

---

## 2. Monitoring and integrity

### 2.1 Journal chain verification

The audit journal is *append-only* (database trigger) and hash-chained. Verification
recomputes every fingerprint and locates any break:

```bash
make verify-journal
```

Or via the interface (**Journal → Verify chain**). Feed it into your monitoring: a
break means either tampering or storage corruption — in both cases a security incident
(see §3.1). Recommended cadence: daily — already automated by the `journal_verify`
Celery task (03:30, result sealed into the journal).

The **Journal** view additionally offers server-side filters (free text, event domain,
ok/denied result, actor, date range), a statistics panel, and a **signed JSON export**
(cross-cutting roles only, MFA step-up required) for handing over to a SIEM or an
external auditor.

### 2.1bis WORM anchoring of the journal (out-of-band detection)

On top of the hash chain, the **chain head** (sequence + current fingerprint) is sealed
every 6 h into a dedicated MinIO **Object Lock** bucket (`JOURNAL_ANCHOR_BUCKET`,
Celery task `journal_anchor`), then compared daily against the actual database state
(`journal_anchor_verify`, 04:00). A mismatch means an actor with privileged database
access rewrote the journal *and* recomputed the chain — the WORM anchor, however,
cannot be modified. Any mismatch is sealed as an alert into the journal: surface it in
monitoring.

### 2.2 Monitoring indicators

To surface in your monitoring tool:

- **Integrity**: `verify-journal` result (boolean), freshness of the latest backup,
  freshness of the latest WORM anchor (§2.1bis) and absence of `journal.anchor.*`
  alerts.
- **Vault**: *sealed/unsealed* state (a platform whose Vault re-sealed itself can no
  longer encrypt evidence).
- **Ingestion sandbox**: size of the `quarantine` bucket (abnormal growth = rejected
  files).
- **Catalogs**: date of the last successful sync; alert when too old or in `fallback`.
- **RLS**: the number of rows visible without a context must remain **zero**
  (fail-closed invariant).

---

## 3. Incident response

### 3.1 Suspected journal tampering

`verify-journal` fails → the chain is broken at a precise rank (located by the
verification).

1. Do not "repair" the chain — the goal is detection, not concealment.
2. Isolate the most recent healthy backup and compare the fingerprint at the breaking
   rank.
3. Treat it as a security incident: who had direct database access (bypassing the
   API)? Reminder: the application role `app_api` can neither `UPDATE` nor `DELETE`
   the journal; a break implies privileged access outside the application.

### 3.2 Client compromise — crypto-shredding

To make a client's evidence unrecoverable (right to erasure, end of contract,
compromise), destroying their key material is enough — without touching the stored
objects:

```bash
# Full details and precautions in runbook-vault.md (§4).
# Destroying the client's KEK makes all their DEKs — hence all their evidence — undecipherable.
```

The operation is **irreversible** and journaled. Require dual validation (MFA step-up +
a second administrator). Check beforehand that no legal retention obligation (Object
Lock COMPLIANCE) stands in the way.

### 3.3 Revoking an access

Deactivating an account is done in the IdP (Keycloak) **and** by setting its status to
`inactive` (the `can()` matrix then denies at the very first gate). The SPA renews
sessions **silently** while the user is active (access token ~10 min, refresh token 14
sliding days); this renewal **does not extend** a deactivated account: at the first
rotation (at most ~10 min), the refresh is denied (`account_inactive`) and **the whole
token family is revoked**. For an immediate cut-off, rotate `JWT_SIGNING_KEY`
(invalidates all sessions).

---

## 4. Restoration (drill and real)

```bash
# 1. Restore the database
docker compose exec -T postgres psql -U postgres purple < backup/pg_<date>.sql
# 2. Restore the objects (evidence-* buckets), Object Lock included
#    mc mirror backup/minio_<date>/ minio/
# 3. Restore/unseal Vault and re-import the KEKs (runbook-vault.md)
make init-vault
# 4. Prove end-to-end integrity
make verify-journal
```

A restoration is only validated if `verify-journal` passes **and** a restored audit's
evidence decrypts (which proves database + objects + KEKs are mutually consistent).
Schedule this drill periodically: a backup that was never restored is not a backup.

---

## 5. Access management and multi-client isolation

- **Roles** (7): `admin`, `manager`, `auditeur`, `ciso`, `voc`, `cert`, `operateur`
  (multi-client provider: full CRUD on inventory/scenarios/deliverables and validation
  of audits/vulns/tickets, **strictly confined to their scope**, no journal access).
  Rights are frozen in the RBAC matrix (`test_matrix.py` locks it) — they are not
  configurable at runtime.
- **Client scope**: an account's `client_scope` (array of ids) bounds what it sees,
  enforced by RLS. Only cross-cutting roles (admin/manager and service roles) ignore
  the scope; for **any other role, an empty scope = no access** (fail-closed, both in
  `can()` and in RLS). The interface's scope filter (top bar) only **narrows the
  display** within what RLS already allows — it never widens access.
- **Principle**: the server decides alone. Never try to widen an access in the
  database; go through the account and its scope.
- **Authentication hardening** (operational reminders): Redis rate limiting on
  `/login`, `/refresh` and `/step-up` (`RATE_LIMIT_ENABLED`, graceful degradation if
  Redis goes down); TOTP secrets encrypted at rest (AES-256-GCM, `TOTP_ENC_KEY`) with
  code anti-replay; OIDC/PKCE state in Redis (multi-worker, single-use);
  Swagger/OpenAPI disabled when `ENVIRONMENT=production`.

---

## 6. Command cheat sheet

| Need | Command |
|---|---|
| Start / stop | `make up` / `make down` |
| Follow the logs | `make logs` |
| Synchronize the catalogs | `make sync-reference` |
| Verify the journal | `make verify-journal` |
| Back up | `make backup` |
| Security acceptance (fast) | `make test-security` |
| Full acceptance | `make test` |
| Check network exposure | `make config` |
| Apply migrations | `make migrate` |
