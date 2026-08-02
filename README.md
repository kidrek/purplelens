# Purple Team Operations Cockpit

🇫🇷 [Version française](README.fr.md)

Multi-tenant platform for running a Purple Team (coordinated offensive and defensive
cybersecurity). It manages the full lifecycle: organizations, applications, people,
threat scenarios, audits, Purple exercises, attack chains, defensive observations,
vulnerabilities, detection tickets, deliverables — and an **end-to-end encrypted
evidence subsystem**.

This repository implements the project's normative documents (at the repo root):
requirements specification v2 (`cahier_des_charges_v2.md`), technical architecture DAT
v1.0 (`dat_v1.1.md`), Auth & RBAC specification v2.1
(`Backend_specification_auth_rbac_v2.md`) and artistic direction v2.7.

## Guided tour

A complete, screen-by-screen tour of the platform, in navigation order. Screenshots use
the dark SOC theme (theme B) and were taken on the demo dataset. Detailed role-based
journeys are covered in the [user guide](docs/en/user-guide.md)
([version française](docs/guide-utilisateur.md)).

### Sign-in & account

![Login page](docs/img/login.png)

*Sign-in: organization SSO (Keycloak, OIDC + PKCE) or local fallback with e-mail /
password / TOTP. Once signed in, the session is **silently renewed** while you are
active — no more untimely logouts.*

![My account](docs/img/account.png)

*My account: identity and role, **TOTP enrollment** (mandatory for operational roles and
step-up), and the "auditor card" that makes you selectable as an auditor on audits
within your scope.*

### Steering

![Cockpit — Purple Team dashboard](docs/img/cockpit.png)

*Cockpit: detection rate, blind spots, criticals past SLA, coverage per MITRE tactic,
aggregated posture and the latest journal events — restricted to your tenant scope.*

![Purple exercises — Red → Blue → Detection loop](docs/img/exercices.png)

*Purple exercises: the Red → Blue → Detection loop on a single screen — run KPIs
(coverage, steps played, detections, blind spots), posture breakdown, attack-step
timeline with defensive verdicts (prevented / alerted / logged / no telemetry) and
on-the-fly creation of remediation tickets.*

![Purple exercise card — all runs](docs/img/exercice-drawer.png)

*A Purple exercise card: the aggregated posture dashboard across **all runs** of the
audit — detection progressing run over run, per-technique verdicts, MTTD/MTTR
indicators and steps turned "covered" by a closed detection ticket.*

![Purple exercise step editor](docs/img/exercice-steps.png)

*The step editor, stacked on the exercise card: the attack chain replayed step by
step against the defensive response — verdict, detection and response timestamps, and
the Blue Team's observations for each technique.*

![Audit card — pentest engagement](docs/img/audit-drawer.png)

*Audits: an engagement card (opened from the list) — PTES progress, test actions,
emulated CTI scenario (FIN7) and the audit's ATT&CK TTP coverage.*

| | |
|---|---|
| ![Vulnerabilities](docs/img/vulnerabilities.png) | ![Detection tickets](docs/img/tickets.png) |
| Vulnerabilities & gaps: severity, CVSS, computed SLAs, CISO/Manager validation, CVE/EPSS enrichment. | Detection tickets: born from exercise blind spots, with ATT&CK technique, D3FEND countermeasure and Sigma rule. |

![Vulnerability card](docs/img/vuln-drawer.png)

*Vulnerability card: identity (client, linked audit, application, SLA), analysis,
OWASP Top 10 / CWE / CVSS classification, and online **VOC enrichment** via CIRCL —
EPSS, CISA KEV, SSVC, VEX — with graceful degradation when offline.*

![Detection ticket card](docs/img/ticket-drawer.png)

*Ticket card: ATT&CK technique and D3FEND countermeasure resolved to plain names
("T1608.004 — Drive-by Target", "D3-NTA — Network Traffic Analysis"), blind-spot
description, priority and remediation status.*

### Knowledge

![ATT&CK matrix — coverage per tactic](docs/img/attack-matrix.png)

*ATT&CK matrix: tactics as columns (covered / total), techniques tinted by status,
expandable sub-techniques, activity badges, and 4 reading layers — Coverage /
Detection / Gap / imported ATT&CK Navigator layer.*

![Threat scenarios](docs/img/scenarios.png)

*Threat scenarios: cross-tenant CTI library (emulated actors, sophistication, Admiralty
credibility), **STIX 2.1** import / export. The "emulated actor" field searches the
**threat-actor catalogs** (ATT&CK Groups + MISP Galaxy, aliases included) and can
**import the actor's TTPs** straight into the scenario's attack steps.*

![FIN7 scenario card](docs/img/scenario-drawer.png)

*A scenario card: emulated actor (FIN7), 50 TTPs with their per-tactic ATT&CK coverage,
D3FEND countermeasures, remaining blind spots and linked audits — the bridge between
intelligence and exercise.*

| | |
|---|---|
| ![Organizations](docs/img/organisations.png) | ![Applications](docs/img/applications.png) |
| Organizations: clients and providers, sector, default TLP — the foundation of tenant isolation. | Applications: inventory of the tested perimeter, linked to audits and vulnerabilities. |

| | |
|---|---|
| ![Organization card](docs/img/organisation-drawer.png) | ![Application card](docs/img/application-drawer.png) |
| Organization card: contact, default TLP and attachments (applications, audits, people). | Application card: criticality, environment and links to the perimeter's audits and vulnerabilities. |

![People](docs/img/ressources.png)

*People: team members and contacts, attached to organizations and selectable in
engagements.*

### Deliverables & traceability

![Deliverable generator](docs/img/deliverables.png)

*Deliverables: four types — engagement letters, NDAs, PTES reports and **Purple exercise
reports** (all runs of an audit: step timeline, verdicts, per-tactic coverage) —
generated as PDF (headless Chromium) from bilingual FR/EN templates with a **TLP
classification banner**, an evidence register with inline previews (secrets masked),
sealed in locked storage and traced in the journal.*

![Deliverable card](docs/img/deliverable-drawer.png)

*A produced deliverable's card: type, client, language, TLP marking and download —
every access is traced in the journal.*

![Evidence vault](docs/img/evidence.png)

*Evidence vault: upload via presigned URL (the API never sees the plaintext), ingestion
sandbox (antivirus, true file type, AES-256-GCM envelope encryption), **WORM** storage
and TLP marking. Decrypted download is the one documented exception: only the API can
unwrap the data key, so it streams the cleartext under inline access control (fresh
step-up for TLP:RED) with every access traced. Requires `make init-vault` before the
first deposits.*

![Tamper-evident journal](docs/img/journal.png)

*Journal: hash-chained, modifiable by no one (read is reserved to cross-cutting roles,
tenant-scoped for the rest) — server-side filters (text, event domain, result, actor,
date range), statistics, step-up-gated JSON export, and the "Verify chain integrity"
button recomputing the chain server-side. In the background the chain head is **anchored
every 6 h into WORM storage** to detect out-of-band tampering.*

### System

![Methodology library](docs/img/bibliotheque.png)

*Library: a corpus of 38 articles (procedures, processes, business articles) filterable
by profile — auditor, VOC, CTI, Purple Manager — with ISO 27002 cross-references and
exportable templates.*

![Library article — process](docs/img/bibliotheque-article.png)

*Reading a process ("The detection engineering loop"): step-by-step flow with decision
points, "key takeaways" box, relevant profiles and ISO 27002 reference (A.8.16) —
methodology right next to the tool.*

![Security reference catalogs](docs/img/parametres.png)

*Settings — reference catalogs: local ATT&CK / ATT&CK Groups / D3FEND / OWASP / CWE /
CAPEC / MISP Threat Actors catalog, synchronizable from online sources (falls back to
the embedded baseline when offline).*

![Administration](docs/img/admin.png)

*Administration (`admin` role): accounts, roles and each user's **client scope**
(fail-closed security: an empty scope means no access for non-manager roles), account
creation and deactivation.*

### Not pictured

- **⌘K command palette** — free-text navigation across views and methodology articles.
- **Deep links into a card** (`/audits?open=<id>`, `/exercices?open=<id>`) — a link from
  a vulnerability, an organization or a scenario opens the target card directly; the
  drawer is the only surface where an audit's or an exercise's content is displayed.
- **Per-view KPI bands** — every list view (audits, exercises, vulnerabilities,
  organizations, people, scenarios, journal) carries server-computed analytics that
  honor the same filters as the table.
- **Server-driven navigation** — menu entries only appear when the server grants read
  access to the underlying entity (`readable_entities` from `/whoami`).
- **Scenario cascades** — linking a CTI scenario to an audit auto-derives its PTES test
  actions; creating an exercise on such an audit seeds its attack chain.

## Security doctrine — defense in depth (4 layers)

No authorization is ever decided client-side: **the server decides, always**.
Binaries never transit through the API — with one documented exception: decrypted
evidence download, served by the API (sole holder of the data key) under inline access
control and full tracing. Four independent layers stack up, so that the failure of any
single one does not compromise the whole:

1. **Application `can()` engine** — a 5-gate evaluator (authentication, MFA/step-up,
   RBAC matrix, client tenancy, TLP/PAP) checked on every call, deny by default.
2. **PostgreSQL RLS** — *forced* Row-Level Security (`FORCE ROW LEVEL SECURITY`) on all
   tenant-scoped tables. The application role (`app_api`) is `NOBYPASSRLS`: even a query
   that escaped layer 1 only sees the clients within its scope. Without an established
   application context, **no row is visible**.
3. **Envelope encryption** — each evidence item is encrypted with a per-audit
   AES-256-GCM data key (DEK); the DEK is itself wrapped by a per-client master key
   (KEK) managed in Vault (*transit* engine). Destroying the KEK/DEK makes the data
   unrecoverable (*crypto-shredding*).
4. **WORM storage + tamper-evident journal** — encrypted objects are stored in MinIO
   with *Object Lock* (write-once-read-many); the audit journal is hash-chained
   (tamper-evident) and **immutable at the application level**: no role, not even
   `admin`, can modify or delete it. Its chain head is additionally **anchored into a
   WORM bucket every 6 hours** and re-verified daily, catching even a privileged
   database-level rewrite.

Authentication hardening on top: Redis rate limiting on `/login`, `/refresh` and
`/step-up`; TOTP anti-replay with secrets encrypted at rest (AES-256-GCM); single-use
OIDC/PKCE state; Swagger/OpenAPI disabled in production (`ENVIRONMENT=production`).

Deployment follows the **single entry point rule** (DAT §4.1bis): only the `frontend`
reverse proxy publishes ports; every other service communicates solely on internal
Docker networks. A CI check (`scripts/check_ports.py`) fails if any other service
exposes a port.

## Tech stack

| Layer       | Technology |
|-------------|------------|
| Backend/BFF | Python 3.11+ (validated on 3.12) · FastAPI · SQLAlchemy 2 (async) · Alembic |
| Tasks       | Celery + Redis (`ingest` / `jobs` queues) |
| Data        | PostgreSQL 15+ (validated on 16, forced RLS) |
| Secrets/KEK | HashiCorp Vault (transit engine) |
| Objects     | MinIO (S3, Object Lock COMPLIANCE) |
| Antivirus   | ClamAV (ingestion sandbox) |
| Identity    | Keycloak (OIDC + PKCE S256) — the IdP authenticates, the product authorizes |
| Frontend    | Vue 3 · Vite · Pinia · vue-i18n (FR/EN) — themes A (light) / B (dark SOC) |
| Deployment  | Docker Compose + Makefile |

## Quick start

Prerequisites: Docker, Docker Compose, Make.

```bash
cp .env.example .env          # `make up` then replaces every "change-me-*" value via
                              # `make secrets` (VAULT_TOKEN / OIDC_CLIENT_SECRET stay manual;
                              # set ENVIRONMENT=production for a production instance)
make bootstrap                # full first start: stack + schema + demo accounts
make init-vault               # (before storing evidence) unseal + transit + KEK
```

`make bootstrap` chains `up` (dev TLS certificate generated if needed), waiting for
PostgreSQL availability, `migrate` (Alembic schema) and `seed` (reference catalogs +
demo accounts). Idempotent: safe to re-run.

Manual equivalent, step by step:

```bash
make up                       # start the whole stack
make migrate                  # apply the schema (app_migrator role)
make seed                     # reference catalogs + demo organizations + accounts
make seed-demo                # (optional) rich demo dataset — audits, Purple exercises,
                              # vulnerabilities, tickets, scenarios (lights up every KPI)
```

`make seed-demo` is idempotent (deterministic UUIDs) and kept separate from `seed`, so a
production instance stays free of fictitious data. To start from a clean slate, `make
seed-demo-fresh` first purges every business row (including leftovers from test runs,
which share the demo database) while preserving reference catalogs, corpus, accounts,
the seed organizations and the journal, then re-seeds.

Access: `https://localhost/` (self-signed certificate in dev — accept the warning).
Demo accounts: `admin@purple.local`, `auditeur@purple.local`, `ciso@purple.local`,
`operateur@purple.local` (multi-client provider role, scoped to both demo clients).
The password is the value of `SEED_DEFAULT_PASSWORD` in `.env`; since MFA is not
enrolled on the demo accounts, **leave the TOTP field empty** at sign-in (enrollment
happens later via "My account").

Importing the demo dataset:

```bash
make import-maquette FILE=export.json
```

## Tests

```bash
make test            # full suite (unit + security)
make test-security   # blocking families: RLS isolation, RBAC matrix, ingestion sandbox,
                     # journal immutability, crypto-shredding, network exposure
```

The RLS isolation tests run against a real migrated PostgreSQL database
(`TEST_DATABASE_URL`) and prove, among other things, that a connection without context
sees no rows and that an out-of-scope write is rejected by the `WITH CHECK` clause.

## Structure

```
backend/            FastAPI API, Celery workers, migrations, tests
  app/
    security/       RBAC matrix, 5-gate can() engine, context, tokens, OIDC, MFA
    journal/        hash-chained journal (tamper-evident)
    storage/        envelope encryption, Vault, MinIO (WORM)
    models/         ORM (business + security + evidence)
    api/routes/     11 routers: auth, entities (generic CRUD), evidence, deliverables,
                    admin (users + journal), analytics, stix, reference, vulnerabilities,
                    exercises, profile ("my card")
    workers/        ingestion sandbox (antivirus, true type, encryption, WORM), jobs,
                    journal WORM anchoring
    deliverables/   HTML→PDF deliverable generation (4 types, FR/EN, TLP banners)
  sql/              roles.sql (PG roles) + schema_evidence.sql (evidence DDL + RLS)
  migrations/       Alembic (complete initial schema)
  scripts/          verify_journal.py, sync_reference.py (ops CLIs)
frontend/           Vue 3 + Vite (design tokens reused verbatim)
deploy/             nginx (single reverse proxy), keycloak (realm), vault
scripts/            check_ports.py, gen_secrets.sh, backup.sh, restore.sh
docs/               FR docs + docs/en/ mirrors (user guide, deployment, operations, Vault runbook), screenshots (img/)
```

## Architecture decisions (DAT)

D1 Python/FastAPI/SQLAlchemy async · D2 Vue 3 + reuse of design tokens ·
D3 Docker Compose (Kubernetes out of scope) · D4 role managed in the product (the IdP
only authenticates) · D5 global MFA for operational roles + step-up on high-risk
actions · D6 read-only Manager rights on People/Applications/Actions · D7 embedded
Keycloak (OIDC + PKCE) · D8 client-side over-encryption deferred.

## Documentation

Every document exists in English and French (cross-linked at the top of each file).

| Document (EN) | Version française | Purpose |
|---|---|---|
| [deployment.md](docs/en/deployment.md) | [deploiement.md](docs/deploiement.md) | Production deployment (secrets, install order, integrations, TLS, upgrades) |
| [operations.md](docs/en/operations.md) | [exploitation.md](docs/exploitation.md) | Day-2 operations (catalog sync, backup, journal verification, incident response, crypto-shredding) |
| [runbook-vault.md](docs/en/runbook-vault.md) | [runbook-vault.md](docs/runbook-vault.md) | Vault in detail (unsealing, KEK rotation, crypto-shredding) |
| [user-guide.md](docs/en/user-guide.md) | [guide-utilisateur.md](docs/guide-utilisateur.md) | Role-based onboarding and business journeys |
| [validation.md](docs/en/validation.md) | [validation.md](docs/validation.md) | Execution proof — test coverage |
| [ACCEPTANCE.md](docs/en/ACCEPTANCE.md) | [RECETTE.md](docs/RECETTE.md) | Acceptance testing and hardening |

## License

Internal project. See the terms of the service contract.
