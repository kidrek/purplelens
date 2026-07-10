"""Entités de sécurité : app_user, refresh_token, journal (spec backend v2 §2 / §6)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class AppUser(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "app_user"

    external_sub: Mapped[str | None] = mapped_column(Text, nullable=True)  # 'sub' OIDC
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # admin|manager|ciso|auditeur|voc|cert
    # clients rattachés ; [] = tous clients (selon droits du rôle)
    client_scope: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PgUUID(as_uuid=True)), default=list, server_default=text("'{}'::uuid[]"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="active", server_default=text("'active'"), nullable=False)
    mfa_enrolled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    # Repli comptes locaux (Argon2id) — désactivés par défaut
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshToken(UUIDMixin, Base):
    __tablename__ = "refresh_token"

    user_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(  # active|rotated|revoked
        String(16), default="active", server_default=text("'active'"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Journal(Base):
    """Journal tamper-evident — INSERT only (immutabilité par trigger)."""

    __tablename__ = "journal"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), default=uuid.uuid4,
        server_default=text("gen_random_uuid()"), unique=True, nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    actor_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    curr_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
