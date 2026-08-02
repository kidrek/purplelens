# Validation — execution proof

🇫🇷 [Version française](../validation.md)

This document summarizes the checks executed on the delivered code. They were run
against a real **PostgreSQL 16** database (Alembic migration applied under the
`app_migrator` role, application queries under `app_api` with `NOBYPASSRLS`).

## Automated coverage

The full suite (`make test`) covers **35 test files (~200 tests)**. Main families
(non-exhaustive list — the exact count evolves with the code):

| Family (DAT §6)             | File                             | What it proves |
|-----------------------------|----------------------------------|----------------|
| RBAC matrix (exhaustive)    | `test_matrix.py`                 | Every role × entity is defined; journal read-only for everyone (admin included); no human access to `audit_dek`; deny-by-default outside the matrix; precise rights from the specification (VOC, CISO, Manager D6, CERT). |
| `can()` engine (5 gates)    | `test_rbac_gates.py`             | Gate order, deny by default, client isolation, TLP/PAP. |
| RLS isolation (real DB)     | `test_rls_isolation.py`          | Fail-closed without a context (0 rows); isolation by scope; empty scope + **cross-cutting** role (admin/manager/service) = all clients, empty scope + scoped role = **no access** (fail-closed); `WITH CHECK` blocks out-of-scope writes; append-only journal (trigger). |
| Envelope encryption         | `test_crypto.py`                 | AES-256-GCM round-trip; AAD binding (altering the audit_id breaks decryption); ciphertext tampering detection; 256-bit DEK required. |
| Tamper-evident journal      | `test_journal_chain.py`          | Deterministic chaining; any alteration breaks the chain. |
| Ingestion sandbox           | `test_ingest_detection.py`       | Real type detection by signature; lying extension rejected; EICAR blocked even without ClamAV. |
| Tokens / step-up            | `test_tokens.py`                 | Access token issuance/decoding; step-up freshness; MFA requirement. |
| Network exposure            | `test_network_exposure.py`       | Only `frontend` publishes ports; data services never on `edge`. |
| CVE enrichment (CIRCL)      | `test_circl_enrichment.py`       | Defensive parser on a real CVE 5.x record: CVSS priority 4.0>3.1>3.0>2.0, CWE, CPE, products, EPSS/KEV when present; offline → graceful degradation. |
| STIX 2.1 import/export      | `test_stix_import.py` · `test_stix_export.py` | Scenario ↔ bundle round-trip (techniques, actor, TLP, D3FEND); bundle without an aggregated grouping; multiple groupings. |
| Catalog sync (MITRE)        | `test_reference_sync.py`         | ATT&CK parsers (actives, standard tactic preferred) and D3FEND (ext_id + label) on samples. |
| Hierarchical ATT&CK matrix  | `test_attack_matrix.py`          | Coverage aggregation; sub-technique → parent roll-up (Navigator behavior). |
| Cockpit (aggregates)        | `test_cockpit.py`                | Detection rate, blind spots, kill-chain band (per-tactic states, order), detection trend. |
| Exercise step editor        | `test_exercise_steps.py`         | Loading from a scenario (named, ordered steps). |
| E2e acceptance — parity (HTTP) | `test_e2e_features.py`        | Step loading/reordering + guards; per-application coverage + client filter; cockpit widgets + filter; **RLS-scoped scenario usage**. |
| Journal WORM anchoring      | `test_journal_anchor.py`         | Deterministic anchor serialization; detection of an anchor ↔ database mismatch (out-of-band tampering). |
| Journal filters/stats/export | `test_journal_filters.py`       | Server-side filters (text, domain, result, actor, dates); per-client isolation; export under step-up. |
| Auth hardening              | `test_totp_ratelimit.py` · `test_secret_box.py` · `test_oidc_state.py` · `test_security_hardening_p0.py` | TOTP anti-replay + rate limiting; TOTP secrets encrypted at rest; single-use OIDC/PKCE state; JWT claim requirements and weak-secret rejection. |
| WORM bucket                 | `test_worm_bucket.py`            | Object Lock (COMPLIANCE) required on evidence and anchor buckets. |
| Derived audit actions       | `test_audit_actions.py`          | Scenario → PTES action derivation (tactic → phase mapping, deduplication, idempotence). |
| Engagement block            | `test_engagement_defaults.py`    | Server-side pre-fill of the 18 keys (parity with the drawer). |
| "My card" (profile)         | `test_profile_resource.py`       | Upsert of the account-linked person card; scope enforcement. |
| Per-view analytics          | `test_organisations_analytics.py` · `test_ressources_analytics.py` | Server aggregates for the KPI bands (organizations, people), filters included. |

## Complementary manual proofs

Checks made live on the migrated database:

- **Multi-client RLS isolation.** Two clients A and B, one audit each. `app_api`
  without a context sees nothing; with scope A it only sees audit A; with an empty
  scope and a set role (admin/manager) it sees both. An insertion attempt into client B
  from a scope-A context is rejected by the `WITH CHECK` clause.

- **Fail-closed fix.** The `app_client_visible` function was hardened to require an
  established application context (`app.role`): a raw `app_api` connection, without a
  context, returns **0 rows** (before the hardening, an empty scope without a role was
  indistinguishable from a multi-client role and let everything show).

- **Inviolable journal.** `UPDATE` and `DELETE` on `journal` are rejected by a trigger
  (`journal is append-only`). Chain verification recomputes every fingerprint: an
  alteration of an entry's **content** (even bypassing the trigger at the database
  level) is detected and locates the first break.

- **Application seed.** The seed inserts the reference catalogs (multi-domain ATT&CK /
  D3FEND / OWASP / CWE / CAPEC / groups / MISP actors), three organizations (two
  clients, one provider) and the demo accounts (`admin` / `auditeur` / `ciso` /
  `operateur`) — validating the database-side defaults. `make seed-demo` adds the rich
  business dataset (idempotent).

- **Frontend.** Production Vite build succeeds (63 modules); every view and the A/B
  theme system (verbatim design tokens) compile.

## Reproducing

Everything is containerized (no Python/Node required on the host):

```bash
make test           # full suite (api-test compose profile, migrated PostgreSQL)
make test-security  # blocking security families only
make lint           # ruff (backend) + eslint (frontend), containerized
make frontend-build # production Vite build
```

These `make` targets (`lint`, `test`, `test-security`, `config`, `frontend-build`) are
the entry points for a continuous-integration pipeline — no CI pipeline ships in the
repository at this time.
