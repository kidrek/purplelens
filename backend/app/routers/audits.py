from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Audit, DetectionAssessment, Scenario
from app.schemas.schemas import (
    AssessmentCreate,
    AssessmentOut,
    AuditCreate,
    AuditOut,
)

router = APIRouter(prefix="/audits", tags=["audits"])


@router.get("", response_model=list[AuditOut])
def list_audits(db: Session = Depends(get_db)):
    return db.query(Audit).order_by(Audit.created_at.desc()).all()


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
    audit = db.get(Audit, audit_id)
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
    # tri kill-chain : step_order renseigné d'abord (ordre croissant), puis id
    rows.sort(key=lambda a: (a.step_order is None, a.step_order or 0, a.id))
    return rows


@router.post("/{audit_id}/assessments", response_model=AssessmentOut, status_code=201)
def upsert_assessment(
    audit_id: int, payload: AssessmentCreate, db: Session = Depends(get_db)
):
    if db.get(Audit, audit_id) is None:
        raise HTTPException(404, "Audit introuvable")

    # Upsert : une seule évaluation par (audit, technique)
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
    """Crée une évaluation vide (non détecté/non réagi) pour chaque technique
    des scénarios rattachés à l'audit, sans écraser les évaluations existantes.
    L'ordre kill-chain (step_order) est pré-rempli selon l'ordre des tactiques."""
    audit = db.get(Audit, audit_id)
    if audit is None:
        raise HTTPException(404, "Audit introuvable")

    # ordre logique des tactiques ATT&CK pour pré-remplir la kill-chain
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
    # techniques à créer, triées par tactique pour un step_order cohérent
    to_create = []
    for scenario in audit.scenarios:
        for tech in scenario.techniques:
            if tech.id not in existing:
                to_create.append(tech)
                existing.add(tech.id)
    to_create.sort(key=lambda t: tactic_rank.get(t.tactic or "", 99))

    # repart du max step_order déjà présent
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
