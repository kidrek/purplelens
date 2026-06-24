from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Scenario, ScenarioStep, Technique
from app.schemas.schemas import ScenarioCreate, ScenarioOut, TechniqueOut

router = APIRouter(prefix="/cti", tags=["cti"])


def _get_or_create_technique(db: Session, mitre_id: str, name="", tactic="") -> Technique:
    tech = db.query(Technique).filter(Technique.mitre_id == mitre_id).first()
    if tech is None:
        tech = Technique(mitre_id=mitre_id, name=name, tactic=tactic)
        db.add(tech)
        db.flush()
    else:
        # enrichit si on a de nouvelles infos
        if name and not tech.name:
            tech.name = name
        if tactic and not tech.tactic:
            tech.tactic = tactic
    return tech


def _apply_steps_and_techniques(db: Session, scenario: Scenario, data: dict):
    """Construit les étapes de kill-chain et dérive les techniques associées."""
    steps = data.pop("steps", [])
    mitre_ids = data.pop("technique_mitre_ids", [])

    # Remplace les étapes
    scenario.steps = []
    db.flush()
    seen = set()
    for s in steps:
        scenario.steps.append(ScenarioStep(
            order=s.get("order", 1),
            tactic=s.get("tactic", ""),
            mitre_id=s.get("mitre_id", ""),
            technique_name=s.get("technique_name", ""),
            action=s.get("action", ""),
            description=s.get("description", ""),
        ))
        if s.get("mitre_id"):
            seen.add((s["mitre_id"], s.get("technique_name", ""), s.get("tactic", "")))

    # techniques dérivées des étapes (+ celles éventuellement passées à part)
    techniques = []
    for mid, name, tactic in seen:
        techniques.append(_get_or_create_technique(db, mid, name, tactic))
    for mid in mitre_ids:
        if mid not in {m for m, _, _ in seen}:
            techniques.append(_get_or_create_technique(db, mid))
    scenario.techniques = techniques


@router.get("/techniques", response_model=list[TechniqueOut])
def list_techniques(db: Session = Depends(get_db)):
    return db.query(Technique).order_by(Technique.mitre_id).all()


@router.get("/scenarios", response_model=list[ScenarioOut])
def list_scenarios(db: Session = Depends(get_db)):
    return db.query(Scenario).order_by(Scenario.name).all()


@router.post("/scenarios", response_model=ScenarioOut, status_code=201)
def create_scenario(payload: ScenarioCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    scenario = Scenario(
        name=data["name"], description=data["description"],
        threat_actor=data["threat_actor"], objective=data["objective"],
        engagement_type=data["engagement_type"], sophistication=data["sophistication"],
        ioc=data["ioc"], ioa=data["ioa"], references=data["references"],
    )
    db.add(scenario)
    db.flush()
    _apply_steps_and_techniques(db, scenario, data)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut)
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(404, "Scénario introuvable")
    return scenario


@router.put("/scenarios/{scenario_id}", response_model=ScenarioOut)
def update_scenario(
    scenario_id: int, payload: ScenarioCreate, db: Session = Depends(get_db)
):
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(404, "Scénario introuvable")
    data = payload.model_dump()
    for k in ("name", "description", "threat_actor", "objective",
              "engagement_type", "sophistication", "ioc", "ioa", "references"):
        setattr(scenario, k, data[k])
    _apply_steps_and_techniques(db, scenario, data)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.delete("/scenarios/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(404, "Scénario introuvable")
    db.delete(scenario)
    db.commit()
