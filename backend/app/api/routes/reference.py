"""Référentiels de sécurité — consultation et import (cahier §, vue Paramètres).

Lister l'état des catalogues est ouvert à tout compte authentifié (données globales,
non sensibles). L'import/actualisation peuple les tables `ref_*` et est réservé à
l'administrateur (action de configuration). Idempotent (ext_id unique, migration 0002).
"""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import bindparam
from sqlalchemy import text as _text

from app.db.session import service_session
from app.journal.chain import append as journal_append
from app.reference.catalogs import catalog_stats, import_catalog
from app.security.context import SecurityContext
from app.security.rbac import get_security_context

router = APIRouter(prefix="/api/reference", tags=["reference"])

# Tables des acteurs (threat actors), indexées par le préfixe de `key` exposé côté API :
# "mitre:G0016" → MITRE ATT&CK Groups ; "misp:<id>" → MISP Galaxy threat-actor.
_ACTOR_TABLES = {"mitre": "ref_attack_group", "misp": "ref_misp_actor"}


def _coerce_data(value) -> dict:
    """`data` JSONB peut revenir en dict (ORM) ou en chaîne (SQL brut/asyncpg) — normalise."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return {}
    return value or {}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


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
    cols = (
        "ext_id, name"
        + (", tactic" if cat["has_tactic"] else "")
        + (", category" if cat.get("has_category") else "")
    )
    async with service_session("admin_service") as session:
        rows = (await session.execute(
            _text(f"SELECT {cols} FROM {cat['table']} ORDER BY ext_id")
        )).mappings().all()
    return {"catalog": catalog_id, "entries": [dict(r) for r in rows]}


@router.get("/actors")
async def list_actors(ctx: SecurityContext = Depends(get_security_context)):
    """Liste fusionnée des acteurs de la menace (ATT&CK Groups + MISP), pour l'autocomplétion
    « Émuler un threat actor » du formulaire Scénario. Ouvert à tout compte authentifié.

    Fusion/dédup : les doublons entre sources (ex. « APT29 » MITRE ⇄ « Cozy Bear » MISP dont
    l'alias est APT29) sont réunis en une seule entrée — on préfère la source MITRE pour les
    TTPs et on agrège les alias des deux, pour que la recherche par alias couvre tout.
    """
    async with service_session("admin_service") as session:
        groups = (await session.execute(_text(
            "SELECT ext_id, name, data FROM ref_attack_group ORDER BY name"))).mappings().all()
        actors = (await session.execute(_text(
            "SELECT ext_id, name, data FROM ref_misp_actor ORDER BY name"))).mappings().all()

    merged: list[dict] = []
    by_norm: dict[str, int] = {}

    def _register(actor: dict) -> None:
        idx = len(merged)
        merged.append(actor)
        for tok in [actor["name"], *actor["aliases"]]:
            by_norm.setdefault(_norm(tok), idx)

    # MITRE d'abord (source préférée pour les techniques).
    for r in groups:
        data = _coerce_data(r["data"])
        _register({"key": f"mitre:{r['ext_id']}", "name": r["name"], "source": "attack",
                   "aliases": list(data.get("aliases", [])), "techniques": data.get("techniques", [])})
    # MISP ensuite : fusion si un nom/alias correspond à un acteur déjà présent, sinon ajout.
    for r in actors:
        data = _coerce_data(r["data"])
        aliases = list(data.get("aliases", []))
        hit = next((by_norm[_norm(tok)] for tok in [r["name"], *aliases] if _norm(tok) in by_norm), None)
        if hit is not None:
            existing = merged[hit]
            for extra in [r["name"], *aliases]:
                if _norm(extra) != _norm(existing["name"]) and extra not in existing["aliases"]:
                    existing["aliases"].append(extra)
        else:
            _register({"key": f"misp:{r['ext_id']}", "name": r["name"], "source": "misp",
                       "aliases": aliases, "techniques": data.get("techniques", [])})

    return {"actors": [{"key": a["key"], "name": a["name"], "source": a["source"],
                        "aliases": a["aliases"], "technique_count": len(a["techniques"])}
                       for a in merged]}


@router.get("/actors/{key}/techniques")
async def actor_techniques(key: str, ctx: SecurityContext = Depends(get_security_context)):
    """TTPs connues d'un acteur (`key` = "mitre:Gxxxx" | "misp:<id>"), hydratées via ATT&CK.

    Lit `data.techniques` de l'acteur et complète chaque ext_id avec son nom/tactique depuis
    ref_attack_technique (ignore les ext_id absents : partiel honnête si le socle est réduit).
    """
    src, _, ext_id = key.partition(":")
    table = _ACTOR_TABLES.get(src)
    if not table or not ext_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="unknown_actor")
    async with service_session("admin_service") as session:
        row = (await session.execute(
            _text(f"SELECT name, data FROM {table} WHERE ext_id = :e"), {"e": ext_id}
        )).mappings().first()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="unknown_actor")
        data = _coerce_data(row["data"])
        tech_ids = list(data.get("techniques", []))
        hydrated: dict[str, dict] = {}
        if tech_ids:
            stmt = _text(
                "SELECT ext_id, name, tactic FROM ref_attack_technique WHERE ext_id IN :ids"
            ).bindparams(bindparam("ids", expanding=True))
            for h in (await session.execute(stmt, {"ids": tech_ids})).mappings().all():
                hydrated[h["ext_id"]] = h
    techniques = [{"ext_id": tid, "name": (hydrated.get(tid) or {}).get("name") or tid,
                   "tactic": (hydrated.get(tid) or {}).get("tactic")} for tid in tech_ids]
    return {"key": key, "name": row["name"], "aliases": data.get("aliases", []),
            "techniques": techniques}


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
    """(Ré)synchronise tous les catalogues. Admin uniquement.

    Pour les catalogues synchronisables (ATT&CK, D3FEND) : source amont MITRE avec repli
    gracieux sur le socle embarqué si la source est injoignable. Pour les autres (OWASP,
    CWE, CAPEC) : socle embarqué. Ainsi « Tout synchroniser » n'écrase plus un ATT&CK
    déjà synchronisé en ligne par le sous-ensemble embarqué.
    """
    if ctx.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    from app.reference.catalogs import CATALOGS
    from app.reference.sync import SYNCABLE, SyncUnavailable, sync_catalog

    result: dict[str, dict] = {}
    async with service_session("admin_service") as session:
        for cat in CATALOGS:
            cid = cat["id"]
            if cid in SYNCABLE:
                try:
                    n = await sync_catalog(session, cid)
                    source = "upstream"
                except SyncUnavailable:
                    n = await import_catalog(session, cid)
                    source = "fallback"
            else:
                n = await import_catalog(session, cid)
                source = "embedded"
            result[cid] = {"entries": n, "source": source}
        await journal_append(
            session, event_type="reference.synced", actor_id=ctx.user_id,
            subject="all", detail={
                "catalogs": len(result),
                "upstream": sum(1 for r in result.values() if r["source"] == "upstream"),
            },
        )
    return {"imported": result}
