"""Profil self-service — « Ma fiche ».

Un compte opérationnel (operateur/auditeur, mais aussi ciso/voc/cert…) est autonome sur
la chaîne scénario→audit→exercice mais ne peut se sélectionner comme auditeur d'un audit
tant qu'il n'existe pas de **ressource** (type humaine) le représentant : le picker
« Auditeurs assignés » liste des ressources, pas des comptes. Ce routeur laisse
l'utilisateur créer/éditer **sa propre** fiche ressource, liée par `ressource.app_user_id`,
dans une organisation de son périmètre. `ressource` reste la source unique (compétences,
contact) réutilisée par la validation d'audit et la lettre d'engagement.

Capacité self-service bornée par le périmètre client (porte 4 + RLS `WITH CHECK`), et non
par la matrice `ressources:C` — éditer sa propre fiche n'est pas gérer l'inventaire des
ressources du client. On force `type='humaine'` et `app_user_id = moi` côté serveur.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.session import rls_session
from app.journal.chain import append as journal_append
from app.models.business import Ressource
from app.security.context import SecurityContext
from app.security.rbac import get_security_context

router = APIRouter(prefix="/api/profile", tags=["profile"])


class MyResourceIn(BaseModel):
    organisation_id: uuid.UUID
    nom: str = Field(min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=32)
    competences: list[str] = Field(default_factory=list)
    contact: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


def _serialize(r: Ressource) -> dict:
    return {
        "id": str(r.id), "organisation_id": str(r.organisation_id), "app_user_id": str(r.app_user_id),
        "nom": r.nom, "type": r.type, "role": r.role, "competences": r.competences or [],
        "contact": r.contact, "description": r.description, "tags": r.tags or [],
    }


def _org_in_scope(ctx: SecurityContext, org: uuid.UUID) -> bool:
    # Les rôles multi-clients (admin/manager) opèrent de droit sur toutes les organisations ;
    # sinon l'organisation doit figurer dans le périmètre du token.
    return ctx.is_multi_client or str(org) in {str(c) for c in ctx.client_scope}


@router.get("/resources")
async def my_resources(ctx: SecurityContext = Depends(get_security_context)):
    """Mes fiches ressource liées (au plus une par organisation de mon périmètre)."""
    me = uuid.UUID(ctx.user_id)
    async with rls_session(user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope) as s:
        rows = (await s.execute(
            select(Ressource).where(Ressource.app_user_id == me).order_by(Ressource.nom)
        )).scalars().all()
        return {"resources": [_serialize(r) for r in rows]}


@router.put("/resource")
async def upsert_my_resource(
    body: MyResourceIn, ctx: SecurityContext = Depends(get_security_context)
):
    """Crée ou met à jour ma fiche pour une organisation de mon périmètre.

    Upsert par (app_user_id, organisation_id) ; `type` et `app_user_id` sont imposés par
    le serveur (jamais depuis le corps)."""
    me = uuid.UUID(ctx.user_id)
    org = body.organisation_id
    if not _org_in_scope(ctx, org):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="organisation_out_of_scope")
    async with rls_session(user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope) as s:
        existing = (await s.execute(select(Ressource).where(
            Ressource.app_user_id == me, Ressource.organisation_id == org
        ))).scalar_one_or_none()
        fields = dict(nom=body.nom, role=body.role, competences=body.competences,
                      contact=body.contact, description=body.description, tags=body.tags)
        if existing is not None:
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.type = "humaine"
            obj, event = existing, "profile.resource.update"
        else:
            obj = Ressource(organisation_id=org, app_user_id=me, type="humaine", **fields)
            s.add(obj)
            event = "profile.resource.create"
        await s.flush()
        await journal_append(
            s, event_type=event, actor_id=ctx.user_id, client_id=str(org), subject=str(obj.id),
            detail={"organisation_id": str(org)},
        )
        return _serialize(obj)
