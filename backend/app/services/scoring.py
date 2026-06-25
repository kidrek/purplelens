"""Moteur de scoring Purple Team.

Calcule les 5 KPIs du MVP par application :
  1. Coverage ATT&CK   = techniques testées / techniques pertinentes
  2. Detection Coverage = techniques détectées / techniques testées
  3. Response Coverage  = techniques avec réaction / techniques testées
  4. MTTD               = moyenne des temps de détection
  5. MTTR               = moyenne des temps de réaction

Une technique "pertinente" pour une application = toute technique présente
dans au moins un scénario rattaché à un audit de cette application.
Une technique "testée" = ayant au moins une évaluation (DetectionAssessment).
"""

from statistics import mean

from sqlalchemy.orm import Session

from app.models.models import (
    Application,
    Audit,
    DetectionAssessment,
    Finding,
    Scenario,
)
from app.models.enums import Severity
from app.services.mitre_catalog import get_catalog_size


def _pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(100 * numerator / denominator, 1)


# Niveau de criticité métier dérivé du DIC max (1-5) -> label + coefficient
def _business_criticality(dic_max: int) -> dict:
    table = {
        5: ("Vitale", 1.2),
        4: ("Critique", 1.1),
        3: ("Importante", 1.0),
        2: ("Modérée", 0.9),
        1: ("Mineure", 0.8),
    }
    label, coef = table.get(dic_max, ("Importante", 1.0))
    return {"level": dic_max, "label": label, "coefficient": coef}


# Coefficient d'exposition réseau par type d'exposition
def _exposure_coefficient(exposure: str) -> dict:
    table = {
        "Internet": 1.5,
        "Partenaire": 1.3,
        "Cloud": 1.2,
        "Interne": 1.0,
    }
    return {"exposure": exposure, "coefficient": table.get(exposure, 1.0)}


# Catalogue des types d'audit pour la couverture
AUDIT_TYPE_CATALOG = ["BAS", "Pentest", "Red Team", "Purple Team"]


def _audit_coverage(audits) -> dict:
    """Quels types d'audit ont été réalisés sur l'application."""
    done = {a.audit_type.value for a in audits}
    items = [{"type": t, "done": t in done} for t in AUDIT_TYPE_CATALOG]
    covered = sum(1 for it in items if it["done"])
    return {
        "items": items,
        "covered": covered,
        "total": len(AUDIT_TYPE_CATALOG),
        "coverage_pct": _pct(covered, len(AUDIT_TYPE_CATALOG)),
    }


def compute_application_scores(db: Session, app_id: int) -> dict:
    application = db.get(Application, app_id)
    if application is None:
        return {}

    audits = db.query(Audit).filter(Audit.application_id == app_id).all()
    audit_ids = [a.id for a in audits]

    # --- Techniques pertinentes : union des techniques de tous les scénarios
    #     rattachés aux audits de l'application.
    relevant_technique_ids: set[int] = set()
    for audit in audits:
        for scenario in audit.scenarios:
            for technique in scenario.techniques:
                relevant_technique_ids.add(technique.id)

    # --- Évaluations (techniques effectivement jouées)
    assessments = (
        db.query(DetectionAssessment)
        .filter(DetectionAssessment.audit_id.in_(audit_ids or [-1]))
        .all()
    )

    tested_technique_ids = {a.technique_id for a in assessments}

    detected = sum(1 for a in assessments if a.detected)
    responded = sum(1 for a in assessments if a.responded)
    tested = len(assessments)

    detect_times = [
        a.detection_time_min for a in assessments
        if a.detected and a.detection_time_min is not None
    ]
    response_times = [
        a.response_time_min for a in assessments
        if a.responded and a.response_time_min is not None
    ]

    # --- Vulnérabilités par sévérité
    findings = db.query(Finding).filter(Finding.application_id == app_id).all()
    by_severity = {s.value: 0 for s in Severity}
    for f in findings:
        by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1

    # --- Couverture sur le catalogue ATT&CK complet
    catalog_size = get_catalog_size(db, include_subtechniques=False)

    return {
        "application_id": application.id,
        "application_name": application.name,
        "exposure": application.exposure.value,
        "dic": {
            "availability": application.dic_availability,
            "integrity": application.dic_integrity,
            "confidentiality": application.dic_confidentiality,
        },
        "techniques_relevant": len(relevant_technique_ids),
        "techniques_tested": len(tested_technique_ids),
        "techniques_detected": detected,
        "techniques_responded": responded,
        "catalog_size": catalog_size,
        "kpis": {
            # KPI 1 — couverture sur le catalogue complet ATT&CK (0 si catalogue non synchronisé)
            "attack_coverage_pct": _pct(
                len(tested_technique_ids), catalog_size
            ) if catalog_size else _pct(
                len(tested_technique_ids), len(relevant_technique_ids)
            ),
            "attack_coverage_pct_of_relevant": _pct(
                len(tested_technique_ids), len(relevant_technique_ids)
            ),
            "catalog_synced": catalog_size > 0,
            # KPI 2
            "detection_coverage_pct": _pct(detected, tested),
            # KPI 3
            "response_coverage_pct": _pct(responded, tested),
            # KPI 4
            "mttd_min": round(mean(detect_times), 1) if detect_times else None,
            # KPI 5
            "mttr_min": round(mean(response_times), 1) if response_times else None,
        },
        "vulnerabilities": by_severity,
        "audits_count": len(audits),
        "business_criticality": _business_criticality(
            max(
                application.dic_availability,
                application.dic_integrity,
                application.dic_confidentiality,
            )
        ),
        "network_exposure": _exposure_coefficient(application.exposure.value),
        "audit_coverage": _audit_coverage(audits),
    }


def compute_portfolio(db: Session) -> dict:
    """Vue d'ensemble : agrégat sur toutes les applications."""
    apps = db.query(Application).all()
    rows = [compute_application_scores(db, a.id) for a in apps]

    def _avg(key_path):
        vals = []
        for r in rows:
            v = r["kpis"][key_path]
            if v is not None:
                vals.append(v)
        return round(mean(vals), 1) if vals else 0.0

    total_critical = sum(r["vulnerabilities"].get("Critical", 0) for r in rows)
    total_high = sum(r["vulnerabilities"].get("High", 0) for r in rows)

    return {
        "applications": rows,
        "summary": {
            "applications_count": len(rows),
            "avg_attack_coverage_pct": _avg("attack_coverage_pct"),
            "avg_detection_coverage_pct": _avg("detection_coverage_pct"),
            "avg_response_coverage_pct": _avg("response_coverage_pct"),
            "open_critical": total_critical,
            "open_high": total_high,
        },
    }


def _audit_recency_key(audit):
    """Clé de récence d'un audit : date de fin, sinon début, sinon id.
    Sert à départager les doublons (on garde la valeur la plus récente)."""
    return (
        audit.end_date or audit.start_date,
        audit.id,
    )


def compute_application_matrix(db: Session, app_id: int) -> dict:
    """Matrice MITRE ATT&CK consolidée pour une application.

    Pour chaque technique testée (au moins une évaluation), agrège les
    résultats de TOUS les audits de l'application. En cas de doublon (même
    technique évaluée dans plusieurs audits), on conserve la valeur de l'audit
    le plus récent.

    Renvoie les techniques regroupées par tactique, prêtes à afficher en
    matrice, avec le niveau de capacité détection / réaction.
    """
    application = db.get(Application, app_id)
    if application is None:
        return {}

    audits = db.query(Audit).filter(Audit.application_id == app_id).all()
    audit_by_id = {a.id: a for a in audits}
    audit_ids = list(audit_by_id.keys())

    assessments = (
        db.query(DetectionAssessment)
        .filter(DetectionAssessment.audit_id.in_(audit_ids or [-1]))
        .all()
    )

    # technique_id -> meilleure (plus récente) évaluation
    latest: dict[int, DetectionAssessment] = {}
    for a in assessments:
        audit = audit_by_id.get(a.audit_id)
        if audit is None:
            continue
        cur = latest.get(a.technique_id)
        if cur is None or _audit_recency_key(audit) >= _audit_recency_key(
            audit_by_id[cur.audit_id]
        ):
            latest[a.technique_id] = a

    # Construit les cellules, regroupées par tactique
    tactics: dict[str, list] = {}
    for tech_id, a in latest.items():
        tech = a.technique
        source_audit = audit_by_id[a.audit_id]
        # niveau de capacité : detected + responded => "full",
        # detected seul => "detect", rien => "none"
        if a.detected and a.responded:
            capability = "full"
        elif a.detected:
            capability = "detect"
        else:
            capability = "none"

        cell = {
            "mitre_id": tech.mitre_id,
            "name": tech.name,
            "tactic": tech.tactic or "Autre",
            "detected": bool(a.detected),
            "responded": bool(a.responded),
            "capability": capability,
            "detection_time_min": a.detection_time_min,
            "response_time_min": a.response_time_min,
            "source_audit_id": source_audit.id,
            "source_audit_name": source_audit.name,
        }
        tactics.setdefault(cell["tactic"], []).append(cell)

    # tri des techniques par identifiant dans chaque tactique
    for cells in tactics.values():
        cells.sort(key=lambda c: c["mitre_id"])

    # ordre logique des tactiques ATT&CK (celles connues d'abord)
    tactic_order = [
        "Initial Access", "Execution", "Persistence", "Privilege Escalation",
        "Defense Evasion", "Credential Access", "Discovery",
        "Lateral Movement", "Collection", "Command and Control",
        "Exfiltration", "Impact",
    ]
    ordered = []
    for t in tactic_order:
        if t in tactics:
            ordered.append({"tactic": t, "techniques": tactics.pop(t)})
    # tactiques restantes (non listées) en fin
    for t in sorted(tactics):
        ordered.append({"tactic": t, "techniques": tactics[t]})

    counts = {
        "full": sum(1 for a in latest.values() if a.detected and a.responded),
        "detect": sum(1 for a in latest.values() if a.detected and not a.responded),
        "none": sum(1 for a in latest.values() if not a.detected),
        "total": len(latest),
    }

    return {
        "application_id": application.id,
        "application_name": application.name,
        "tactics": ordered,
        "counts": counts,
    }
