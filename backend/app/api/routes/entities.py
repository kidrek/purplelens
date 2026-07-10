"""Routeur CRUD générique — une famille de routes par entité du registre.

Chaque route :
  1. exige la permission de matrice via `require(entity, action)` (porte 3, 403 net) ;
  2. ouvre une `rls_session` portant le contexte de sécurité → la RLS PostgreSQL
     (couche 2) restreint automatiquement les lignes visibles au périmètre client ;
  3. délègue au service générique, qui journalise l'opération.

Aucune décision d'autorisation n'est laissée au client (invariant DAT §2.2).
"""
from __future__ import annotations

import uuid

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError

from app.api import service
from app.api.registry import REGISTRY, EntitySpec
from app.db.session import rls_session
from app.security.context import SecurityContext
from app.security.matrix import Action
from app.security.rbac import can, require

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["entities"])


def _serialize(obj) -> dict:
    """Sérialisation ORM → dict simple (colonnes mappées uniquement)."""
    from sqlalchemy import inspect as sa_inspect

    data = {}
    for col in sa_inspect(obj).mapper.column_attrs:
        data[col.key] = getattr(obj, col.key)
    return data


async def _provision_client_bucket(code: str | None) -> None:
    """Crée le bucket MinIO du client (Object Lock à la création — cf. storage/
    minio_client.py) juste après la création de son organisation. Sans ce hook,
    toute génération de livrable ou dépôt de preuve pour ce client échoue avec
    NoSuchBucket — le bootstrap ne provisionnait que la quarantaine (§ historique
    « créé à la volée » jamais implémenté). Non bloquant : un incident MinIO ne
    doit pas empêcher la création de la fiche organisation ; rattrapable ensuite
    via `python -m app.storage.bootstrap`.
    """
    if not code:
        return
    try:
        from app.storage import minio_client

        minio_client.ensure_buckets([code])
    except Exception:  # pragma: no cover
        _log.error(
            "provisioning MinIO échoué pour l'organisation %s — bucket manquant, "
            "relancer `python -m app.storage.bootstrap`", code, exc_info=True
        )


def _register(spec: EntitySpec) -> None:
    entity = spec.entity

    @router.get(f"/{entity}", name=f"list_{entity}")
    async def _list(
        request: Request,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        ctx: SecurityContext = Depends(require(entity, Action.L)),
    ):
        # Filtres : seuls les paramètres de requête correspondant à une colonne
        # déclarée `filterable` sont retenus (le reste est ignoré).
        filters = {
            k: v for k, v in request.query_params.items()
            if k in spec.filterable
        }
        async with rls_session(
            user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
        ) as session:
            rows, total = await service.list_entities(
                session, spec, limit=limit, offset=offset, filters=filters
            )
            items = [_serialize(r) for r in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @router.get(f"/{entity}/{{item_id}}", name=f"get_{entity}")
    async def _get(
        item_id: uuid.UUID,
        ctx: SecurityContext = Depends(require(entity, Action.L)),
    ):
        async with rls_session(
            user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
        ) as session:
            obj = await service.get_entity(session, spec, item_id)
            if obj is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
            return _serialize(obj)

    # Création — uniquement si la matrice accorde C à au moins un rôle sur l'entité.
    @router.post(f"/{entity}", status_code=status.HTTP_201_CREATED, name=f"create_{entity}")
    async def _create(
        payload: dict,
        ctx: SecurityContext = Depends(require(entity, Action.C)),
    ):
        # Porte 4 fine : le client déclaré doit appartenir au périmètre de l'appelant.
        _enforce_scope_on_write(spec, payload, ctx)
        try:
            async with rls_session(
                user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
            ) as session:
                obj = await service.create_entity(session, spec, payload, actor_id=ctx.user_id)
                await session.flush()
                result = _serialize(obj)
        except IntegrityError as exc:
            # Doctrine : jamais de 500 opaque ; détail précis côté serveur seulement
            # (DAT §2.4 — la réponse ne porte pas d'information exploitable).
            _log.warning("integrity violation on %s.create: %s", entity, exc.orig)
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail="constraint_violation"
            ) from None
        if entity == "organisations":
            await _provision_client_bucket(result.get("code"))
        return result

    @router.put(f"/{entity}/{{item_id}}", name=f"update_{entity}")
    async def _update(
        item_id: uuid.UUID,
        payload: dict,
        ctx: SecurityContext = Depends(require(entity, Action.E)),
    ):
        async with rls_session(
            user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
        ) as session:
            obj = await service.get_entity(session, spec, item_id)
            if obj is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
            try:
                obj = await service.update_entity(session, spec, obj, payload, actor_id=ctx.user_id)
                await session.flush()
            except IntegrityError as exc:
                _log.warning("integrity violation on %s.update: %s", entity, exc.orig)
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, detail="constraint_violation"
                ) from None
            return _serialize(obj)

    @router.delete(f"/{entity}/{{item_id}}", status_code=status.HTTP_204_NO_CONTENT,
                   name=f"delete_{entity}")
    async def _delete(
        item_id: uuid.UUID,
        ctx: SecurityContext = Depends(require(entity, Action.S)),
    ):
        async with rls_session(
            user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
        ) as session:
            obj = await service.get_entity(session, spec, item_id)
            if obj is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
            await service.delete_entity(session, spec, obj, actor_id=ctx.user_id)
        return None


def _enforce_scope_on_write(spec: EntitySpec, payload: dict, ctx: SecurityContext) -> None:
    """Porte 4 sur écriture : empêche de créer une ligne pour un client hors périmètre.

    La RLS bloquerait déjà l'INSERT (policy WITH CHECK), mais un refus applicatif
    explicite donne un 403 lisible plutôt qu'une erreur base opaque.
    """
    if spec.client_field is None or spec.client_field == "id":
        return
    declared = payload.get(spec.client_field)
    if declared is None:
        return
    record = {"client_id": str(declared)}
    decision = can(ctx, Action.C, spec.entity, record)
    if not decision.allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")


for _spec in REGISTRY.values():
    _register(_spec)
