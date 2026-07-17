"""Entités métier — transposition du modèle IndexedDB de la maquette (DAT §2.3, cahier §2).

Groupes : référentiel client · activité d'audit · purple/cycle · vulnérabilités/VOC ·
connaissance CTI (hors RLS client) · référentiels · livrables & corpus.

Toutes les tables à `client_id` reçoivent une politique RLS (posée par la migration ;
aucune exception « temporaire » — DAT §2.2 règle 1). Les scénarios/étapes CTI sont la
SEULE famille hors RLS client (catalogue global v4.1).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


def _uuid_fk(target: str, **kw):
    return mapped_column(PgUUID(as_uuid=True), ForeignKey(target), **kw)


# ── Référentiel client ───────────────────────────────────────────────────────
class Organisation(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "organisation"

    nom: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)  # code court (arborescence S3)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # client|prestataire|interne
    secteur: Mapped[str | None] = mapped_column(Text)
    contacts: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    tlp_defaut: Mapped[str] = mapped_column(String(16), default="AMBER", server_default=text("'AMBER'"))
    referent_interne: Mapped[str | None] = mapped_column(Text)
    siren: Mapped[str | None] = mapped_column(String(16))
    statut: Mapped[str] = mapped_column(String(16), default="actif", server_default=text("'actif'"))
    tags: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    commentaires: Mapped[str | None] = mapped_column(Text)


class Application(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "application"

    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str | None] = mapped_column(String(64))
    criticite: Mapped[str | None] = mapped_column(String(16))
    stack: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    contact_metier: Mapped[str | None] = mapped_column(Text)
    statut: Mapped[str] = mapped_column(String(16), default="actif", server_default=text("'actif'"))
    exposition: Mapped[str | None] = mapped_column(String(16))  # Interne|DMZ|Externe
    valeur_metier: Mapped[int | None] = mapped_column(Integer)  # 1..5
    tags: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    tlp: Mapped[str] = mapped_column(String(16), default="AMBER", server_default=text("'AMBER'"))


class Ressource(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "ressource"

    organisation_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str | None] = mapped_column(String(32))  # Red|Blue|Purple
    competences: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    contact: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    # Lien vers le compte propriétaire de cette fiche (self-service « Ma fiche »). Nullable :
    # les fiches saisies par un admin ne sont pas rattachées à un compte. Posé uniquement par
    # le routeur /api/profile, jamais par le CRUD générique (absent de writable).
    app_user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, index=True)

    @property
    def client_id(self):  # pour la résolution de scope (via organisation)
        return self.organisation_id


# ── Activité d'audit ─────────────────────────────────────────────────────────
class Audit(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "audit"

    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    nom: Mapped[str] = mapped_column(Text, nullable=False)  # auto-généré, figé
    period: Mapped[str | None] = mapped_column(String(8))
    seq: Mapped[int | None] = mapped_column(Integer)
    categorie: Mapped[str] = mapped_column(String(16), nullable=False)  # Red|Purple|Pentest|BAS
    type_test: Mapped[str | None] = mapped_column(String(16))
    scenario_id: Mapped[uuid.UUID | None] = _uuid_fk("scenario.id", nullable=True)
    applications: Mapped[list] = mapped_column(
        ARRAY(PgUUID(as_uuid=True)), default=list, server_default=text("'{}'::uuid[]")
    )
    # Auditeurs assignés (→ ressource, type humaine). Alimente la lettre d'engagement
    # (cahier §5.A « Auditeurs assignés ») ; pas de FK ARRAY en PG, validé applicativement.
    auditeurs: Mapped[list] = mapped_column(
        ARRAY(PgUUID(as_uuid=True)), default=list, server_default=text("'{}'::uuid[]")
    )
    environnement: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    date_debut: Mapped[date | None] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date)
    statut: Mapped[str] = mapped_column(String(16), default="planifie", server_default=text("'planifie'"))
    budget: Mapped[float | None] = mapped_column(Numeric(12, 2))
    priorite: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(Text)
    tlp: Mapped[str] = mapped_column(String(16), default="AMBER", server_default=text("'AMBER'"))
    engagement: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))  # bloc PTES + NDA
    jalons: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    referentiels_methodo: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))


class AuditAction(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "audit_action"

    audit_id: Mapped[uuid.UUID] = _uuid_fk("audit.id", nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    ptes_phase: Mapped[str | None] = mapped_column(String(32))
    titre: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    application_id: Mapped[uuid.UUID | None] = _uuid_fk("application.id", nullable=True)
    auditeur_id: Mapped[uuid.UUID | None] = _uuid_fk("ressource.id", nullable=True)
    technique_attack: Mapped[str | None] = mapped_column(String(16))
    outil: Mapped[str | None] = mapped_column(Text)
    horodatage_debut: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    horodatage_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resultat: Mapped[str | None] = mapped_column(String(16))  # succès|échec|partiel|info
    vulnerabilite_id: Mapped[uuid.UUID | None] = _uuid_fk("vulnerability.id", nullable=True)
    statut: Mapped[str] = mapped_column(String(16), default="ouvert", server_default=text("'ouvert'"))
    attack_chain_step_id: Mapped[uuid.UUID | None] = _uuid_fk("attack_step.id", nullable=True)


class AuditMilestone(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "audit_milestone"

    audit_id: Mapped[uuid.UUID] = _uuid_fk("audit.id", nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    ptes_phase: Mapped[str] = mapped_column(String(32), nullable=False)
    statut: Mapped[str] = mapped_column(String(16), default="a_venir", server_default=text("'a_venir'"))
    date_prevue: Mapped[date | None] = mapped_column(Date)
    date_reelle: Mapped[date | None] = mapped_column(Date)
    livrable: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


# ── Purple / cycle ───────────────────────────────────────────────────────────
class PurpleExercise(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "purple_exercise"

    audit_id: Mapped[uuid.UUID] = _uuid_fk("audit.id", nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    period: Mapped[str | None] = mapped_column(String(8))
    seq: Mapped[int | None] = mapped_column(Integer)
    equipe: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    date: Mapped[date | None] = mapped_column(Date)
    statut: Mapped[str] = mapped_column(String(16), default="planifie", server_default=text("'planifie'"))
    tlp: Mapped[str] = mapped_column(String(16), default="AMBER", server_default=text("'AMBER'"))
    notes: Mapped[str | None] = mapped_column(Text)
    run_number: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))


class AttackStep(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attack_step"

    exercise_id: Mapped[uuid.UUID] = _uuid_fk("purple_exercise.id", nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    technique: Mapped[str | None] = mapped_column(String(16))
    titre: Mapped[str | None] = mapped_column(Text)
    horodatage: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    horodatage_detection: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    horodatage_reponse: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verdict: Mapped[str] = mapped_column(String(16), default="not_tested", server_default=text("'not_tested'"))
    # prevented|alerted|logged|no_telemetry|not_tested


class DefenseObservation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "defense_observation"

    attack_step_id: Mapped[uuid.UUID] = _uuid_fk("attack_step.id", nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(Text)
    resultat: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


class DetectionTicket(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "detection_ticket"

    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    # Référence métier auto-générée et figée : TICK_{AAAAMM}-{NN}_{CLIENT}_{APP}_{TECHNIQUE}
    # (client/app de l'audit lié via source_attack_step_id). period/seq figés à la création.
    reference: Mapped[str | None] = mapped_column(Text)
    period: Mapped[str | None] = mapped_column(String(8))
    seq: Mapped[int | None] = mapped_column(Integer)
    source_attack_step_id: Mapped[uuid.UUID | None] = _uuid_fk("attack_step.id", nullable=True)
    technique_attack: Mapped[str | None] = mapped_column(String(16))
    mesure_d3fend: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    description: Mapped[str | None] = mapped_column(Text)
    priorite: Mapped[str | None] = mapped_column(String(8))
    statut: Mapped[str] = mapped_column(String(16), default="ouvert", server_default=text("'ouvert'"))
    regle_sigma: Mapped[str | None] = mapped_column(Text)
    valide_par: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True)
    valide_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gap_decouvert_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ── Vulnérabilités / VOC ─────────────────────────────────────────────────────
class Vulnerability(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "vulnerability"

    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    audit_id: Mapped[uuid.UUID | None] = _uuid_fk("audit.id", nullable=True, index=True)
    titre: Mapped[str] = mapped_column(Text, nullable=False)  # auto-généré
    period: Mapped[str | None] = mapped_column(String(8))
    seq: Mapped[int | None] = mapped_column(Integer)
    cve: Mapped[str | None] = mapped_column(String(32))
    cwe: Mapped[str | None] = mapped_column(String(32))
    severite: Mapped[str | None] = mapped_column(String(16))
    cvss_score: Mapped[float | None] = mapped_column(Numeric(4, 1))
    cvss_vector: Mapped[str | None] = mapped_column(Text)
    statut: Mapped[str] = mapped_column(String(24), default="ouverte", server_default=text("'ouverte'"))
    decouvreur: Mapped[str | None] = mapped_column(Text)  # historique — non édité (cf. decouvreur_id)
    decouvreur_id: Mapped[uuid.UUID | None] = _uuid_fk("ressource.id", nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    recommandation: Mapped[str | None] = mapped_column(Text)
    applications: Mapped[list] = mapped_column(
        ARRAY(PgUUID(as_uuid=True)), default=list, server_default=text("'{}'::uuid[]")
    )
    techniques: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    d3fend: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    owasp_top10: Mapped[str | None] = mapped_column(String(16))
    phase_decouverte: Mapped[str | None] = mapped_column(String(32))
    exploitabilite: Mapped[str | None] = mapped_column(String(16))
    preuve_exploitation: Mapped[str | None] = mapped_column(Text)
    impact_metier: Mapped[str | None] = mapped_column(Text)
    sla_niveau: Mapped[str | None] = mapped_column(String(8))  # P1..P4 dérivé
    sla_echeance: Mapped[date | None] = mapped_column(Date)
    tlp: Mapped[str] = mapped_column(String(16), default="RED", server_default=text("'RED'"))
    valide_par: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True)
    valide_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VulnerabilityEnrichment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "vulnerability_enrichment"

    vulnerability_id: Mapped[uuid.UUID] = _uuid_fk("vulnerability.id", nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    epss_score: Mapped[float | None] = mapped_column(Numeric(6, 5))
    epss_percentile: Mapped[float | None] = mapped_column(Numeric(6, 5))
    epss_date: Mapped[date | None] = mapped_column(Date)
    kev: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    kev_date_added: Mapped[date | None] = mapped_column(Date)
    kev_due_date: Mapped[date | None] = mapped_column(Date)
    kev_ransomware: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    ssvc_decision: Mapped[str | None] = mapped_column(String(16))
    vex_status: Mapped[str | None] = mapped_column(String(24))
    enrichment_status: Mapped[str | None] = mapped_column(String(16))
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enrichment_source: Mapped[str | None] = mapped_column(Text)
    # Cache du sous-ensemble CIRCL sans colonne dédiée (CAPEC, références, produits,
    # variantes CVSS) → disponible hors-ligne après le premier appel (cahier §6, A.2).
    raw: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class RemediationTicket(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "remediation_ticket"

    vulnerability_id: Mapped[uuid.UUID] = _uuid_fk("vulnerability.id", nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    statut: Mapped[str] = mapped_column(String(24), default="ouvert", server_default=text("'ouvert'"))
    echeance: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class SlaRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sla_rule"

    client_id: Mapped[uuid.UUID | None] = _uuid_fk("organisation.id", nullable=True, index=True)
    niveau: Mapped[str] = mapped_column(String(8), nullable=False)  # P1..P4
    condition: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    delai_jours: Mapped[int] = mapped_column(Integer, default=90, server_default=text("90"))


# ── Connaissance CTI (SANS client_id — catalogue global, hors RLS client) ────
class Scenario(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "scenario"

    nom: Mapped[str] = mapped_column(Text, nullable=False)  # descriptif, saisi (ex. « Émulation FIN7 »)
    # Référence métier auto-générée et figée : SCEN_{AAAAMM}-{NN} (catalogue CTI global, sans client).
    reference: Mapped[str | None] = mapped_column(Text)
    period: Mapped[str | None] = mapped_column(String(8))
    seq: Mapped[int | None] = mapped_column(Integer)
    objectif: Mapped[str | None] = mapped_column(Text)
    acteur_emule: Mapped[str | None] = mapped_column(Text)
    type_engagement: Mapped[str | None] = mapped_column(String(16))
    sophistication: Mapped[str | None] = mapped_column(String(16))
    ioc: Mapped[str | None] = mapped_column(Text)
    ioa: Mapped[str | None] = mapped_column(Text)
    references: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    credibilite: Mapped[int | None] = mapped_column(Integer)  # 1..6 (Admiralty)
    techniques: Mapped[list] = mapped_column(  # dérivé des étapes
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    d3fend: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    tlp: Mapped[str] = mapped_column(String(16), default="AMBER", server_default=text("'AMBER'"))
    pap: Mapped[str] = mapped_column(String(16), default="AMBER", server_default=text("'AMBER'"))
    notes: Mapped[str | None] = mapped_column(Text)


class ScenarioStep(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scenario_step"

    scenario_id: Mapped[uuid.UUID] = _uuid_fk("scenario.id", nullable=False, index=True)
    ordre: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    technique: Mapped[str | None] = mapped_column(String(16))
    tactique: Mapped[str | None] = mapped_column(String(32))
    commande: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


# ── Livrables & corpus ───────────────────────────────────────────────────────
class Deliverable(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "deliverable"

    client_id: Mapped[uuid.UUID] = _uuid_fk("organisation.id", nullable=False, index=True)
    audit_id: Mapped[uuid.UUID | None] = _uuid_fk("audit.id", nullable=True)
    type: Mapped[str] = mapped_column(String(24), nullable=False)  # engagement|nda|rapport
    titre: Mapped[str | None] = mapped_column(Text)
    langue: Mapped[str] = mapped_column(String(4), default="fr", server_default=text("'fr'"))
    tlp: Mapped[str] = mapped_column(String(16), default="AMBER", server_default=text("'AMBER'"))
    statut: Mapped[str] = mapped_column(String(16), default="genere", server_default=text("'genere'"))
    storage_key: Mapped[str | None] = mapped_column(Text)  # PDF rendu (bucket livrables)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class CorpusArticle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "corpus_article"

    slug: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    nature: Mapped[str] = mapped_column(String(16), nullable=False)  # procedure|processus|metier
    profils: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    titre_fr: Mapped[str] = mapped_column(Text, nullable=False)
    titre_en: Mapped[str | None] = mapped_column(Text)
    contenu: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))  # bilingue structuré
    controles_iso: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    gabarit: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
