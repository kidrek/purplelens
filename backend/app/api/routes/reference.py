"""Référentiels de sécurité — consultation et import (cahier §, vue Paramètres).

Lister l'état des catalogues est ouvert à tout compte authentifié (données globales,
non sensibles). L'import/actualisation peuple les tables `ref_*` et est réservé à
l'administrateur (action de configuration). Idempotent (ext_id unique, migration 0002).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.db.session import service_session
from app.journal.chain import append as journal_append
from app.reference.catalogs import catalog_stats, import_catalog
from app.security.context import SecurityContext
from app.security.rbac import get_security_context

router = APIRouter(prefix="/api/reference", tags=["reference"])


@router.get("/catalogs")
async def list_catalogs(ctx: SecurityContext = Depends(get_security_context)):
    """État des catalogues : entrées en base, source, dernière mise à jour."""
    async with service_session("admin_service") as session:
        return {"catalogs": await catalog_stats(session)}


@router.get("/{catalog_id}/entries")
async def catalog_entries(catalog_id: str, ctx: SecurityContext = Depends(get_security_context)):
    """Entrées d'un catalogue (depuis la base) pour l'autocomplétion des formulaires.
    Ouvert à tout compte authentifié : données globales, non sensibles."""
    from sqlalchemy import text as _text

    from app.reference.catalogs import CATALOGS

    cat = next((c for c in CATALOGS if c["id"] == catalog_id), None)
    if cat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="unknown_catalog")
    cols = "ext_id, name" + (", tactic" if cat["has_tactic"] else "") + (", category" if cat.get("has_category") else "")
    async with service_session("admin_service") as session:
        rows = (await session.execute(
            _text(f"SELECT {cols} FROM {cat['table']} ORDER BY ext_id")
        )).mappings().all()
    return {"catalog": catalog_id, "entries": [dict(r) for r in rows]}


@router.post("/{catalog_id}/import")
async def import_one(catalog_id: str, ctx: SecurityContext = Depends(get_security_context)):
    """(Ré)importe un catalogue depuis le socle embarqué. Admin uniquement."""
    if ctx.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    async with service_session("admin_service") as session:
        try:
            n = await import_catalog(session, catalog_id)
        except KeyError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="unknown_catalog") from None
        await journal_append(
            session, event_type="reference.imported", actor_id=ctx.user_id,
            subject=catalog_id, detail={"entries": n},
        )
    return {"id": catalog_id, "entries": n}


@router.post("/{catalog_id}/sync")
async def sync_online(catalog_id: str, ctx: SecurityContext = Depends(get_security_context)):
    """Synchronise un catalogue depuis la source amont MITRE (ATT&CK/D3FEND). Admin.

    Récupère le catalogue complet en ligne (≈700 techniques ATT&CK) et l'upsert.
    Dégradation gracieuse : si la source est injoignable, on retombe sur le socle
    embarqué et on le signale (statut « fallback »).
    """
    if ctx.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    from app.reference.sync import SYNCABLE, SyncUnavailable, sync_catalog

    if catalog_id not in SYNCABLE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="not_syncable")
    async with service_session("admin_service") as session:
        try:
            n = await sync_catalog(session, catalog_id)
            source = "upstream"
        except SyncUnavailable:
            # Source amont indisponible → socle embarqué.
            n = await import_catalog(session, catalog_id)
            source = "fallback"
        await journal_append(
            session, event_type="reference.synced", actor_id=ctx.user_id,
            subject=catalog_id, detail={"entries": n, "source": source},
        )
    return {"id": catalog_id, "entries": n, "source": source}


@router.get("/d3fend/suggest")
async def suggest_d3fend_endpoint(
    techniques: str = "", ctx: SecurityContext = Depends(get_security_context)
):
    """Contre-mesures D3FEND suggérées pour un ensemble de techniques ATT&CK
    (paramètre `techniques` = liste d'ext_id séparés par des virgules, ex. T1190,T1566).
    Socle de correspondance volontairement partiel — cf. reference/attack_d3fend.py.
    En pratique le champ `d3fend` des Vulnérabilités/Scénarios est déjà calculé
    serveur à l'écriture (service.py) ; cet endpoint sert l'aperçu live du formulaire
    et le regroupement par technique affiché dans le drawer Scénario (cahier §0.8)."""
    from app.reference.attack_d3fend import suggest_d3fend

    ids = [t.strip().upper() for t in techniques.split(",") if t.strip()]
    by_technique = {t: suggest_d3fend([t]) for t in ids}
    return {"techniques": ids, "suggestions": suggest_d3fend(ids), "by_technique": by_technique}


@router.post("/import-all")
async def import_all(ctx: SecurityContext = Depends(get_security_context)):
    """(Ré)importe tous les catalogues. Admin uniquement."""
    if ctx.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    from app.reference.catalogs import CATALOGS

    result = {}
    async with service_session("admin_service") as session:
        for cat in CATALOGS:
            result[cat["id"]] = await import_catalog(session, cat["id"])
        await journal_append(
            session, event_type="reference.imported", actor_id=ctx.user_id,
            subject="all", detail={"catalogs": len(result)},
        )
    return {"imported": result}
