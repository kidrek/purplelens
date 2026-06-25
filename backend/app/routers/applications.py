from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Application, Audit, Finding
from app.models.enums import AuditStatus, Severity
from app.schemas.schemas import ApplicationCreate, ApplicationOut
from app.services.scoring import compute_portfolio

router = APIRouter(prefix="/applications", tags=["applications"])

IN_PROGRESS_STATUSES = {AuditStatus.in_progress, AuditStatus.scoping, AuditStatus.review}
DONE_STATUSES = {AuditStatus.completed, AuditStatus.closed}
AUDIT_TYPES = ["BAS", "Pentest", "Red Team", "Purple Team"]


@router.get("", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    return db.query(Application).order_by(Application.name).all()


@router.get("/kpis")
def applications_kpis(db: Session = Depends(get_db)):
    """
    KPIs agrégés pour la page Applications :
    - Nombre total d'applications
    - Nombre d'applications exposées Internet
    - % d'applications couvertes par type d'audit (BAS/Pentest/Red Team/Purple Team)
    - % de couverture détection (moy. portfolio)
    - % de couverture réaction (moy. portfolio)
    """
    apps = db.query(Application).all()
    total = len(apps)
    internet_count = sum(1 for a in apps if a.exposure.value == "Internet")

    # Couverture par type d'audit : % d'apps ayant au moins un audit done/in_progress
    audits = db.query(Audit).all()
    by_app: dict[int, list] = {a.id: [] for a in apps}
    for audit in audits:
        if audit.application_id in by_app:
            by_app[audit.application_id].append(audit)

    audit_coverage: dict[str, float] = {}
    for atype in AUDIT_TYPES:
        covered = sum(
            1 for app in apps
            if any(
                a.audit_type.value == atype and
                (a.status in DONE_STATUSES or a.status in IN_PROGRESS_STATUSES)
                for a in by_app[app.id]
            )
        )
        audit_coverage[atype] = round(100 * covered / total, 1) if total else 0.0

    # Détection & réaction depuis le portfolio scoring
    portfolio = compute_portfolio(db)
    summary = portfolio.get("summary", {})

    return {
        "total":            total,
        "internet_count":   internet_count,
        "internet_pct":     round(100 * internet_count / total, 1) if total else 0.0,
        "audit_coverage":   audit_coverage,
        "detection_pct":    summary.get("avg_detection_coverage_pct", 0.0),
        "reaction_pct":     summary.get("avg_response_coverage_pct", 0.0),
    }


@router.get("/coverage")
def applications_coverage(db: Session = Depends(get_db)):
    """
    Retourne pour chaque application la couverture par type d'audit.
    Format : { app_id: { "BAS": "done"|"in_progress"|null, ... } }
    """
    apps = db.query(Application).order_by(Application.name).all()
    audits = db.query(Audit).all()

    by_app: dict[int, list] = {a.id: [] for a in apps}
    for audit in audits:
        if audit.application_id in by_app:
            by_app[audit.application_id].append(audit)

    result = {}
    for app in apps:
        coverage = {}
        for atype in AUDIT_TYPES:
            app_audits = [a for a in by_app[app.id] if a.audit_type.value == atype]
            if any(a.status in DONE_STATUSES for a in app_audits):
                coverage[atype] = "done"
            elif any(a.status in IN_PROGRESS_STATUSES for a in app_audits):
                coverage[atype] = "in_progress"
            else:
                coverage[atype] = None
        result[app.id] = coverage

    return result


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    app = Application(**payload.model_dump())
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.get("/{app_id}", response_model=ApplicationOut)
def get_application(app_id: int, db: Session = Depends(get_db)):
    app = db.get(Application, app_id)
    if app is None:
        raise HTTPException(404, "Application introuvable")
    return app


@router.put("/{app_id}", response_model=ApplicationOut)
def update_application(
    app_id: int, payload: ApplicationCreate, db: Session = Depends(get_db)
):
    app = db.get(Application, app_id)
    if app is None:
        raise HTTPException(404, "Application introuvable")
    for k, v in payload.model_dump().items():
        setattr(app, k, v)
    db.commit()
    db.refresh(app)
    return app


@router.delete("/{app_id}", status_code=204)
def delete_application(app_id: int, db: Session = Depends(get_db)):
    app = db.get(Application, app_id)
    if app is None:
        raise HTTPException(404, "Application introuvable")
    db.delete(app)
    db.commit()
