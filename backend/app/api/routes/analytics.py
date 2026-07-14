"""Analytique — matrice de couverture ATT&CK.

Vue transverse en lecture seule : pour chaque technique ATT&CK, on agrège ce que
l'activité Purple du périmètre courant a touché (étapes d'attaque exécutées + leur
verdict défensif, vulnérabilités, tickets de détection, actions d'audit) et ce que la
bibliothèque de scénarios couvre. Le cloisonnement est assuré par la RLS : les tables
métier sont filtrées au périmètre client du rôle ; le référentiel et les scénarios sont
globaux (CTI transverse).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import rls_session
from app.security.context import SecurityContext
from app.security.matrix import Action
from app.security.rbac import require

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Ordre canonique des tactiques (ATT&CK Enterprise) pour l'affichage en colonnes.
_TACTIC_ORDER = [
    "reconnaissance", "resource-development", "initial-access", "execution",
    "persistence", "privilege-escalation", "defense-evasion", "credential-access",
    "discovery", "lateral-movement", "collection", "command-and-control",
    "exfiltration", "impact",
]

# Meilleur verdict défensif observé (du plus favorable au moins favorable).
_VERDICT_RANK = ["prevented", "alerted", "logged", "no_telemetry", "not_tested"]


async def compute_attack_matrix(s: AsyncSession) -> dict:
    """Agrège la couverture ATT&CK sur la session fournie.

    Le cloisonnement RLS, s'il s'applique, est déjà porté par la session (contexte
    posé en amont). Fonction pure d'agrégation → testable directement.
    """
    ref = (await s.execute(text(
        "SELECT ext_id, name, tactic, "
        "COALESCE((SELECT array_agg(x) FROM jsonb_array_elements_text(data->'tactics') x), "
        "ARRAY[]::text[]) AS tactics "
        "FROM ref_attack_technique"
    ))).all()
    steps = (await s.execute(text(
        "SELECT technique, verdict, count(*) c FROM attack_step "
        "WHERE technique IS NOT NULL GROUP BY technique, verdict"
    ))).all()
    vulns = (await s.execute(text(
        "SELECT t AS technique, count(*) c FROM vulnerability v, "
        "jsonb_array_elements_text(v.techniques) t WHERE v.deleted_at IS NULL GROUP BY t"
    ))).all()
    tickets = (await s.execute(text(
        "SELECT technique_attack technique, count(*) c FROM detection_ticket "
        "WHERE technique_attack IS NOT NULL AND deleted_at IS NULL GROUP BY technique_attack"
    ))).all()
    actions = (await s.execute(text(
        "SELECT technique_attack technique, count(*) c FROM audit_action "
        "WHERE technique_attack IS NOT NULL AND deleted_at IS NULL GROUP BY technique_attack"
    ))).all()
    scenarios = (await s.execute(text(
        "SELECT t AS technique, count(*) c FROM scenario sc, "
        "jsonb_array_elements_text(sc.techniques) t WHERE sc.deleted_at IS NULL GROUP BY t"
    ))).all()

    tech: dict[str, dict] = {}

    def _entry(code: str) -> dict:
        return tech.setdefault(code, {
            "ext_id": code, "name": None, "tactic": None, "tactics": [],
            "steps": 0, "vulns": 0, "tickets": 0, "actions": 0, "scenarios": 0,
            "verdicts": {}, "best_verdict": None,
        })

    for r in ref:
        e = _entry(r.ext_id)
        e["name"] = r.name
        e["tactic"] = r.tactic
        # Toutes les tactiques rattachées (multi-tactiques ATT&CK) ; repli sur la
        # tactique primaire pour les référentiels mono-tactique historiques.
        e["tactics"] = list(r.tactics) if r.tactics else ([r.tactic] if r.tactic else [])
    for r in steps:
        e = _entry(r.technique)
        e["steps"] += r.c
        e["verdicts"][r.verdict] = e["verdicts"].get(r.verdict, 0) + r.c
    for r in vulns:
        _entry(r.technique)["vulns"] += r.c
    for r in tickets:
        _entry(r.technique)["tickets"] += r.c
    for r in actions:
        _entry(r.technique)["actions"] += r.c
    for r in scenarios:
        _entry(r.technique)["scenarios"] += r.c

    for e in tech.values():
        for v in _VERDICT_RANK:
            if e["verdicts"].get(v):
                e["best_verdict"] = v
                break
        e["used"] = bool(e["steps"] or e["vulns"] or e["tickets"] or e["actions"])
        e["in_library"] = bool(e["scenarios"])
        # Détecté : une réponse défensive a été observée (prévenu / alerté / journalisé).
        e["detected"] = e["best_verdict"] in ("prevented", "alerted", "logged")

    # ── Hiérarchie technique / sous-technique (T1055 ⊃ T1055.011) ────────────
    # Les sous-techniques sont rattachées à leur parent ; la couverture se cumule
    # du sous vers le parent (comportement ATT&CK Navigator).
    def _parent_code(code: str) -> str:
        return code.split(".")[0]

    parents: dict[str, dict] = {}
    for code, e in tech.items():
        if "." not in code:
            parents.setdefault(code, e)
    # Parents manquants (sous-technique orpheline) : créer un stub.
    for code in tech:
        if "." in code:
            pc = _parent_code(code)
            if pc not in parents:
                parents[pc] = _entry(pc)
    for p in parents.values():
        p["subtechniques"] = []
    for code, e in tech.items():
        if "." in code:
            parents[_parent_code(code)]["subtechniques"].append(e)

    # Cumul : le parent est couvert/détecté si lui-même ou une sous-technique l'est.
    for p in parents.values():
        subs = p["subtechniques"] = sorted(p["subtechniques"], key=lambda x: x["ext_id"])
        p["sub_count"] = len(subs)
        p["sub_used"] = sum(1 for s in subs if s["used"])
        p["used"] = p["used"] or any(s["used"] for s in subs)
        p["detected"] = p["detected"] or any(s["detected"] for s in subs)
        if not p["best_verdict"]:
            for v in _VERDICT_RANK:
                if any(s["verdicts"].get(v) for s in subs):
                    p["best_verdict"] = v
                    break

    def _tactic_key(t: str | None) -> tuple[int, str]:
        if t in _TACTIC_ORDER:
            return (_TACTIC_ORDER.index(t), t)
        return (len(_TACTIC_ORDER), t or "non-mappée")

    # Placement multi-tactiques : une technique parente apparaît dans CHAQUE colonne à
    # laquelle elle (ou l'une de ses sous-techniques) se rattache — fidèle au Navigator.
    # Le même objet est référencé dans plusieurs listes ; les KPIs restent comptés une
    # seule fois (agrégés sur `parents.values()`).
    tactics: dict[str, list] = {}
    for e in parents.values():
        tacs = list(e.get("tactics") or ([e["tactic"]] if e.get("tactic") else []))
        for st in e.get("subtechniques", []):
            for t in (st.get("tactics") or ([st["tactic"]] if st.get("tactic") else [])):
                if t not in tacs:
                    tacs.append(t)
        for t in (tacs or ["non-mappée"]):
            tactics.setdefault(t, []).append(e)
    ordered = sorted(tactics.items(), key=lambda kv: _tactic_key(kv[0]))

    # ── KPIs au niveau parent (avec cumul) : chiffres lisibles quel que soit le
    # volume du référentiel (≈200 techniques parentes vs 697 avec sous-techniques).
    parent_total = len(parents)
    covered = sum(1 for e in parents.values() if e["used"])
    detected = sum(1 for e in parents.values() if e["used"] and e["detected"])
    gaps = sum(1 for e in parents.values() if e["used"] and not e["detected"])
    untested = sum(1 for e in parents.values() if e.get("name") is not None and not e["used"])
    return {
        "tactics": [
            {"tactic": name, "techniques": sorted(items, key=lambda x: x["ext_id"])}
            for name, items in ordered
        ],
        "summary": {
            "reference_total": len(ref),
            "parent_total": parent_total,
            "techniques_touched": covered,
            "coverage_pct": round(covered / parent_total * 100) if parent_total else 0,
            "covered": covered,
            "detected": detected,
            "gaps": gaps,
            "untested": untested,
        },
    }


@router.get("/attack-matrix")
async def attack_matrix(
    # Ancrage d'autorisation : tout rôle a L sur les étapes d'attaque ; la RLS fait le
    # reste (aucune donnée hors périmètre ne peut être agrégée).
    ctx: SecurityContext = Depends(require("attack_steps", Action.L)),
):
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as s:
        return await compute_attack_matrix(s)


# Verdicts « caught » : une réponse défensive a eu lieu (prévenu / alerté / journalisé).
_CAUGHT = ("prevented", "alerted", "logged")


async def compute_cockpit(s, client_id: str | None = None) -> dict:
    """Indicateurs du tableau de bord, agrégés sur la session fournie (cloisonnée RLS).

    Regroupe : posture des verdicts, taux de détection, angles morts, vulnérabilités
    (dont criticals hors SLA), audits par type, et un aperçu du journal.

    La posture (verdicts, taux de détection, angles morts) est mesurée sur le POOL du
    dernier exercice (run) de chaque audit — méthode unique, identique à celle de la
    tendance : les runs anciens d'un même audit ne comptent pas.

    `client_id` (optionnel) restreint l'agrégation à un client précis, à l'intérieur du
    périmètre RLS déjà appliqué (confort des rôles multi-clients).
    """
    cf = " AND client_id = :cid" if client_id else ""
    p = {"cid": client_id} if client_id else {}

    # Pool « dernier run par audit » : même critère de date que la tendance.
    last_run_pool = (
        "SELECT DISTINCT ON (audit_id) id FROM purple_exercise "
        f"WHERE deleted_at IS NULL{cf} "
        "ORDER BY audit_id, coalesce(date, created_at::date) DESC, created_at DESC"
    )

    # Posture des verdicts (étapes d'attaque du dernier run de chaque audit).
    verdict_rows = (await s.execute(text(
        "SELECT verdict, count(*) c FROM attack_step "
        f"WHERE exercise_id IN ({last_run_pool}){cf} GROUP BY verdict"
    ), p)).all()
    verdicts = {r.verdict: r.c for r in verdict_rows}
    tested = sum(v for k, v in verdicts.items() if k != "not_tested")
    caught = sum(verdicts.get(k, 0) for k in _CAUGHT)
    blind = verdicts.get("no_telemetry", 0)
    detection_rate = round(caught / tested * 100) if tested else None

    # Angles morts par tactique (maquette §panel.blind) : mêmes runs poolés, regroupés
    # par tactique du référentiel ; restitués plus bas en ordre kill-chain (inconnues en fin).
    blind_tac_rows = (await s.execute(text(
        "SELECT coalesce(r.tactic, '?') AS tactic, count(*) c "
        "FROM attack_step a LEFT JOIN ref_attack_technique r ON r.ext_id = a.technique "
        f"WHERE a.verdict = 'no_telemetry' AND a.exercise_id IN ({last_run_pool})"
        f"{cf.replace('client_id', 'a.client_id')} "
        "GROUP BY 1"
    ), p)).all()

    # Vulnérabilités : total, par sévérité, et criticals hors SLA.
    vuln_total = (await s.execute(text(
        f"SELECT count(*) FROM vulnerability WHERE deleted_at IS NULL{cf}"
    ), p)).scalar_one()
    sev_rows = (await s.execute(text(
        f"SELECT severite, count(*) c FROM vulnerability WHERE deleted_at IS NULL{cf} "
        "GROUP BY severite"
    ), p)).all()
    p1_breached = (await s.execute(text(
        f"SELECT count(*) FROM vulnerability WHERE deleted_at IS NULL{cf} "
        "AND sla_niveau = 'P1' AND sla_echeance < now()::date "
        "AND statut NOT IN ('corrige','resolu','ferme','accepte')"
    ), p)).scalar_one()

    # Audits : total et répartition par type.
    audit_total = (await s.execute(text(
        f"SELECT count(*) FROM audit WHERE deleted_at IS NULL{cf}"
    ), p)).scalar_one()
    cat_rows = (await s.execute(text(
        f"SELECT categorie, count(*) c FROM audit WHERE deleted_at IS NULL{cf} "
        "GROUP BY categorie"
    ), p)).all()

    exercise_total = (await s.execute(text(
        f"SELECT count(*) FROM purple_exercise WHERE deleted_at IS NULL{cf}"
    ), p)).scalar_one()

    # Aperçu du journal (dernières entrées).
    jrows = (await s.execute(text(
        "SELECT seq, event_type, actor_label, client_id, created_at FROM journal "
        f"WHERE true{cf} ORDER BY seq DESC LIMIT 8"
    ), p)).all()

    # ── Couverture par tactique MITRE (ordre kill-chain) ──────────────────────
    # Pour chaque tactique : techniques TESTÉES (distinct) et détectées, sur le pool
    # du dernier run par audit — même photographie que la posture et les angles morts.
    # Une technique jamais testée ne crée pas de tactique dans la bande.
    tac_rows = (await s.execute(text(
        "SELECT r.tactic, a.technique, "
        " bool_or(a.verdict IN ('prevented','alerted','logged')) AS detected "
        "FROM attack_step a JOIN ref_attack_technique r ON r.ext_id = a.technique "
        "WHERE a.technique IS NOT NULL AND a.verdict != 'not_tested' "
        f"AND a.exercise_id IN ({last_run_pool})"
        f"{cf.replace('client_id', 'a.client_id')} "
        "GROUP BY r.tactic, a.technique"
    ), p)).all()
    by_tac: dict[str, dict] = {}
    for r in tac_rows:
        e = by_tac.setdefault(r.tactic or "non-mappée", {"tot": 0, "det": 0})
        e["tot"] += 1
        if r.detected:
            e["det"] += 1

    def _tac_rank(t: str) -> int:
        return _TACTIC_ORDER.index(t) if t in _TACTIC_ORDER else len(_TACTIC_ORDER)

    tactic_coverage = [
        {
            "tactic": t, "total": v["tot"], "detected": v["det"],
            "state": ("detected" if v["det"] == v["tot"] else
                      "gap" if v["det"] == 0 else "partial"),
        }
        for t, v in sorted(by_tac.items(), key=lambda kv: _tac_rank(kv[0]))
    ]

    # Angles morts par tactique, ordre kill-chain ('?' et inconnues en fin).
    blind_tactics = [
        {"tactic": r.tactic, "count": r.c}
        for r in sorted(blind_tac_rows, key=lambda r: _tac_rank(r.tactic))
    ]

    # ── Tendance du taux de détection ─────────────────────────────────────────
    # Posture cumulée : à chaque point (fins de mois, ≤12), on retient le dernier run
    # de chaque audit à cette date et on mesure caught/tested sur ces runs.
    ex_rows = (await s.execute(text(
        "SELECT id, audit_id, coalesce(date, created_at::date) AS d "
        f"FROM purple_exercise WHERE deleted_at IS NULL{cf}"
    ), p)).all()
    trend: list[dict] = []
    if ex_rows:
        step_rows = (await s.execute(text(
            f"SELECT exercise_id, verdict FROM attack_step WHERE true{cf}"
        ), p)).all()
        steps_by_ex: dict[str, list[str]] = {}
        for r in step_rows:
            steps_by_ex.setdefault(str(r.exercise_id), []).append(r.verdict)

        import datetime as _dt

        today = _dt.date.today()
        first = min(r.d for r in ex_rows)
        # Fins de mois entre le premier run et aujourd'hui, plafonnées à 12 points.
        buckets: list[_dt.date] = []
        y, m = first.year, first.month
        while (y, m) <= (today.year, today.month):
            nm_y, nm_m = (y + 1, 1) if m == 12 else (y, m + 1)
            eom = _dt.date(nm_y, nm_m, 1) - _dt.timedelta(days=1)
            buckets.append(min(eom, today))
            y, m = nm_y, nm_m
        if len(buckets) > 12:
            stride = -(-len(buckets) // 12)  # plafonner en gardant le dernier point
            kept = buckets[::stride]
            if kept[-1] != buckets[-1]:
                kept.append(buckets[-1])
            buckets = kept

        for d in buckets:
            latest: dict[str, tuple] = {}  # audit_id -> (date, exercise_id)
            for r in ex_rows:
                if r.d <= d and (str(r.audit_id) not in latest or r.d >= latest[str(r.audit_id)][0]):
                    latest[str(r.audit_id)] = (r.d, str(r.id))
            tested_n = caught_n = 0
            for _, exid in latest.values():
                for v in steps_by_ex.get(exid, []):
                    if v != "not_tested":
                        tested_n += 1
                        if v in ("prevented", "alerted", "logged"):
                            caught_n += 1
            trend.append({
                "date": d.isoformat(),
                "tested": tested_n, "caught": caught_n,
                "pct": round(caught_n / tested_n * 100) if tested_n else 0,
                "audits": len(latest),
            })

    return {
        "kpis": {
            "detection_rate": detection_rate,
            "blind_spots": blind,
            "p1_breached": p1_breached,
            "audits": audit_total,
        },
        "posture": {
            "verdicts": verdicts,
            "tested": tested,
            "caught": caught,
        },
        "blind_tactics": blind_tactics,
        "vulnerabilities": {
            "total": vuln_total,
            "by_severity": {r.severite: r.c for r in sev_rows},
        },
        "audits_by_type": {r.categorie: r.c for r in cat_rows},
        "exercises": exercise_total,
        "tactic_coverage": tactic_coverage,
        "trend": trend,
        "journal": [
            {"seq": r.seq, "event_type": r.event_type, "actor": r.actor_label,
             "client_id": str(r.client_id) if r.client_id else None,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in jrows
        ],
    }


@router.get("/cockpit")
async def cockpit(
    client_id: str | None = None,
    ctx: SecurityContext = Depends(require("attack_steps", Action.L)),
):
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as s:
        return await compute_cockpit(s, client_id=client_id)


_CLOSED_VULN = ("corrige", "resolu", "ferme", "accepte")


async def compute_applications_coverage(s, client_id: str | None = None) -> list[dict]:
    """Couverture par application : vulnérabilités liées (total/hautes/ouvertes) et
    présence dans un périmètre d'audit. Le lien app↔vuln/audit est un tableau natif
    d'identifiants (uuid[]) → rapprochement par `application.id = ANY(...)`.
    """
    rows = (await s.execute(text(
        """
        SELECT a.id, a.nom, a.code, a.criticite, a.exposition, a.contact_metier,
               a.stack, a.type, a.statut, a.tlp,
          (SELECT count(*) FROM vulnerability v WHERE v.deleted_at IS NULL
             AND a.id = ANY(v.applications)) AS vuln_total,
          (SELECT count(*) FROM vulnerability v WHERE v.deleted_at IS NULL
             AND a.id = ANY(v.applications)
             AND lower(v.severite) IN ('critique','haute')) AS vuln_high,
          (SELECT count(*) FROM vulnerability v WHERE v.deleted_at IS NULL
             AND a.id = ANY(v.applications)
             AND v.statut NOT IN ('corrige','resolu','ferme','accepte')) AS vuln_open,
          EXISTS(SELECT 1 FROM audit au WHERE au.deleted_at IS NULL
             AND a.id = ANY(au.applications)) AS audited
        FROM application a
        WHERE a.deleted_at IS NULL{cf}
        ORDER BY a.nom
        """.replace("{cf}", " AND a.client_id::text = :cid" if client_id else "")
    ), ({"cid": client_id} if client_id else {}))).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["id"] = str(r["id"])
        out.append(d)
    return out


@router.get("/applications-coverage")
async def applications_coverage(
    client_id: str | None = None,
    ctx: SecurityContext = Depends(require("applications", Action.L)),
):
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as s:
        return {"items": await compute_applications_coverage(s, client_id=client_id)}


@router.get("/scenario-usage/{scenario_id}")
async def scenario_usage(
    scenario_id: str,
    ctx: SecurityContext = Depends(require("scenarios", Action.L)),
):
    """Contexte d'usage d'un scénario : audits/applications/clients/exercices qui le
    référencent, et couverture (détection/angles morts) mesurée sur ces exercices pour
    les techniques du scénario.

    Les scénarios sont une bibliothèque globale, mais les audits sont cloisonnés : chacun
    ne voit que les usages de son périmètre RLS.
    """
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as s:
        scen = (await s.execute(text(
            "SELECT techniques FROM scenario WHERE id = :sid AND deleted_at IS NULL"
        ), {"sid": scenario_id})).first()
        techniques = list(scen.techniques or []) if scen else []

        audit_rows = (await s.execute(text(
            "SELECT a.id, a.nom, a.statut, a.client_id, a.applications, o.nom AS client_nom "
            "FROM audit a JOIN organisation o ON o.id = a.client_id "
            "WHERE a.deleted_at IS NULL AND a.scenario_id = :sid "
            "ORDER BY a.created_at DESC"
        ), {"sid": scenario_id})).all()
        audit_ids = [str(r.id) for r in audit_rows]

        app_ids = sorted({str(a) for r in audit_rows for a in (r.applications or [])})
        app_rows = []
        if app_ids:
            app_rows = (await s.execute(text(
                "SELECT id, nom FROM application WHERE id = ANY(CAST(:ids AS uuid[])) AND deleted_at IS NULL"
            ), {"ids": app_ids})).all()

        exercice_rows = []
        if audit_ids:
            exercice_rows = (await s.execute(text(
                "SELECT id, nom, statut, audit_id FROM purple_exercise "
                "WHERE audit_id = ANY(CAST(:ids AS uuid[])) AND deleted_at IS NULL ORDER BY created_at DESC"
            ), {"ids": audit_ids})).all()
        exercice_ids = [str(r.id) for r in exercice_rows]

        # Couverture : meilleur verdict par technique du scénario, sur les étapes des
        # exercices liés (mêmes rangs que /analytics/attack-matrix, pour cohérence).
        covered = gaps = 0
        if techniques and exercice_ids:
            verdict_rows = (await s.execute(text(
                "SELECT technique, verdict FROM attack_step "
                "WHERE exercise_id = ANY(CAST(:ids AS uuid[])) AND technique = ANY(:techs)"
            ), {"ids": exercice_ids, "techs": techniques})).all()
            best: dict[str, str] = {}
            rank = {"prevented": 0, "alerted": 1, "logged": 2, "no_telemetry": 3, "not_tested": 4}
            for r in verdict_rows:
                cur = best.get(r.technique)
                if cur is None or rank.get(r.verdict, 9) < rank.get(cur, 9):
                    best[r.technique] = r.verdict
            for tq in techniques:
                v = best.get(tq)
                if v in ("prevented", "alerted", "logged"):
                    covered += 1
                elif v is not None:
                    gaps += 1  # jouée (no_telemetry) mais non détectée

    return {
        "scenario_id": scenario_id,
        "audits": [
            {"id": str(r.id), "nom": r.nom, "statut": r.statut,
             "client_id": str(r.client_id), "client_nom": r.client_nom}
            for r in audit_rows
        ],
        "clients": sorted({r.client_nom for r in audit_rows}),
        "applications": [{"id": str(r.id), "nom": r.nom} for r in app_rows],
        "exercices": [
            {"id": str(r.id), "nom": r.nom, "statut": r.statut, "audit_id": str(r.audit_id)}
            for r in exercice_rows
        ],
        "coverage": {
            "total": len(techniques), "covered": covered, "gaps": gaps,
            "covered_pct": round(covered / len(techniques) * 100) if techniques else 0,
        },
    }
