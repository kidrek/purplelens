"""Schémas du sous-système de preuves (cahier §6quater)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class EvidenceInitRequest(BaseModel):
    """Déclaration d'une preuve avant dépôt (le binaire ne transite JAMAIS par l'API).

    Le serveur crée la ligne `evidence` en statut `quarantined`, provisionne la DEK
    d'audit si besoin, puis renvoie une URL présignée d'upload vers le bucket de
    quarantaine. Le sas (worker) prend le relais après le PUT client.
    """

    audit_id: UUID
    client_id: UUID
    original_filename: str = Field(min_length=1, max_length=512)
    declared_mime: str | None = None
    size_bytes: int = Field(gt=0, le=209_715_200)  # MAX_EVIDENCE_BYTES = 200 Mio
    finding_id: UUID | None = None
    audit_action_id: UUID | None = None
    attack_step_id: UUID | None = None
    tlp: str = "RED"
    pap: str = "RED"
    contains_pii: bool = False
    contains_secrets: bool = False
    caption: str | None = None


class PresignedUpload(BaseModel):
    evidence_id: UUID
    upload_url: str
    object_key: str
    bucket: str
    expires_in: int
    method: str = "PUT"


class PresignedDownload(BaseModel):
    evidence_id: UUID
    download_url: str
    expires_in: int
    tlp: str
    pap: str
    masked: bool = False  # true si contains_secrets et rendu → jamais d'URL directe


class EvidenceOut(ORMModel):
    id: UUID
    audit_id: UUID
    client_id: UUID
    original_filename: str
    detected_mime: str | None = None
    size_bytes: int | None = None
    sha256_plaintext: str | None = None
    tlp: str
    pap: str
    contains_pii: bool
    contains_secrets: bool
    caption: str | None = None
    ingest_status: str
    rejected_reason: str | None = None
    av_verdict: str | None = None
    uploaded_at: datetime
    stored_at: datetime | None = None
    retention_until: datetime | None = None
    legal_hold: bool


class CustodyChain(BaseModel):
    """Vue chaîne de possession (custody) reconstituée depuis evidence + journal."""

    evidence_id: UUID
    original_filename: str
    sha256_plaintext: str | None
    sha256_ciphertext: str | None
    ingest_status: str
    uploaded_by: UUID | None
    uploaded_at: datetime
    stored_at: datetime | None
    journal_entry_id: UUID | None
    encryption_alg: str
    object_lock_until: datetime | None
    accesses: list[AccessEntry]


class AccessEntry(BaseModel):
    purpose: str
    granted: bool
    denial_reason: str | None = None
    actor_user_id: UUID | None = None
    created_at: datetime


CustodyChain.model_rebuild()
