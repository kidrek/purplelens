from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.enums import (
    AuditStatus,
    AuditType,
    Exposure,
    FindingEventType,
    FindingStatus,
    Severity,
)

# ---------------------------------------------------------------------------
# Tables d'association
# ---------------------------------------------------------------------------

# Un scénario CTI couvre plusieurs techniques ATT&CK (et inversement).
scenario_technique = Table(
    "scenario_technique",
    Base.metadata,
    Column("scenario_id", ForeignKey("scenarios.id"), primary_key=True),
    Column("technique_id", ForeignKey("techniques.id"), primary_key=True),
)

# Un audit rejoue un ou plusieurs scénarios CTI.
audit_scenario = Table(
    "audit_scenario",
    Base.metadata,
    Column("audit_id", ForeignKey("audits.id"), primary_key=True),
    Column("scenario_id", ForeignKey("scenarios.id"), primary_key=True),
)


# ---------------------------------------------------------------------------
# Module 1 — Référentiel des applications (objet central)
# ---------------------------------------------------------------------------
class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, default="")
    owner = Column(String, default="")          # Responsable
    team = Column(String, default="")           # Equipe
    email = Column(String, default="")
    phone = Column(String, default="")
    exposure = Column(Enum(Exposure), default=Exposure.interne)
    technologies = Column(String, default="")   # libellé lisible CSV (ex: "Nginx, PostgreSQL")
    technologies_cpe = Column(Text, default="") # JSON array [{cpe, vendor, product}, …]
    url = Column(String, default="")
    scope_red_team = Column(Text, default="")
    scope_pentest = Column(Text, default="")

    # Criticité DIC (1 à 5)
    dic_availability = Column(Integer, default=3)   # Disponibilité
    dic_integrity = Column(Integer, default=3)      # Intégrité
    dic_confidentiality = Column(Integer, default=3)  # Confidentialité

    created_at = Column(DateTime, default=datetime.utcnow)

    audits = relationship("Audit", back_populates="application", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="application")


# ---------------------------------------------------------------------------
# Module 2 — Base CTI : techniques MITRE + scénarios de menace
# ---------------------------------------------------------------------------
class Technique(Base):
    """Technique MITRE ATT&CK (T1566, T1059, ...)."""

    __tablename__ = "techniques"

    id = Column(Integer, primary_key=True)
    mitre_id = Column(String, unique=True, index=True)  # ex. T1566
    name = Column(String, default="")
    tactic = Column(String, default="")  # ex. Initial Access

    scenarios = relationship(
        "Scenario", secondary=scenario_technique, back_populates="techniques"
    )


class Scenario(Base):
    """Scénario de menace créé par le CTI.

    Décrit une chaîne d'attaque (kill-chain) réutilisable lors de la
    planification d'un audit.
    """

    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, default="")
    threat_actor = Column(String, default="")  # ex. APT29, FIN7 (adversaire émulé)
    objective = Column(Text, default="")        # objectif visé
    engagement_type = Column(Enum(AuditType), default=AuditType.purple_team)
    sophistication = Column(String, default="Intermédiaire")  # Fondamental/Intermédiaire/Avancé
    ioc = Column(Text, default="")
    ioa = Column(Text, default="")
    references = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    techniques = relationship(
        "Technique", secondary=scenario_technique, back_populates="scenarios"
    )
    steps = relationship(
        "ScenarioStep", back_populates="scenario",
        cascade="all, delete-orphan", order_by="ScenarioStep.order",
    )
    audits = relationship(
        "Audit", secondary=audit_scenario, back_populates="scenarios"
    )


class ScenarioStep(Base):
    """Étape de la kill-chain d'un scénario : tactique + technique + action."""

    __tablename__ = "scenario_steps"

    id = Column(Integer, primary_key=True)
    scenario_id = Column(ForeignKey("scenarios.id"), nullable=False)
    order = Column(Integer, default=1)
    tactic = Column(String, default="")          # ex. Initial Access
    mitre_id = Column(String, default="")        # ex. T1190
    technique_name = Column(String, default="")  # description courte de la technique
    action = Column(Text, default="")            # commande système / outil
    description = Column(Text, default="")        # action + résultat attendu

    scenario = relationship("Scenario", back_populates="steps")


# ---------------------------------------------------------------------------
# Module 3 — Gestion des audits (cœur du produit)
# ---------------------------------------------------------------------------
class Audit(Base):
    __tablename__ = "audits"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    audit_type = Column(Enum(AuditType), default=AuditType.purple_team)
    status = Column(Enum(AuditStatus), default=AuditStatus.draft)

    application_id = Column(ForeignKey("applications.id"), nullable=False)
    team = Column(String, default="")
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    results = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="audits")
    scenarios = relationship(
        "Scenario", secondary=audit_scenario, back_populates="audits"
    )
    assessments = relationship(
        "DetectionAssessment", back_populates="audit", cascade="all, delete-orphan"
    )
    findings = relationship("Finding", back_populates="audit")
    evidence = relationship("Evidence", back_populates="audit", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Module 4 — Exécution ATT&CK : évaluation détection / réaction
# ---------------------------------------------------------------------------
class DetectionAssessment(Base):
    """Pour une technique jouée pendant un audit : a-t-on détecté ? réagi ?"""

    __tablename__ = "detection_assessments"

    id = Column(Integer, primary_key=True)
    audit_id = Column(ForeignKey("audits.id"), nullable=False)
    technique_id = Column(ForeignKey("techniques.id"), nullable=False)

    detected = Column(Integer, default=0)   # 0/1 — booléen SQLite-friendly
    responded = Column(Integer, default=0)  # 0/1

    # Minutes — alimentent MTTD / MTTR
    detection_time_min = Column(Float, nullable=True)
    response_time_min = Column(Float, nullable=True)

    # Kill-chain : description de l'étape et commande / outil utilisé
    step_description = Column(Text, default="")  # ce qui a été tenté
    command = Column(Text, default="")           # commande / outil (ex. sqlmap …)
    step_order = Column(Integer, nullable=True)  # ordre dans la kill-chain

    notes = Column(Text, default="")

    audit = relationship("Audit", back_populates="assessments")
    technique = relationship("Technique")


# ---------------------------------------------------------------------------
# Module 5 — Gestion des vulnérabilités
# ---------------------------------------------------------------------------
class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    impact = Column(Text, default="")
    cvss = Column(Float, default=0.0)
    severity = Column(Enum(Severity), default=Severity.medium)
    status = Column(Enum(FindingStatus), default=FindingStatus.open)

    # Mapping — stockage dual : libellé court legacy + JSON structuré
    owasp      = Column(String, default="")  # libellé lisible (ex: "A03:2021, A05:2021")
    cwe        = Column(String, default="")  # libellé lisible (ex: "CWE-89, CWE-20")
    capec      = Column(String, default="")  # libellé lisible (ex: "CAPEC-66")
    owasp_refs = Column(Text, default="")    # JSON [{ref_id, name}, …]
    cwe_refs   = Column(Text, default="")    # JSON [{ref_id, name}, …]
    capec_refs = Column(Text, default="")    # JSON [{ref_id, name}, …]

    application_id = Column(ForeignKey("applications.id"), nullable=False)
    audit_id = Column(ForeignKey("audits.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    updated_at = Column(DateTime, nullable=True)

    application = relationship("Application", back_populates="findings")
    audit = relationship("Audit", back_populates="findings")
    events = relationship("FindingEvent", back_populates="finding",
                          cascade="all, delete-orphan", order_by="FindingEvent.created_at")


# ---------------------------------------------------------------------------
# Module 6 — Evidence Vault (métadonnées ; binaire en MinIO/S3)
# ---------------------------------------------------------------------------
class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True)
    audit_id = Column(ForeignKey("audits.id"), nullable=False)
    filename = Column(String, nullable=False)
    kind = Column(String, default="")   # screenshot | log | pcap | payload | script | report
    tags = Column(String, default="")   # CSV
    version = Column(Integer, default=1)
    storage_key = Column(String, default="")  # clé objet S3/MinIO
    sha256 = Column(String, default="")        # intégrité
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    audit = relationship("Audit", back_populates="evidence")


# ---------------------------------------------------------------------------
# Module 5b — Journal des événements de vulnérabilité
# ---------------------------------------------------------------------------
class FindingEvent(Base):
    """Trace chaque changement d'état d'un finding : création, changement de
    statut, fermeture, réouverture, commentaire libre."""

    __tablename__ = "finding_events"

    id         = Column(Integer, primary_key=True)
    finding_id = Column(ForeignKey("findings.id"), nullable=False)
    event_type = Column(Enum(FindingEventType), nullable=False)
    old_status = Column(Enum(FindingStatus), nullable=True)
    new_status = Column(Enum(FindingStatus), nullable=True)
    note       = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    finding = relationship("Finding", back_populates="events")
