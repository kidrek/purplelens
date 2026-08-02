# User Guide — Purple Team Cockpit

🇫🇷 [Version française](../guide-utilisateur.md)

This guide walks through the main journeys by role. The interface is bilingual (FR/EN,
toggle in the top bar) and offers two themes matching the artistic direction: **A**
(light, violet) and **B** (dark SOC) — toggle next to the language. On the right of the
top bar, an **account chip** shows your name (with an **MFA** badge until two-factor
authentication is enrolled); clicking it opens "My account".

## Signing in

Two modes coexist:

- **SSO (recommended)**: "Sign in via your organization" redirects to the identity
  provider (Keycloak, OIDC + PKCE). After authentication, the product determines your
  role and scope — the identity does not carry the role.
- **Local fallback**: e-mail + password + TOTP code, for service accounts or emergency
  situations.

Operational roles require MFA. Some sensitive actions demand a **recent
re-authentication** (step-up): the interface then prompts you for a fresh TOTP code.

**Session continuity**: while you are working, your session is **silently renewed** —
you are not logged out every few minutes. A new authentication is only required after
**prolonged inactivity** or if the session is revoked (account deactivated, key
rotation).

## Roles

| Role       | Main purpose |
|------------|--------------|
| `admin`    | Administration, account management, broad CRUD (journal is **read-only**, never the encryption keys) |
| `manager`  | Steering and validation; read-only on People/Applications/Actions (D6) |
| `ciso`     | Validation of vulnerabilities and tickets, visibility over their scope |
| `auditeur` | Running audits, depositing evidence |
| `voc`      | Vulnerability management (Vulnerability Operations) |
| `cert`     | Detection: observations, detection tickets, scenarios |
| `operateur`| Multi-client provider "business super-user": full CRUD on inventory, scenarios and deliverables, validation of their audits/vulnerabilities/tickets — strictly confined to their client list |

What you can see and do is **decided by the server**. A missing or greyed-out button
reflects a right that was not granted: the interface mirrors the decision, it neither
invents nor bypasses it. The **side menu itself adapts**: entries the server does not
grant you read access to (for instance the Journal for non-cross-cutting roles) simply
do not appear.

**Navigation tip**: the **command palette** (⌘K / Ctrl-K) gives free-text access to the
views and to the methodology library articles.

## Cockpit

Home screen: detection rate, blind spots, P1 SLA breaches, posture per tactic
(kill-chain band), trend, latest events — limited to your scope. Multi-client roles see
the aggregate of their clients; the **scope selector** in the top bar narrows the
display (it never widens it). Most list views also carry their own **KPI band**,
computed server-side with the same filters as the table.

## Business journeys

- **Organizations**: clients and providers, sector (**NACE Rev. 2** taxonomy),
  internal contact, default TLP.
- **Applications**: application inventory (criticality, exposure, business value) with
  consolidated posture — linked vulnerabilities, audit coverage; an application's side
  panel is a dedicated mini-cockpit.
- **People**: team members and contacts (auditor/SOC/CISO… role, skills) — selectable as
  auditors on audits.
- **Audits**: engagements (auto reference `TYPE_YYYYMM-NN_CLIENT_APP`, e.g.
  `PEN_202602-01_ACME_PORTAIL`), category, test type, PTES milestones, status,
  priority. The **engagement block** (objectives, scope, rules, contacts, NDA clauses —
  18 sections) is **pre-filled at creation** and feeds the engagement letter. Linking a
  **CTI scenario** to the audit **automatically derives the PTES test actions** (one
  action per scenario step, deduplicated by technique).
- **Purple exercises**: emulation sessions attached to an audit, teams, successive
  *runs*, per-attack-step verdicts (prevented / alerted / logged / no telemetry / not
  tested), detection (MTTD) and response (MTTR) delays computed from the recorded
  timestamps. The list groups runs by audit; the exercise panel shows detection
  progressing run over run, and its step editor puts the attack chain and the defensive
  observations side by side.
- **Vulnerabilities**: CVE/CWE, CVSS score, SLA level and deadline computed
  automatically, **D3FEND countermeasures derived from the ATT&CK techniques**,
  validation by the CISO/Manager; on-demand CIRCL enrichment (EPSS, KEV, SSVC).
- **Detection tickets**: born from an exercise's **blind spots** (a step with no
  telemetry) — a ticket can only be created from a source attack step; auto reference
  `TICK_YYYYMM-NN_CLIENT_APP_TECHNIQUE`, associated D3FEND measure, optional Sigma
  rule, lifecycle open → in progress → handled → closed with validation. A closed
  ticket moves the corresponding technique to the "covered" state.
- **Scenarios**: cross-cutting threat library (emulated actors, ATT&CK techniques,
  Admiralty-scale credibility, STIX 2.1 import/export) — shared, outside client
  isolation. The "emulated actor" field builds on the **actor catalogs** (ATT&CK
  Groups + MISP Galaxy): pick an actor, then **import their TTPs** as scenario steps.

## ATT&CK matrix

The **ATT&CK matrix** page shows coverage as a table: **tactics** as columns (with a
*covered / total* counter), **techniques** as cards tinted by their **coverage status**.
A **layer** selector changes what the colors mean:

- **Coverage**: nature of the coverage / best defensive verdict;
- **Detection**: technique detected (defensive response) vs **gap** (played, not
  detected);
- **Gap**: highlights detection gaps only;
- **Imported**: highlights the techniques of an imported **ATT&CK Navigator** layer
  (`.json`).

Each card can carry **activity badges** (offensive steps, vulnerabilities, tickets,
linked scenarios) and **expands** to show its sub-techniques.

![ATT&CK matrix — coverage per tactic](../img/attack-matrix.png)

## Evidence (vault)

The vault shows the evidence within your scope with its **sealing state** and **TLP**
marking. Key points:

- The **upload** never transits through the application: it uses a **short-lived
  presigned URL**, issued by the server after a triple check (rights, tenant isolation,
  TLP/PAP). The **decrypted download** is the one documented exception: only the
  servers hold the key, so the cleartext file is served by the API, under reinforced
  access control (a fresh step-up is required for TLP:RED) and systematic tracing —
  evidence marked as containing "secrets" is never served in the clear.
- A deposited file goes through a **sandbox**: quarantine, antivirus scan, true file
  type verification, envelope encryption, WORM storage, then sealing into the journal.
  The progress bar reflects these stages.
- Download is only possible once the evidence is **stored** (sandbox passed).
- Every access — **including denials** — is traced. You will never see the content of
  an item whose marking is incompatible with your context.

## Journal

Reserved for cross-cutting roles (`admin`, `manager`, `ciso`), **read-only** — nobody
can modify it, not even the administrator; scoped roles only see the events of their
own tenant. The view offers **server-side filters** (free text, event domain, ok/denied
result, actor, date range), a **statistics** panel, and a **JSON export** (step-up
required). The "Verify chain integrity" button asks the server to recompute the hash
chain and flags any break; in the background, the chain head is additionally **anchored
into WORM storage** every 6 hours.

## Deliverables

Four types are generated as PDF: **engagement letter**, **NDA**, **PTES report** and
**Purple exercise report** (all runs of an audit: step timeline, verdicts, per-tactic
coverage). Bilingual FR/EN templates, **TLP classification banner**, evidence register
with inline previews, deposit into locked storage. Items marked as secrets are masked
in the renderings.

## Library

Bilingual methodology corpus (procedures, processes, business articles), filterable by
profile, reachable from the **Library** menu or via the ⌘K palette. Articles open in a
side panel anywhere in the application (deep links `?open=`).

## Settings

Status of the **reference catalogs** (multi-domain ATT&CK Enterprise/Mobile/ICS,
D3FEND, OWASP, CWE, CAPEC, ATT&CK groups, MISP actors) with offline import and
**online synchronization** ("Sync all", administrators only).

## Administration

Account management (creation, role change, deactivation) — every action is
**high-risk**: a step-up TOTP code is requested on the fly. Roles and their rights are
frozen in the server-side matrix, never configurable at runtime.

## My account — "My card"

The **My account** page lets you enroll MFA (TOTP) and maintain your **auditor card**
("Ma fiche"): a person card linked to your account, per organization of your scope.
Once created, you become selectable as an auditor on an audit — without waiting for a
manager to create the card for you.

## Good practices

- Renew your TOTP code whenever the interface asks (step-up): it signals a high-impact
  action.
- Respect the TLP/PAP marking: it drives dissemination and rendering.
- An unexpected denial is a server decision: contact your administrator if you believe
  a right is missing.
