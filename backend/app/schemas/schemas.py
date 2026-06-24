from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.enums import (
    AuditStatus,
    AuditType,
    Exposure,
    FindingStatus,
    Severity,
)


# --- Techniques & scénarios (CTI) ---
class TechniqueOut(BaseModel):
    id: int
    mitre_id: str
    name: str
    tactic: str

    class Config:
        from_attributes = True


class ScenarioStepIn(BaseModel):
    order: int = 1
    tactic: str = ""
    mitre_id: str = ""
    technique_name: str = ""
    action: str = ""
    description: str = ""


class ScenarioStepOut(ScenarioStepIn):
    id: int

    class Config:
        from_attributes = True


class ScenarioBase(BaseModel):
    name: str
    description: str = ""
    threat_actor: str = ""        # adversaire émulé
    objective: str = ""           # objectif visé
    engagement_type: AuditType = AuditType.purple_team
    sophistication: str = "Intermédiaire"
    ioc: str = ""
    ioa: str = ""
    references: str = ""


class ScenarioCreate(ScenarioBase):
    technique_mitre_ids: list[str] = []   # conservé pour compat
    steps: list[ScenarioStepIn] = []


class ScenarioOut(ScenarioBase):
    id: int
    techniques: list[TechniqueOut] = []
    steps: list[ScenarioStepOut] = []

    class Config:
        from_attributes = True


# --- Applications ---
class ApplicationBase(BaseModel):
    name: str
    description: str = ""
    owner: str = ""
    team: str = ""
    email: str = ""
    phone: str = ""
    exposure: Exposure = Exposure.interne
    technologies: str = ""
    technologies_cpe: str = ""
    url: str = ""
    scope_red_team: str = ""
    scope_pentest: str = ""
    dic_availability: int = 3
    dic_integrity: int = 3
    dic_confidentiality: int = 3


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationOut(ApplicationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Audits ---
class AuditBase(BaseModel):
    name: str
    audit_type: AuditType = AuditType.purple_team
    status: AuditStatus = AuditStatus.draft
    application_id: int
    team: str = ""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    results: str = ""


class AuditCreate(AuditBase):
    scenario_ids: list[int] = []


class AuditOut(AuditBase):
    id: int
    scenarios: list[ScenarioOut] = []

    class Config:
        from_attributes = True


# --- Détection / réaction (Module 4) ---
class AssessmentBase(BaseModel):
    audit_id: int
    technique_id: int
    detected: bool = False
    responded: bool = False
    detection_time_min: Optional[float] = None
    response_time_min: Optional[float] = None
    step_description: str = ""
    command: str = ""
    step_order: Optional[int] = None
    notes: str = ""


class AssessmentCreate(AssessmentBase):
    pass


class AssessmentOut(AssessmentBase):
    id: int
    technique: TechniqueOut

    class Config:
        from_attributes = True


# --- Vulnérabilités ---
class FindingBase(BaseModel):
    title: str
    description: str = ""
    impact: str = ""
    cvss: float = 0.0
    severity: Severity = Severity.medium
    status: FindingStatus = FindingStatus.open
    owasp: str = ""
    cwe: str = ""
    capec: str = ""
    owasp_refs: str = ""
    cwe_refs: str = ""
    capec_refs: str = ""
    application_id: int
    audit_id: Optional[int] = None


class FindingCreate(FindingBase):
    pass


class FindingOut(FindingBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
