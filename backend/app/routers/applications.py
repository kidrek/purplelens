from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Application
from app.schemas.schemas import ApplicationCreate, ApplicationOut

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    return db.query(Application).order_by(Application.name).all()


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
