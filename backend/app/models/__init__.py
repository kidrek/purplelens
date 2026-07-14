"""Agrégateur des modèles — garantit que toutes les tables sont enregistrées sur Base.metadata."""
from app.models.base import Base  # noqa: F401
from app.models.business import (  # noqa: F401
    Application,
    AttackStep,
    Audit,
    AuditAction,
    AuditMilestone,
    CorpusArticle,
    DefenseObservation,
    Deliverable,
    DetectionTicket,
    Organisation,
    PurpleExercise,
    RemediationTicket,
    Ressource,
    Scenario,
    ScenarioStep,
    SlaRule,
    Vulnerability,
    VulnerabilityEnrichment,
)
from app.models.evidence import (  # noqa: F401
    AuditDek,
    Evidence,
    EvidenceAccess,
    RefAttackGroup,
    RefAttackTechnique,
    RefCapec,
    RefCwe,
    RefD3fend,
    RefMispActor,
    RefOwasp,
)
from app.models.security import AppUser, Journal, RefreshToken  # noqa: F401

# Tables portant client_id → doivent toutes avoir une politique RLS (DAT §2.2 règle 1).
CLIENT_SCOPED_TABLES = [
    "organisation", "application", "ressource", "audit", "audit_action",
    "audit_milestone", "purple_exercise", "attack_step", "defense_observation",
    "detection_ticket", "vulnerability", "vulnerability_enrichment",
    "remediation_ticket", "deliverable",
    "evidence", "evidence_access", "audit_dek",
]

# Tables SANS client_id (catalogue global CTI + référentiels + sécurité).
CLIENT_UNSCOPED_TABLES = [
    "scenario", "scenario_step", "corpus_article", "sla_rule",
    "ref_attack_technique", "ref_d3fend", "ref_owasp", "ref_cwe", "ref_capec",
    "ref_attack_group", "ref_misp_actor",
    "app_user", "refresh_token", "journal",
]
