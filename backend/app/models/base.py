"""Base déclarative et mixins communs (DAT §2.3).

Convention : UUID partout, created_at/updated_at, soft delete (deleted_at) sur les
entités métier — suppression non destructive (cahier v3.2). La suppression réelle est
réservée au crypto-shredding des preuves.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    # server_default en plus du défaut Python : les INSERT SQL bruts (journal, sas
    # d'ingestion, seed) qui omettent `id` obtiennent un UUID côté base.
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True,
        default=uuid.uuid4, server_default=text("gen_random_uuid()"),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    # default= côté Python (en plus du server_default) : évite que SQLAlchemy n'ajoute
    # un RETURNING implicite pour relire ces colonnes après l'INSERT. Pour les tables
    # dont la colonne de cloisonnement RLS est leur propre id (ex. organisation), ce
    # RETURNING exige aussi que la ligne neuve satisfasse la politique SELECT — hors
    # d'atteinte par construction pour une ligne qui vient de naître.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        server_default=func.now(), server_onupdate=func.now(), nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
