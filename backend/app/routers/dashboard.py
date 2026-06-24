from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Finding
from app.schemas.schemas import FindingCreate, FindingOut
from app.services.scoring import (
    compute_application_matrix,
    compute_application_scores,
    compute_portfolio,
)

router = APIRouter(tags=["findings", "dashboard"])


# --- Module 5 : vulnérabilités ---
@router.get("/findings", response_model=list[FindingOut])
def list_findings(
    application_id: int | None = None,
    audit_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Finding)
    if application_id is not None:
        q = q.filter(Finding.application_id == application_id)
    if audit_id is not None:
        q = q.filter(Finding.audit_id == audit_id)
    return q.order_by(Finding.cvss.desc()).all()


@router.post("/findings", response_model=FindingOut, status_code=201)
def create_finding(payload: FindingCreate, db: Session = Depends(get_db)):
    finding = Finding(**payload.model_dump())
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@router.put("/findings/{finding_id}", response_model=FindingOut)
def update_finding(
    finding_id: int, payload: FindingCreate, db: Session = Depends(get_db)
):
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(404, "Vulnérabilité introuvable")
    for k, v in payload.model_dump().items():
        setattr(finding, k, v)
    db.commit()
    db.refresh(finding)
    return finding


@router.delete("/findings/{finding_id}", status_code=204)
def delete_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(404, "Vulnérabilité introuvable")
    db.delete(finding)
    db.commit()


# --- Module 7 : dashboard Purple Team ---
@router.get("/dashboard/portfolio")
def portfolio(db: Session = Depends(get_db)):
    """Vue d'ensemble du portefeuille applicatif."""
    return compute_portfolio(db)


@router.get("/dashboard/application/{app_id}")
def application_dashboard(app_id: int, db: Session = Depends(get_db)):
    """Vue détaillée par application avec les 5 KPIs."""
    scores = compute_application_scores(db, app_id)
    if not scores:
        raise HTTPException(404, "Application introuvable")
    return scores


@router.get("/dashboard/application/{app_id}/matrix")
def application_matrix(app_id: int, db: Session = Depends(get_db)):
    """Matrice ATT&CK consolidée (dernière valeur par technique)."""
    matrix = compute_application_matrix(db, app_id)
    if not matrix:
        raise HTTPException(404, "Application introuvable")
    return matrix
