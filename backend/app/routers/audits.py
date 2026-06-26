from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Application, Audit, DetectionAssessment, Finding, Scenario
from app.models.enums import AuditStatus, FindingStatus
from app.schemas.schemas import (
    AssessmentCreate,
    AssessmentOut,
    AuditCreate,
    AuditOut,
)

router = APIRouter(prefix="/audits", tags=["audits"])

DONE_STATUSES = {AuditStatus.completed, AuditStatus.closed}
OPEN_STATUSES = {
    FindingStatus.open,
    FindingStatus.validated,
    FindingStatus.assigned,
    FindingStatus.in_progress,
}


def _period_bounds(period: str) -> tuple[datetime | None, datetime]:
    now = datetime.utcnow()
    if period == "1m":
        return now - timedelta(days=30), now
    if period == "6m":
        return now - timedelta(days=182), now
    if period == "1a":
        return datetime(now.year, 1, 1), now
    return None, now


# ── KPI audits (doit être avant /{audit_id} pour éviter collision de route) ──
@router.get("/kpis")
def audits_kpis(period: str = "1a", db: Session = Depends(get_db)):
    """
    KPIs de la page Gestion des audits, filtrés par période.
    Période : 1m | 6m | 1a | all
    """
    from_dt, to_dt = _period_bounds(period)

    # Audits de la période — filtrés sur end_date (date de réalisation effective)
    q = db.query(Audit).filter(
        Audit.end_date.isnot(None),
        Audit.end_date <= to_dt,
    )
    if from_dt:
        q = q.filter(Audit.end_date >= from_dt)
    audits = q.all()

    done_audits = [a for a in audits if a.status in DONE_STATUSES]
    total_audits = len(done_audits)

    # Applications
    total_apps = db.query(Application).count()
    audited_app_ids = {a.application_id for a in done_audits}
    audited_apps = len(audited_app_ids)

    # Taux de détection moyen
    assessments_q = db.query(DetectionAssessment).join(Audit).filter(
        Audit.created_at <= to_dt
    )
    if from_dt:
        assessments_q = assessments_q.filter(Audit.created_at >= from_dt)
    assessments = assessments_q.all()
    detection_rate = (
        round(100 * sum(1 for a in assessments if a.detected) / len(assessments), 1)
        if assessments else 0.0
    )

    # Vulnérabilités ouvertes sur la période
    vuln_q = db.query(Finding).filter(Finding.status.in_(OPEN_STATUSES))
    if from_dt:
        vuln_q = vuln_q.filter(Finding.created_at >= from_dt)
    vuln_q = vuln_q.filter(Finding.created_at <= to_dt)
    open_vulns = vuln_q.count()

    # Répartition par type
    repartition = {t: 0 for t in ["BAS", "Pentest", "Red Team", "Purple Team"]}
    for a in done_audits:
        key = a.audit_type.value
        if key in repartition:
            repartition[key] += 1

    # Heatmap audits — année courante, basée sur end_date
    year = datetime.utcnow().year
    year_start = datetime(year, 1, 1)
    year_end   = datetime(year, 12, 31, 23, 59, 59)
    audit_heatmap: dict[str, int] = {}
    for a in db.query(Audit).filter(
        Audit.end_date.isnot(None),
        Audit.end_date >= year_start,
        Audit.end_date <= year_end,
    ).all():
        day = a.end_date.strftime("%Y-%m-%d")
        audit_heatmap[day] = audit_heatmap.get(day, 0) + 1

    # Heatmap vulnérabilités — basée sur les événements FindingEvent (created)
    from app.models.models import FindingEvent
    from app.models.enums import FindingEventType
    vuln_heatmap: dict[str, int] = {}
    for ev in db.query(FindingEvent).filter(
        FindingEvent.event_type == FindingEventType.created,
        FindingEvent.created_at >= year_start,
        FindingEvent.created_at <= year_end,
    ).all():
        day = ev.created_at.strftime("%Y-%m-%d")
        vuln_heatmap[day] = vuln_heatmap.get(day, 0) + 1

    return {
        "period": period,
        "total_audits": total_audits,
        "total_apps": total_apps,
        "audited_apps": audited_apps,
        "detection_rate": detection_rate,
        "open_vulns": open_vulns,
        "repartition": repartition,
        "audit_heatmap": audit_heatmap,
        "vuln_heatmap": vuln_heatmap,
    }


@router.get("", response_model=list[AuditOut])
def list_audits(db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    return (
        db.query(Audit)
        .options(
            joinedload(Audit.scenarios),
            joinedload(Audit.assessments).joinedload(DetectionAssessment.technique),
            joinedload(Audit.findings),
            joinedload(Audit.application),
        )
        .order_by(Audit.created_at.desc())
        .all()
    )


@router.post("", response_model=AuditOut, status_code=201)
def create_audit(payload: AuditCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    scenario_ids = data.pop("scenario_ids", [])
    audit = Audit(**data)
    for sid in scenario_ids:
        scenario = db.get(Scenario, sid)
        if scenario:
            audit.scenarios.append(scenario)
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


@router.get("/{audit_id}", response_model=AuditOut)
def get_audit(audit_id: int, db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    audit = (
        db.query(Audit)
        .options(
            joinedload(Audit.scenarios),
            joinedload(Audit.assessments).joinedload(DetectionAssessment.technique),
            joinedload(Audit.findings),
            joinedload(Audit.application),
        )
        .filter(Audit.id == audit_id)
        .first()
    )
    if audit is None:
        raise HTTPException(404, "Audit introuvable")
    return audit


@router.put("/{audit_id}", response_model=AuditOut)
def update_audit(audit_id: int, payload: AuditCreate, db: Session = Depends(get_db)):
    audit = db.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(404, "Audit introuvable")
    data = payload.model_dump()
    scenario_ids = data.pop("scenario_ids", [])
    for k, v in data.items():
        setattr(audit, k, v)
    audit.scenarios = [
        s for s in (db.get(Scenario, sid) for sid in scenario_ids) if s
    ]
    db.commit()
    db.refresh(audit)
    return audit


@router.delete("/{audit_id}", status_code=204)
def delete_audit(audit_id: int, db: Session = Depends(get_db)):
    audit = db.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(404, "Audit introuvable")
    db.delete(audit)
    db.commit()


# --- Module 4 : évaluation détection / réaction par technique ---
@router.get("/{audit_id}/assessments", response_model=list[AssessmentOut])
def list_assessments(audit_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(DetectionAssessment)
        .filter(DetectionAssessment.audit_id == audit_id)
        .all()
    )
    rows.sort(key=lambda a: (a.step_order is None, a.step_order or 0, a.id))
    return rows


@router.post("/{audit_id}/assessments", response_model=AssessmentOut, status_code=201)
def upsert_assessment(
    audit_id: int, payload: AssessmentCreate, db: Session = Depends(get_db)
):
    if db.get(Audit, audit_id) is None:
        raise HTTPException(404, "Audit introuvable")

    existing = (
        db.query(DetectionAssessment)
        .filter(
            DetectionAssessment.audit_id == audit_id,
            DetectionAssessment.technique_id == payload.technique_id,
        )
        .first()
    )
    data = payload.model_dump()
    data["audit_id"] = audit_id
    data["detected"] = int(data["detected"])
    data["responded"] = int(data["responded"])

    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return existing

    assessment = DetectionAssessment(**data)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.post("/{audit_id}/populate", response_model=list[AssessmentOut])
def populate_assessments(audit_id: int, db: Session = Depends(get_db)):
    """Crée une évaluation vide pour chaque technique des scénarios rattachés."""
    audit = db.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(404, "Audit introuvable")

    tactic_rank = {
        t: i for i, t in enumerate([
            "Initial Access", "Execution", "Persistence", "Privilege Escalation",
            "Defense Evasion", "Credential Access", "Discovery",
            "Lateral Movement", "Collection", "Command and Control",
            "Exfiltration", "Impact",
        ])
    }

    existing = {
        a.technique_id
        for a in db.query(DetectionAssessment).filter(
            DetectionAssessment.audit_id == audit_id
        )
    }
    to_create = []
    for scenario in audit.scenarios:
        for tech in scenario.techniques:
            if tech.id not in existing:
                to_create.append(tech)
                existing.add(tech.id)
    to_create.sort(key=lambda t: tactic_rank.get(t.tactic or "", 99))

    base = db.query(DetectionAssessment).filter(
        DetectionAssessment.audit_id == audit_id,
        DetectionAssessment.step_order.isnot(None),
    ).count()
    for i, tech in enumerate(to_create):
        db.add(DetectionAssessment(
            audit_id=audit_id, technique_id=tech.id,
            detected=0, responded=0, step_order=base + i + 1,
        ))
    db.commit()
    return list_assessments(audit_id, db)
