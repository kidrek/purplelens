"""Modèles ORM des preuves (miroir de schema_evidence.sql) et référentiels.

Le DDL SQL fait foi (contraintes/triggers/RLS). Ces classes servent l'ORM applicatif.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class AuditDek(UUIDMixin, Base):
    __tablename__ = "audit_dek"

    audit_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    wrapped_dek: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    kek_ref: Mapped[str] = mapped_column(Text, nullable=False)
    kek_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="active")
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    destroyed_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    destroyed_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    finding_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    audit_action_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    attack_step_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    declared_mime: Mapped[str | None] = mapped_column(Text)
    detected_mime: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256_plaintext: Mapped[str | None] = mapped_column(String(64))
    sha256_ciphertext: Mapped[str | None] = mapped_column(String(64))
    bucket: Mapped[str | None] = mapped_column(Text)
    object_key: Mapped[str | None] = mapped_column(Text)
    thumbnail_key: Mapped[str | None] = mapped_column(Text)
    dek_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("audit_dek.id"))
    nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
    encryption_alg: Mapped[str] = mapped_column(Text, default="AES-256-GCM")
    aad_fields: Mapped[str] = mapped_column(Text, default="id+audit_id+sha256_plaintext")
    tlp: Mapped[str] = mapped_column(String(16), default="RED")
    pap: Mapped[str] = mapped_column(String(16), default="RED")
    contains_pii: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_secrets: Mapped[bool] = mapped_column(Boolean, default=False)
    caption: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    ingest_status: Mapped[str] = mapped_column(String(16), default="quarantined")
    rejected_reason: Mapped[str | None] = mapped_column(Text)
    av_verdict: Mapped[str | None] = mapped_column(Text)
    av_engine_version: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    object_lock_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceAccess(UUIDMixin, Base):
    __tablename__ = "evidence_access"

    evidence_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("evidence.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    actor_label: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    denial_reason: Mapped[str | None] = mapped_column(Text)
    presigned_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ── Référentiels de sécurité (synchronisés serveur — DAT §2.3) ───────────────
class _RefBase(UUIDMixin, TimestampMixin):
    # ext_id est la clé naturelle du référentiel (T1566, D3-UAC…) : unique par table.
    # Rend seed_reference réellement idempotent (ON CONFLICT DO NOTHING).
    ext_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)


class RefAttackTechnique(_RefBase, Base):
    __tablename__ = "ref_attack_technique"
    tactic: Mapped[str | None] = mapped_column(String(64))


class RefD3fend(_RefBase, Base):
    __tablename__ = "ref_d3fend"
    category: Mapped[str | None] = mapped_column(String(32))


class RefOwasp(_RefBase, Base):
    __tablename__ = "ref_owasp"


class RefCwe(_RefBase, Base):
    __tablename__ = "ref_cwe"


class RefCapec(_RefBase, Base):
    __tablename__ = "ref_capec"
