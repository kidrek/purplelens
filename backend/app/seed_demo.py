"""Jeu de données de démonstration riche (make seed-demo).

Complète `seed.py` (qui ne crée que référentiels + comptes + organisations) avec un
jeu métier cohérent et réaliste : applications, ressources, audits multi-catégories,
deux exercices Purple multi-run montrant la détection qui progresse, vulnérabilités sur
toutes les sévérités/bandes SLA, tickets de détection issus des angles morts, scénarios
CTI et livrables. Objectif : faire vivre les KPIs du Cockpit et la matrice ATT&CK.

Choix d'implémentation (cf. plan) :
- Insertions SQL directes sous `service_session("admin_service")`, comme `import_maquette`.
- **UUID déterministes** (`uuid5`) + `ON CONFLICT (id) DO NOTHING` → idempotent, liens stables.
- Champs auto-dérivés côté serveur (nom/reference/period/seq/sla) **reproduits ici** en
  Python selon les formats de `app/api/service.py` (le seed n'appelle pas la couche service).
  Exceptions réutilisées telles quelles : `build_engagement_defaults` (bloc engagement),
  `suggest_d3fend` (contre-mesures) et `_derive_audit_actions_from_scenario` (actions PTES
  dérivées du scénario lié) — fonctions pures ou idempotentes, parité serveur garantie.
- Dates fixes (pas d'horloge) pour des références/period stables entre runs.
- Écart connu vs serveur : les `seq` sont figés pour la stabilité des captures et ne suivent
  pas toujours `_next_seq` (compteur par client+période) — cosmétique, assumé.
- Preuves (`evidence`/`audit_dek`/`evidence_access`) volontairement NON seedées : la chaîne
  nécessite Vault (KEK), ClamAV et MinIO Object Lock vivants ; se démontre en direct.

Usage :
    python -m app.seed_demo            # upsert du jeu de démo (idempotent)
    python -m app.seed_demo --purge    # purge préalable de TOUTES les données métier
                                       # (pollution de tests comprise), puis re-seed.
                                       # Préservés : référentiels ref_*, corpus, comptes,
                                       # organisations ACME/GLOBEX/PRESTA, journal
                                       # (append-only + ancres WORM : non purgeable).
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text

from app.api.engagement_defaults import build_engagement_defaults
from app.db.session import service_session
from app.reference.attack_d3fend import suggest_d3fend

# Espace de noms fixe pour dériver des UUID stables et reproductibles.
NS_DEMO = uuid.UUID("d3305eed-de70-4000-8000-a1b2c3d4e5f6")


def did(*parts: str) -> str:
    """UUID déterministe pour une entité de démo (idempotence + liens stables)."""
    return str(uuid.uuid5(NS_DEMO, ":".join(str(p) for p in parts)))


def period(d: date) -> str:
    return f"{d.year}{d.month:02d}"


def _uuid_arr(ids: list[str]) -> list[uuid.UUID]:
    """Liste d'UUID pour une colonne uuid[] (asyncpg encode nativement une liste)."""
    return [uuid.UUID(i) for i in ids]


# SLA dérivé du CVSS — reproduit app/api/service.py:_derive_sla.
def derive_sla(cvss: float | None, found: date) -> tuple[str | None, date | None]:
    if cvss is None:
        return None, None
    if cvss >= 9.0:
        return "P1", found + timedelta(days=7)
    if cvss >= 7.0:
        return "P2", found + timedelta(days=30)
    if cvss >= 4.0:
        return "P3", found + timedelta(days=90)
    return "P4", found + timedelta(days=180)


# ── Données de référence pour l'orchestration des exercices ───────────────────
# (ext_id ∈ socle ref_attack_technique, cf. reference/catalogs.py) → comptent dans la matrice.

# Exercice A (Portail Client) — 12 techniques, chaîne complète avec angles morts exfil.
TECH_A = [
    ("T1566.001", "Spearphishing Attachment"),
    ("T1190", "Exploit Public-Facing Application"),
    ("T1059.001", "PowerShell"),
    ("T1053", "Scheduled Task/Job"),
    ("T1547", "Boot or Logon Autostart Execution"),
    ("T1055", "Process Injection"),
    ("T1003", "OS Credential Dumping"),
    ("T1110", "Brute Force"),
    ("T1021", "Remote Services"),
    ("T1046", "Network Service Discovery"),
    ("T1041", "Exfiltration Over C2 Channel"),
    ("T1567", "Exfiltration Over Web Service"),
]
# Verdicts par run (alignés sur TECH_A) : ~20 % → ~40 % → ~60 % → ~75 %.
VERDICTS_A = [
    [
        "logged",
        "no_telemetry",
        "logged",
        "no_telemetry",
        "no_telemetry",
        "not_tested",
        "no_telemetry",
        "no_telemetry",
        "no_telemetry",
        "not_tested",
        "no_telemetry",
        "not_tested",
    ],
    [
        "alerted",
        "logged",
        "logged",
        "no_telemetry",
        "no_telemetry",
        "no_telemetry",
        "logged",
        "no_telemetry",
        "no_telemetry",
        "not_tested",
        "no_telemetry",
        "not_tested",
    ],
    [
        "prevented",
        "alerted",
        "alerted",
        "logged",
        "logged",
        "no_telemetry",
        "alerted",
        "no_telemetry",
        "logged",
        "not_tested",
        "no_telemetry",
        "no_telemetry",
    ],
    [
        "prevented",
        "prevented",
        "alerted",
        "alerted",
        "logged",
        "alerted",
        "alerted",
        "logged",
        "logged",
        "no_telemetry",
        "no_telemetry",
        "no_telemetry",
    ],
]
DATES_A = [date(2026, 3, 15), date(2026, 4, 15), date(2026, 5, 15), date(2026, 6, 15)]

# Exercice B (Passerelle Paiement) — 8 techniques exécution/persistence/impact.
TECH_B = [
    ("T1190", "Exploit Public-Facing Application"),
    ("T1059", "Command and Scripting Interpreter"),
    ("T1204", "User Execution"),
    ("T1543", "Create or Modify System Process"),
    ("T1136", "Create Account"),
    ("T1486", "Data Encrypted for Impact"),
    ("T1490", "Inhibit System Recovery"),
    ("T1567", "Exfiltration Over Web Service"),
]
VERDICTS_B = [
    ["alerted", "logged", "no_telemetry", "no_telemetry", "no_telemetry", "no_telemetry", "not_tested", "no_telemetry"],
    ["prevented", "alerted", "logged", "logged", "no_telemetry", "no_telemetry", "no_telemetry", "no_telemetry"],
    ["prevented", "alerted", "alerted", "logged", "logged", "no_telemetry", "no_telemetry", "no_telemetry"],
]
DATES_B = [date(2026, 4, 20), date(2026, 5, 20), date(2026, 6, 20)]

# Exercice GLOBEX — 8 techniques, 2 runs.
TECH_G = [
    ("T1566", "Phishing"),
    ("T1078", "Valid Accounts"),
    ("T1059", "Command and Scripting Interpreter"),
    ("T1548", "Abuse Elevation Control Mechanism"),
    ("T1087", "Account Discovery"),
    ("T1021", "Remote Services"),
    ("T1005", "Data from Local System"),
    ("T1041", "Exfiltration Over C2 Channel"),
]
VERDICTS_G = [
    ["logged", "no_telemetry", "logged", "no_telemetry", "no_telemetry", "not_tested", "no_telemetry", "not_tested"],
    ["alerted", "logged", "alerted", "logged", "no_telemetry", "logged", "no_telemetry", "no_telemetry"],
]
DATES_G = [date(2026, 5, 10), date(2026, 6, 10)]

_CAUGHT = {"prevented", "alerted", "logged"}


async def _org_info(session, code: str) -> tuple[str | None, str | None]:
    """(id, nom) de l'organisation — le nom alimente le bloc engagement/lettre."""
    row = (
        await session.execute(
            text("SELECT id, nom FROM organisation WHERE code = :c AND deleted_at IS NULL"), {"c": code}
        )
    ).first()
    return (str(row.id), row.nom) if row else (None, None)


async def _user_id(session, email: str) -> str | None:
    """id d'un compte seedé (résolu à l'exécution : les comptes n'ont pas d'UUID stable)."""
    row = (await session.execute(text("SELECT id FROM app_user WHERE email = :e"), {"e": email})).first()
    return str(row.id) if row else None


async def _ins(session, table: str, cols: dict, casts: dict | None = None) -> None:
    """Upsert idempotent (ON CONFLICT (id) DO UPDATE) : re-run rafraîchit les champs.
    `casts` : col → type SQL (jsonb/uuid[])."""
    casts = casts or {}
    names = ", ".join(cols)
    vals = ", ".join(f"CAST(:{c} AS {casts[c]})" if c in casts else f":{c}" for c in cols)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "id")
    await session.execute(
        text(f"INSERT INTO {table} ({names}) VALUES ({vals}) ON CONFLICT (id) DO UPDATE SET {updates}"), cols
    )


async def _seed_exercise(
    session, *, key, client_id, audit_id, app_code, client_code, techs, verdicts_per_run, dates, base_seq, equipe=None
):
    """Crée N runs (purple_exercise) + attack_steps ; renvoie les steps du dernier run.

    Les steps `alerted` reçoivent un `horodatage_detection` déterministe qui s'améliore de
    run en run (MTTD qui baisse), et — sur le dernier run — un `horodatage_reponse`
    (MTTR) : ce sont les entrées des tuiles KPI du drawer/de la vue exercice."""
    last_run_steps: list[dict] = []
    for run_idx, (verdicts, d) in enumerate(zip(verdicts_per_run, dates, strict=True), start=1):
        ex_id = did(key, "exo", run_idx)
        seq = base_seq + run_idx
        nom = f"PURPL_{period(d)}-{seq:02d}_{client_code}_{app_code}"
        await _ins(
            session,
            "purple_exercise",
            {
                "id": ex_id,
                "audit_id": audit_id,
                "client_id": client_id,
                "nom": nom,
                "period": period(d),
                "seq": seq,
                "date": d,
                "run_number": run_idx,
                "statut": "termine" if run_idx < len(dates) else "en_cours",
                "tlp": "AMBER",
                "equipe": json.dumps(equipe or []),
                "notes": f"Run {run_idx} — émulation adverse, boucle Red→Blue.",
            },
            casts={"equipe": "jsonb"},
        )
        for i, ((tech, tname), verdict) in enumerate(zip(techs, verdicts, strict=True)):
            step_id = did(key, "step", run_idx, tech)
            start = datetime(d.year, d.month, d.day, 9, i, tzinfo=UTC)
            detection = response = None
            if verdict == "alerted":
                # Détection : ~37-48 min au run 1 → ~13-24 min au run 4 (progression visible).
                detection = start + timedelta(minutes=max(5, 45 - run_idx * 8) + (i * 7) % 12)
                if run_idx == len(dates):
                    # Réaction mesurée sur le run courant uniquement (MTTR).
                    response = detection + timedelta(minutes=25 + (i * 13) % 65)
            await _ins(
                session,
                "attack_step",
                {
                    "id": step_id,
                    "exercise_id": ex_id,
                    "client_id": client_id,
                    "ordre": i,
                    "technique": tech,
                    "titre": tname,
                    "verdict": verdict,
                    "horodatage": start,
                    "horodatage_detection": detection,
                    "horodatage_reponse": response,
                },
            )
            if run_idx == len(dates):
                last_run_steps.append({"id": step_id, "tech": tech, "name": tname, "verdict": verdict})
    return last_run_steps


# Ordre de suppression validé contre le graphe de FK réel (toutes en NO ACTION) :
# feuilles → racines. Inconditionnel : c'est ce qui élimine aussi la pollution laissée
# par les tests (qui partagent la base de démo), y compris dans les tables non
# cloisonnées (scenario…) qu'une purge par client manquerait.
_PURGE_ORDER = [
    "audit_action",
    "audit_milestone",
    "defense_observation",
    "detection_ticket",
    "deliverable",
    "remediation_ticket",
    "vulnerability_enrichment",
    "attack_step",
    "purple_exercise",
    "vulnerability",
    "audit",
    "application",
    "ressource",
    "sla_rule",
    "scenario_step",
    "scenario",
]


async def purge_demo() -> None:
    """Remet la base métier à zéro avant re-seed (make seed-demo-fresh).

    Supprime TOUTES les données métier — jeu de démo et pollution de tests — mais
    préserve : les référentiels `ref_*`, le corpus, les comptes (`app_user`,
    `refresh_token`), les trois organisations du socle (ACME/GLOBEX/PRESTA — les
    `client_scope` des comptes pointent sur leurs ids, et `seed.py` ne les rafraîchit
    pas en re-run), et le `journal` (append-only par trigger pour tous les rôles ; sa
    tête de chaîne est ancrée dans un bucket WORM COMPLIANCE — le purger casserait
    définitivement `journal_anchor_verify`).

    Exécutée sous `admin_service` (scope global) : aucune connexion superuser requise.
    """
    async with service_session("admin_service") as session:
        # Garde-fou WORM : evidence / evidence_access / audit_dek portent des triggers
        # qui interdisent le DELETE physique. Vides aujourd'hui ; si des preuves réelles
        # existent, la purge s'arrête — leur cycle de vie passe par le crypto-shredding.
        worm = {}
        for t in ("evidence", "evidence_access", "audit_dek"):
            worm[t] = (await session.execute(text(f"SELECT count(*) FROM {t}"))).scalar()
        if any(worm.values()):
            print(
                "[seed-demo] ✋ purge refusée : des preuves existent "
                f"({worm}) — tables WORM non supprimables (DELETE interdit par trigger). "
                "Passer par la rétention/crypto-shredding avant de purger."
            )
            raise SystemExit(2)

        deleted = {}
        for t in _PURGE_ORDER:
            res = await session.execute(text(f"DELETE FROM {t}"))
            deleted[t] = res.rowcount
        res = await session.execute(
            text("DELETE FROM organisation WHERE code IS NULL OR code NOT IN ('ACME','GLOBEX','PRESTA')")
        )
        deleted["organisation"] = res.rowcount

    total = sum(deleted.values())
    detail = ", ".join(f"{t}:{n}" for t, n in deleted.items() if n)
    print(f"[seed-demo] purge : {total} ligne(s) supprimée(s) ({detail or 'rien à purger'}).")
    print(
        "[seed-demo] préservés : référentiels, corpus, comptes, organisations "
        "ACME/GLOBEX/PRESTA, journal (append-only + ancres WORM — non purgeable)."
    )


async def seed_demo() -> None:
    async with service_session("admin_service") as session:
        acme, acme_nom = await _org_info(session, "ACME")
        globex, globex_nom = await _org_info(session, "GLOBEX")
        if not acme or not globex:
            print("[seed-demo] Organisations ACME/GLOBEX absentes — lancez d'abord `make seed`.")
            return
        org_nom = {acme: acme_nom or "ACME", globex: globex_nom or "GLOBEX"}

        # ── Coordonnées des organisations (en-tête des lettres/NDA : siren, référent) ──
        presta, _ = await _org_info(session, "PRESTA")
        if presta:
            await session.execute(
                text(
                    "UPDATE organisation SET siren = :s, referent_interne = :r, "
                    "contacts = CAST(:c AS jsonb) WHERE id = :id"
                ),
                {
                    "id": presta,
                    "s": "912 345 678",
                    "r": "M. Vidal — Directeur des opérations offensives",
                    "c": json.dumps(["ops@presta-demo.example", "+33 1 99 00 12 34"]),
                },
            )
        for oid, contacts in (
            (acme, ["RSSI — j.durand@acme-demo.example", "Astreinte SOC — soc@acme-demo.example"]),
            (globex, ["RSSI — k.lopez@globex-demo.example"]),
        ):
            await session.execute(
                text("UPDATE organisation SET contacts = CAST(:c AS jsonb) WHERE id = :id"),
                {"id": oid, "c": json.dumps(contacts)},
            )

        # ── Applications (enrichies : stack, URL, version, contact, valeur métier) ──
        apps = {
            # code: (client, nom, criticite, exposition, type, valeur_metier, version, stack, url, contact)
            "PORTAIL": (
                acme,
                "Portail Client",
                "critique",
                "externe",
                "Application web",
                5,
                "4.2.1",
                "Vue 3 · FastAPI · PostgreSQL",
                "https://portail.acme-demo.example",
                "Produit — L. Fontaine",
            ),
            "SIRH": (
                acme,
                "SI RH",
                "haute",
                "interne",
                "Application web",
                4,
                "2.8.0",
                "Java Spring · Oracle",
                "https://rh.acme-demo.internal",
                "DRH — N. Aubry",
            ),
            "PAIE": (
                acme,
                "Passerelle Paiement",
                "critique",
                "externe",
                "API",
                5,
                "1.5.3",
                "Go · Redis · PCI-DSS",
                "https://pay.acme-demo.example",
                "Finance — R. Simon",
            ),
            "INTRA": (
                acme,
                "Intranet",
                "moyenne",
                "interne",
                "Application web",
                2,
                "3.0.0",
                "PHP · MySQL",
                "https://intranet.acme-demo.internal",
                "DSI — équipe socle",
            ),
            "GLXWEB": (
                globex,
                "Boutique en ligne",
                "critique",
                "externe",
                "Application web",
                5,
                "6.1.0",
                "Next.js · Node · Stripe",
                "https://shop.globex-demo.example",
                "E-commerce — T. Marchand",
            ),
            "GLXERP": (
                globex,
                "ERP Finance",
                "haute",
                "interne",
                "Progiciel",
                4,
                "12.4",
                "SAP · HANA",
                "https://erp.globex-demo.internal",
                "Finance — C. Petit",
            ),
        }
        app_id = {code: did("app", code) for code in apps}
        for code, (cid, nom, crit, expo, typ, vm, ver, stack, url, contact) in apps.items():
            await _ins(
                session,
                "application",
                {
                    "id": app_id[code],
                    "client_id": cid,
                    "nom": nom,
                    "code": code,
                    "criticite": crit,
                    "exposition": expo,
                    "type": typ,
                    "valeur_metier": vm,
                    "version": ver,
                    "stack": stack,
                    "url": url,
                    "contact_metier": contact,
                    "tags": json.dumps(["démo", expo]),
                    "statut": "actif",
                    "tlp": "AMBER",
                },
                casts={"tags": "jsonb"},
            )

        # ── Ressources (auditeurs humains → sélectionnables sur les audits) ────
        res = {
            "camille": (acme, "Camille Roy", "humaine", "auditeur", ["Pentest web", "Purple Team"]),
            "sami": (acme, "Sami Belkacem", "humaine", "auditeur", ["Red Team", "AD"]),
            "soc": (acme, "SOC N2", "humaine", "soc", ["SIEM", "Détection"]),
            "ciso": (acme, "Direction SSI", "humaine", "ciso", ["Gouvernance"]),
            "alex": (globex, "Alex Nguyen", "humaine", "auditeur", ["Pentest", "Cloud"]),
        }
        res_id = {k: did("res", k) for k in res}
        for k, (cid, nom, typ, role, comp) in res.items():
            await _ins(
                session,
                "ressource",
                {
                    "id": res_id[k],
                    "organisation_id": cid,
                    "nom": nom,
                    "type": typ,
                    "role": role,
                    "competences": json.dumps(comp),
                },
                casts={"competences": "jsonb"},
            )

        # ── Audits (6 ACME + 2 GLOBEX) ────────────────────────────────────────
        # (key, client, client_code, categorie, code_ref, type_test, app_code, statut, debut, prio, seq, auditeurs)
        audits = [
            (
                "aud-pen1",
                acme,
                "ACME",
                "pentest",
                "PEN",
                "black-box",
                "PORTAIL",
                "termine",
                date(2026, 2, 2),
                "P1",
                1,
                ["camille"],
            ),
            (
                "aud-red1",
                acme,
                "ACME",
                "red_team",
                "REDTEAM",
                "grey-box",
                "SIRH",
                "en_cours",
                date(2026, 5, 11),
                "P2",
                1,
                ["sami"],
            ),
            (
                "aud-bas1",
                acme,
                "ACME",
                "bas",
                "BAS",
                "grey-box",
                "INTRA",
                "termine",
                date(2026, 1, 15),
                "P3",
                1,
                ["camille"],
            ),
            # NB : `purple_team` est une catégorie héritée (plus proposée à la saisie) ;
            # les audits porteurs d'exercices Purple sont catégorisés red_team, comme dans l'UI.
            (
                "aud-pur1",
                acme,
                "ACME",
                "red_team",
                "REDTEAM",
                "grey-box",
                "PORTAIL",
                "en_cours",
                date(2026, 3, 3),
                "P2",
                1,
                ["camille", "soc"],
            ),
            (
                "aud-pur2",
                acme,
                "ACME",
                "red_team",
                "REDTEAM",
                "grey-box",
                "PAIE",
                "en_cours",
                date(2026, 4, 7),
                "P2",
                2,
                ["sami", "soc"],
            ),
            (
                "aud-pen2",
                acme,
                "ACME",
                "pentest",
                "PEN",
                "white-box",
                "PAIE",
                "planifie",
                date(2026, 7, 1),
                "P2",
                2,
                ["camille"],
            ),
            (
                "aud-glx-pen",
                globex,
                "GLOBEX",
                "pentest",
                "PEN",
                "black-box",
                "GLXWEB",
                "termine",
                date(2026, 3, 20),
                "P1",
                1,
                ["alex"],
            ),
            (
                "aud-glx-pur",
                globex,
                "GLOBEX",
                "red_team",
                "REDTEAM",
                "grey-box",
                "GLXWEB",
                "en_cours",
                date(2026, 5, 5),
                "P2",
                1,
                ["alex"],
            ),
        ]
        # Acteur émulé par audit (aligné sur le scénario CTI rattaché plus bas) —
        # enrichit les objectifs red_team du bloc engagement.
        acteur_for = {
            "aud-pur1": "FIN7",
            "aud-pur2": "APT28",
            "aud-pen1": "APT29",
            "aud-glx-pur": "Lazarus Group",
        }
        aud_id = {}
        for key, cid, ccode, cat, code_ref, ttest, ac, statut, debut, prio, seq, auds in audits:
            aid = did(key)
            aud_id[key] = aid
            nom = f"{code_ref}_{period(debut)}-{seq:02d}_{ccode}_{ac}"
            # Bloc engagement pré-rempli — même dérivation que la création via l'API
            # (`_seed_audit_engagement` → `build_engagement_defaults`, fonction pure).
            engagement = build_engagement_defaults(
                {
                    "categorie": cat,
                    "type_test": ttest,
                    "environnement": "production",
                    "date_debut": str(debut),
                },
                client_nom=org_nom[cid],
                app_names=[apps[ac][1]],
                acteur_emule=acteur_for.get(key),
            )
            await _ins(
                session,
                "audit",
                {
                    "id": aid,
                    "client_id": cid,
                    "nom": nom,
                    "categorie": cat,
                    "type_test": ttest,
                    "period": period(debut),
                    "seq": seq,
                    "statut": statut,
                    "priorite": prio,
                    "date_debut": debut,
                    "environnement": "production",
                    "tlp": "AMBER",
                    "applications": _uuid_arr([app_id[ac]]),
                    "auditeurs": _uuid_arr([res_id[a] for a in auds]),
                    "engagement": json.dumps(engagement),
                },
                casts={"applications": "uuid[]", "auditeurs": "uuid[]", "engagement": "jsonb"},
            )

        # ── Actions PTES sur l'audit pentest ACME (alimente TTP + « actions de test ») ──
        ptes_actions = [
            ("reconnaissance", "Cartographie de la surface exposée", "T1595", "info"),
            ("reconnaissance", "Énumération des comptes exposés", "T1087", "partiel"),
            ("reconnaissance", "Collecte d'informations techniques", "T1592", "info"),
            ("initial-access", "Hameçonnage ciblé (pièce jointe)", "T1566.001", "échec"),
            ("initial-access", "Exploitation de l'application exposée", "T1190", "succès"),
            ("initial-access", "Réutilisation d'identifiants valides", "T1078", "partiel"),
            ("exploitation", "Injection SQL sur le formulaire de connexion", "T1190", "succès"),
            ("exploitation", "Exécution de commande via désérialisation", "T1059", "succès"),
            ("exploitation", "Exécution PowerShell côté serveur", "T1059.001", "partiel"),
            ("post-exploitation", "Extraction de secrets applicatifs", "T1003", "partiel"),
            ("post-exploitation", "Injection de processus", "T1055", "échec"),
            ("post-exploitation", "Découverte du service réseau interne", "T1046", "succès"),
            ("post-exploitation", "Mouvement latéral vers le back-office", "T1021", "échec"),
            ("post-exploitation", "Collecte de données locales", "T1005", "partiel"),
            ("exploitation", "Persistance par tâche planifiée", "T1053", "succès"),
        ]
        for i, (phase, titre, tech, resultat) in enumerate(ptes_actions):
            await _ins(
                session,
                "audit_action",
                {
                    "id": did("action", "pen1", i),
                    "audit_id": aud_id["aud-pen1"],
                    "client_id": acme,
                    "ptes_phase": phase,
                    "titre": titre,
                    "technique_attack": tech,
                    "resultat": resultat,
                    "application_id": app_id["PORTAIL"],
                    "statut": "clos",
                },
            )

        # ── Jalons PTES de l'audit pentest (avancement du drawer) ─────────────
        pen1_milestones = [
            ("pre-engagement", "atteint", date(2026, 2, 2)),
            ("reconnaissance", "atteint", date(2026, 2, 6)),
            ("threat-modeling", "atteint", date(2026, 2, 9)),
            ("vulnerability-analysis", "en_cours", date(2026, 2, 13)),
            ("exploitation", "en_cours", date(2026, 2, 18)),
            ("reporting", "a_venir", date(2026, 2, 25)),
        ]
        for i, (phase, statut, dprev) in enumerate(pen1_milestones):
            await _ins(
                session,
                "audit_milestone",
                {
                    "id": did("milestone", "pen1", i),
                    "audit_id": aud_id["aud-pen1"],
                    "client_id": acme,
                    "ptes_phase": phase,
                    "statut": statut,
                    "date_prevue": dprev,
                    "date_reelle": dprev if statut == "atteint" else None,
                },
            )

        # ── Exercices Purple ──────────────────────────────────────────────────
        steps_a = await _seed_exercise(
            session,
            key="exA",
            client_id=acme,
            audit_id=aud_id["aud-pur1"],
            app_code="PORTAIL",
            client_code="ACME",
            techs=TECH_A,
            verdicts_per_run=VERDICTS_A,
            dates=DATES_A,
            base_seq=0,
            equipe=["Camille Roy (Red)", "SOC N2 (Blue)"],
        )
        steps_b = await _seed_exercise(
            session,
            key="exB",
            client_id=acme,
            audit_id=aud_id["aud-pur2"],
            app_code="PAIE",
            client_code="ACME",
            techs=TECH_B,
            verdicts_per_run=VERDICTS_B,
            dates=DATES_B,
            base_seq=10,
            equipe=["Sami Belkacem (Red)", "SOC N2 (Blue)"],
        )
        steps_g = await _seed_exercise(
            session,
            key="exG",
            client_id=globex,
            audit_id=aud_id["aud-glx-pur"],
            app_code="GLXWEB",
            client_code="GLOBEX",
            techs=TECH_G,
            verdicts_per_run=VERDICTS_G,
            dates=DATES_G,
            base_seq=0,
            equipe=["Alex Nguyen (Red)", "SOC Globex (Blue)"],
        )

        # ── Observations défensives (narratif de la timeline, sur steps détectés) ──
        for i, st in enumerate([s for s in steps_a if s["verdict"] in _CAUGHT][:4]):
            await _ins(
                session,
                "defense_observation",
                {
                    "id": did("obs", st["id"]),
                    "attack_step_id": st["id"],
                    "client_id": acme,
                    "source": "EDR" if i % 2 else "SIEM",
                    "resultat": st["verdict"],
                    "description": f"Détection de « {st['name']} » ({st['tech']}) corrélée par la Blue Team.",
                },
            )

        # ── Tickets de détection (issus des angles morts du dernier run) ───────
        d3fend_for = {"T1041": ["D3-NTA"], "T1567": ["D3-NTA"], "T1046": ["D3-NTA"], "T1486": ["D3-FA"]}
        sigma_nta = (
            "title: Exfiltration inhabituelle vers un domaine externe\n"
            "logsource:\n  category: proxy\n"
            "detection:\n  selection:\n    c-uri-extension: ['zip','7z','enc']\n"
            "  condition: selection\nlevel: high\n"
        )
        blind_a = [s for s in steps_a if s["verdict"] == "no_telemetry"]
        blind_b = [s for s in steps_b if s["verdict"] == "no_telemetry"]
        ticket_src = blind_a[:3] + blind_b[:1]
        # Cycle de vie complet : ouvert → en_cours → traite → clos. Le ticket clos est
        # validé (valide_par/valide_le) : il alimente le KPI « délai de remédiation » et
        # fait passer son step source à l'état « couvert » dans le drawer d'exercice.
        ticket_statut = {1: "ouvert", 2: "en_cours", 3: "traite", 4: "clos"}
        validateur = await _user_id(session, "ciso@purple.local")
        for i, st in enumerate(ticket_src, start=1):
            tech = st["tech"]
            statut = ticket_statut[i]
            ref = f"TICK_202606-{i:02d}_ACME_{'PORTAIL' if st in blind_a else 'PAIE'}_{tech}"
            await _ins(
                session,
                "detection_ticket",
                {
                    "id": did("ticket", st["id"]),
                    "client_id": acme,
                    "reference": ref,
                    "period": "202606",
                    "seq": i,
                    "source_attack_step_id": st["id"],
                    "technique_attack": tech,
                    "mesure_d3fend": json.dumps(d3fend_for.get(tech, ["D3-NTA"])),
                    "description": f"Angle mort : aucune télémétrie sur « {st['name']} » ({tech}). "
                    f"Déployer la mesure D3FEND associée sur le segment concerné.",
                    "priorite": "P1" if i == 1 else "P2",
                    "statut": statut,
                    "regle_sigma": sigma_nta if tech in ("T1041", "T1567") else None,
                    "gap_decouvert_le": datetime(2026, 6, 15, 10, tzinfo=UTC),
                    "valide_par": validateur if statut == "clos" else None,
                    "valide_le": datetime(2026, 6, 24, 10, tzinfo=UTC) if statut == "clos" else None,
                },
                casts={"mesure_d3fend": "jsonb"},
            )

        # Ticket GLOBEX (angle mort du dernier run de l'exercice Boutique en ligne) —
        # chaque client a ses tickets ; seq par client+période, convention serveur.
        blind_g = [s for s in steps_g if s["verdict"] == "no_telemetry"]
        if blind_g:
            st = next((s for s in blind_g if s["tech"] == "T1005"), blind_g[0])
            await _ins(
                session,
                "detection_ticket",
                {
                    "id": did("ticket", st["id"]),
                    "client_id": globex,
                    "reference": f"TICK_202606-01_GLOBEX_GLXWEB_{st['tech']}",
                    "period": "202606",
                    "seq": 1,
                    "source_attack_step_id": st["id"],
                    "technique_attack": st["tech"],
                    "mesure_d3fend": json.dumps(d3fend_for.get(st["tech"], ["D3-NTA"])),
                    "description": f"Angle mort : aucune télémétrie sur « {st['name']} » ({st['tech']}). "
                    f"Déployer la mesure D3FEND associée sur le segment concerné.",
                    "priorite": "P2",
                    "statut": "ouvert",
                    "regle_sigma": None,
                    "gap_decouvert_le": datetime(2026, 6, 10, 11, tzinfo=UTC),
                    "valide_par": None,
                    "valide_le": None,
                },
                casts={"mesure_d3fend": "jsonb"},
            )

        # ── Vulnérabilités ─────────────────────────────────────────────────────
        # (key, client, ccode, app, severite, cvss, statut, owasp, cwe, cve, found, techniques, exploit)
        vulns = [
            (
                "v-acme-1",
                acme,
                "ACME",
                "PORTAIL",
                "critique",
                9.8,
                "ouverte",
                "A03:2021",
                "CWE-89",
                "CVE-2026-1001",
                date(2026, 6, 20),
                ["T1190"],
                "exploite",
            ),
            (
                "v-acme-2",
                acme,
                "ACME",
                "PAIE",
                "critique",
                9.1,
                "corrigee",
                "A02:2021",
                "CWE-327",
                "CVE-2026-1002",
                date(2026, 2, 10),
                ["T1078"],
                "poc",
            ),
            (
                "v-acme-3",
                acme,
                "ACME",
                "PORTAIL",
                "haute",
                8.2,
                "ouverte",
                "A01:2021",
                "CWE-284",
                None,
                date(2026, 6, 25),
                ["T1078"],
                "poc",
            ),
            (
                "v-acme-4",
                acme,
                "ACME",
                "SIRH",
                "haute",
                7.4,
                "en_cours",
                "A05:2021",
                "CWE-16",
                "CVE-2026-1044",
                date(2026, 5, 30),
                ["T1190"],
                "theorique",
            ),
            (
                "v-acme-5",
                acme,
                "ACME",
                "INTRA",
                "moyenne",
                6.1,
                "ouverte",
                "A07:2021",
                "CWE-352",
                None,
                date(2026, 6, 1),
                [],
                "theorique",
            ),
            (
                "v-acme-6",
                acme,
                "ACME",
                "PORTAIL",
                "moyenne",
                5.3,
                "acceptee",
                "A06:2021",
                "CWE-1104",
                None,
                date(2026, 4, 1),
                [],
                "theorique",
            ),
            (
                "v-acme-7",
                acme,
                "ACME",
                "SIRH",
                "basse",
                3.1,
                "ouverte",
                "A09:2021",
                "CWE-778",
                None,
                date(2026, 6, 5),
                [],
                "theorique",
            ),
            (
                "v-acme-8",
                acme,
                "ACME",
                "PAIE",
                "haute",
                8.8,
                "ouverte",
                "A03:2021",
                "CWE-89",
                "CVE-2026-1088",
                date(2026, 6, 28),
                ["T1190"],
                "poc",
            ),
            (
                "v-glx-1",
                globex,
                "GLOBEX",
                "GLXWEB",
                "critique",
                9.5,
                "ouverte",
                "A03:2021",
                "CWE-78",
                "CVE-2026-2001",
                date(2026, 6, 22),
                ["T1190"],
                "exploite",
            ),
            (
                "v-glx-2",
                globex,
                "GLOBEX",
                "GLXERP",
                "haute",
                7.9,
                "ouverte",
                "A01:2021",
                "CWE-862",
                None,
                date(2026, 6, 10),
                ["T1078"],
                "poc",
            ),
            (
                "v-glx-3",
                globex,
                "GLOBEX",
                "GLXWEB",
                "moyenne",
                5.0,
                "corrigee",
                "A05:2021",
                "CWE-693",
                None,
                date(2026, 3, 15),
                [],
                "theorique",
            ),
            (
                "v-glx-4",
                globex,
                "GLOBEX",
                "GLXWEB",
                "basse",
                2.5,
                "ouverte",
                "A09:2021",
                "CWE-532",
                None,
                date(2026, 6, 12),
                [],
                "theorique",
            ),
            # Ajoutée en fin de liste (les seq des entrées précédentes restent stables).
            (
                "v-acme-9",
                acme,
                "ACME",
                "INTRA",
                "basse",
                3.5,
                "faux_positif",
                "A09:2021",
                "CWE-209",
                None,
                date(2026, 6, 18),
                [],
                "theorique",
            ),
        ]
        aud_for_app = {
            "PORTAIL": "aud-pen1",
            "PAIE": "aud-pur2",
            "SIRH": "aud-red1",
            "INTRA": "aud-bas1",
            "GLXWEB": "aud-glx-pen",
            "GLXERP": "aud-glx-pur",
        }
        for i, (key, cid, ccode, ac, sev, cvss, statut, owasp, cwe, cve, found, techs, exploit) in enumerate(
            vulns, start=1
        ):
            vid = did(key)
            sla_n, sla_e = derive_sla(cvss, found)
            titre = f"VULN_{period(found)}-{i:02d}_{ccode}_{ac}"
            await _ins(
                session,
                "vulnerability",
                {
                    "id": vid,
                    "client_id": cid,
                    "audit_id": aud_id[aud_for_app[ac]],
                    "titre": titre,
                    "period": period(found),
                    "seq": i,
                    "cve": cve,
                    "cwe": cwe,
                    "severite": sev,
                    "cvss_score": cvss,
                    "statut": statut,
                    "owasp_top10": owasp,
                    "exploitabilite": exploit,
                    "phase_decouverte": "exploitation",
                    "description": f"Vulnérabilité {sev} identifiée sur {apps[ac][1]}.",
                    "recommandation": "Corriger selon la recommandation OWASP correspondante et re-tester.",
                    "applications": _uuid_arr([app_id[ac]]),
                    "techniques": json.dumps(techs),
                    # Contre-mesures dérivées des techniques — même calcul que le serveur
                    # (`_apply_d3fend_auto` → `suggest_d3fend`).
                    "d3fend": json.dumps(suggest_d3fend(techs)),
                    "sla_niveau": sla_n,
                    "sla_echeance": sla_e,
                    "decouvreur_id": res_id["camille"] if cid == acme else res_id["alex"],
                    "tlp": "RED",
                },
                casts={"applications": "uuid[]", "techniques": "jsonb", "d3fend": "jsonb"},
            )

        # Enrichissement VOC (CIRCL) sur la critique ACME.
        await _ins(
            session,
            "vulnerability_enrichment",
            {
                "id": did("enr", "v-acme-1"),
                "vulnerability_id": did("v-acme-1"),
                "client_id": acme,
                "epss_score": 0.94210,
                "epss_percentile": 0.99120,
                "epss_date": date(2026, 6, 25),
                "kev": True,
                "kev_ransomware": True,
                "kev_date_added": date(2026, 6, 23),
                "kev_due_date": date(2026, 7, 4),
                "ssvc_decision": "Act",
                "vex_status": "affected",
                "enrichment_status": "enrichi",
                "enrichment_source": "CIRCL",
                "enriched_at": datetime(2026, 6, 25, 8, 30, tzinfo=UTC),
                # Cache brut CIRCL (même forme que routes/vulnerabilities.py) — alimente le
                # bloc CAPEC/références/CPE du drawer VOC.
                "raw": json.dumps(
                    {
                        "cvss_version": "3.1",
                        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                        "capec": ["CAPEC-66"],
                        "references": ["https://vulnerability.circl.lu/vuln/CVE-2026-1001"],
                        "products": ["acme:portail-client"],
                        "cpes": ["cpe:2.3:a:acme:portail_client:4.2.1:*:*:*:*:*:*:*"],
                    }
                ),
            },
            casts={"raw": "jsonb"},
        )

        # ── Scénarios CTI (globaux) + étapes ──────────────────────────────────
        scenarios = [
            (
                "sc-fin7",
                "Émulation FIN7",
                "FIN7",
                "purple-team",
                "apt",
                2,
                "AMBER",
                [
                    ("T1566", "initial-access"),
                    ("T1204", "execution"),
                    ("T1059", "execution"),
                    ("T1053", "execution"),
                    ("T1547", "persistence"),
                    ("T1005", "collection"),
                    ("T1105", "command-and-control"),
                ],
            ),
            (
                "sc-apt29",
                "Émulation APT29",
                "APT29",
                "red-team",
                "apt",
                1,
                "AMBER",
                [
                    ("T1566.001", "initial-access"),
                    ("T1078", "initial-access"),
                    ("T1059.001", "execution"),
                    ("T1027", "defense-evasion"),
                    ("T1071.001", "command-and-control"),
                    ("T1003", "credential-access"),
                ],
            ),
            (
                "sc-apt28",
                "Émulation APT28",
                "APT28",
                "red-team",
                "avancee",
                2,
                "AMBER",
                [
                    ("T1595", "reconnaissance"),
                    ("T1566", "initial-access"),
                    ("T1110", "credential-access"),
                    ("T1003", "credential-access"),
                    ("T1041", "exfiltration"),
                ],
            ),
            (
                "sc-lazarus",
                "Émulation Lazarus",
                "Lazarus Group",
                "assumed-breach",
                "apt",
                2,
                "AMBER",
                [
                    ("T1566", "initial-access"),
                    ("T1059", "execution"),
                    ("T1105", "command-and-control"),
                    ("T1486", "impact"),
                ],
            ),
            (
                "sc-ransomware",
                "Scénario rançongiciel générique",
                "Big Game Hunting",
                "tabletop",
                "intermediaire",
                3,
                "GREEN",
                [
                    ("T1190", "initial-access"),
                    ("T1055", "privilege-escalation"),
                    ("T1021", "lateral-movement"),
                    ("T1490", "impact"),
                    ("T1486", "impact"),
                ],
            ),
        ]
        for i, (key, nom, acteur, engagement, sophist, cred, tlp, steps) in enumerate(scenarios, start=1):
            sid = did(key)
            ref = f"SCEN_202601-{i:02d}"
            await _ins(
                session,
                "scenario",
                {
                    "id": sid,
                    "nom": nom,
                    "reference": ref,
                    "period": "202601",
                    "seq": i,
                    "acteur_emule": acteur,
                    "type_engagement": engagement,
                    "sophistication": sophist,
                    "credibilite": cred,
                    "tlp": tlp,
                    "pap": "AMBER",
                    "objectif": f"Reproduire le mode opératoire de {acteur} pour éprouver la détection.",
                    "techniques": json.dumps([t for t, _ in steps]),
                    "d3fend": json.dumps(suggest_d3fend([t for t, _ in steps])),
                },
                casts={"techniques": "jsonb", "d3fend": "jsonb"},
            )
            for j, (tech, tactique) in enumerate(steps):
                await _ins(
                    session,
                    "scenario_step",
                    {
                        "id": did(key, "step", j),
                        "scenario_id": sid,
                        "ordre": j,
                        "technique": tech,
                        "tactique": tactique,
                        "description": f"Étape {j + 1} — {tech} ({tactique}).",
                    },
                )

        # Rattacher les audits Purple/pentest à un scénario CTI émulé (drawer d'audit enrichi),
        # puis dériver les actions PTES comme le ferait la création via l'API : une action par
        # étape du scénario, dédoublonnée par technique (les 15 actions manuscrites de aud-pen1
        # sont conservées ; idempotent entre re-runs). NB : les chaînes d'attaque des exercices
        # divergent volontairement du scénario lié — elles racontent la progression multi-run.
        from app.api.service import _derive_audit_actions_from_scenario

        for aud_key, sc_key in [
            ("aud-pur1", "sc-fin7"),
            ("aud-pur2", "sc-apt28"),
            ("aud-pen1", "sc-apt29"),
            ("aud-glx-pur", "sc-lazarus"),
        ]:
            await session.execute(
                text("UPDATE audit SET scenario_id = :sid WHERE id = :aid"),
                {"sid": did(sc_key), "aid": aud_id[aud_key]},
            )
            await _derive_audit_actions_from_scenario(
                session,
                audit_id=aud_id[aud_key],
                client_id=globex if aud_key.startswith("aud-glx") else acme,
                scenario_id=did(sc_key),
            )

        # ── Livrables ─────────────────────────────────────────────────────────
        # Statut « brouillon » (état honnête : aucun PDF n'est généré par le seed —
        # `GET /{id}/download` exige statut=genere + storage_key). En démo, cliquer
        # « Générer » produit un vrai PDF via le pipeline complet (pdf-renderer + WORM).
        deliverables = [
            ("dl-eng", acme, "aud-pen1", "engagement", "Lettre d'engagement — Pentest Portail Client", "fr"),
            ("dl-nda", acme, "aud-pen1", "nda", "Accord de confidentialité — ACME", "fr"),
            ("dl-rap", acme, "aud-pen1", "rapport", "Rapport PTES — Pentest Portail Client", "fr"),
            ("dl-glx", globex, "aud-glx-pen", "rapport", "Rapport PTES — Boutique en ligne", "fr"),
            ("dl-exo", acme, "aud-pur1", "exercice", "Rapport d'exercice Purple — Portail Client", "fr"),
        ]
        for key, cid, aud_key, typ, titre, langue in deliverables:
            await _ins(
                session,
                "deliverable",
                {
                    "id": did(key),
                    "client_id": cid,
                    "audit_id": aud_id[aud_key],
                    "type": typ,
                    "titre": titre,
                    "langue": langue,
                    "tlp": "AMBER",
                    "statut": "brouillon",
                },
            )

        # ── « Ma fiche » : lier les fiches ressources aux comptes de démonstration ──
        # (ressource.app_user_id, migration 0017). Garde-fou : l'index unique
        # uq_ressource_user_org interdit deux fiches liées au même (compte, organisation) —
        # on ne lie pas si une autre fiche occupe déjà la paire (fiche créée via /profile).
        for res_key, email in (
            ("camille", "auditeur@purple.local"),
            ("ciso", "ciso@purple.local"),
            ("alex", "operateur@purple.local"),
        ):
            uid = await _user_id(session, email)
            if not uid:
                continue
            await session.execute(
                text(
                    "UPDATE ressource r SET app_user_id = :u WHERE r.id = :rid "
                    "AND NOT EXISTS (SELECT 1 FROM ressource o WHERE o.app_user_id = :u "
                    "AND o.organisation_id = r.organisation_id AND o.id <> r.id)"
                ),
                {"u": uid, "rid": res_id[res_key]},
            )

    print(
        "[seed-demo] terminé : 2 clients enrichis, 8 audits (engagement pré-rempli, actions "
        "PTES dérivées des scénarios), 3 exercices Purple (9 runs, MTTD/MTTR), 13 vulnérabilités, "
        "5 tickets (cycle complet), 5 scénarios CTI, 5 livrables (brouillons). Idempotent."
    )


async def main() -> None:
    if "--purge" in sys.argv[1:]:
        await purge_demo()
    await seed_demo()


if __name__ == "__main__":
    asyncio.run(main())
