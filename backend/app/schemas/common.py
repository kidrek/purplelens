"""Schémas transverses (Pydantic v2)."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base des schémas de sortie : lecture directe depuis les objets ORM."""

    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    """Enveloppe de liste paginée."""

    items: list[T]
    total: int
    limit: int
    offset: int


class Message(BaseModel):
    message: str


class WritePayload(BaseModel):
    """Corps générique de création/édition.

    On accepte un dictionnaire libre : la validation métier (liste blanche des
    champs autorisés) est appliquée côté service à partir du registre d'entités,
    pas ici, afin de garder une seule source de vérité (`registry.writable`).
    """

    model_config = ConfigDict(extra="allow")

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class HealthStatus(BaseModel):
    status: str = "ok"
    checks: dict[str, str] = Field(default_factory=dict)
