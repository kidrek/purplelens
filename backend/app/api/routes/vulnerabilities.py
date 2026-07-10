"""Vulnérabilités — enrichissement décisionnel (KEV / EPSS / SSVC / VEX).

Expose ce que la table `vulnerability_enrichment` porte déjà : la présence au catalogue
CISA KEV (exploitation active connue), le score EPSS (probabilité d'exploitation), le
statut VEX (exploitabilité réelle dans le contexte), et une décision SSVC calculée.

Le cloisonnement est assuré par la RLS (la table porte client_id). L'écriture exige la
permission d'édition des vulnérabilités ; la lecture, la permission de liste.

Note d'honnêteté : KEV et EPSS proviennent en production de sources amont (catalogue
CISA KEV, API FIRST EPSS) rapatriées par CVE ; ici elles sont saisies/actualisées par
l'analyste. La décision SSVC est un arbre simplifié inspiré du modèle CISA (Track,
Track*, Attend, Act), calculé de façon déterministe à partir de CVSS + KEV + EPSS.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from app.config import settings
from app.db.session import rls_session
from app.journal.chain import append as journal_append
from app.security.context import SecurityContext
from app.security.matrix import Action
from app.security.rbac import require
from app.vuln.circl import (
    EnrichmentUnavailable,
    fetch_cve,
    fetch_epss,
    parse_circl,
    parse_epss_row,
)

router = APIRouter(prefix="/api", tags=["vulnerabilities"])


def compute_ssvc(cvss: float | None, kev: bool, epss: float | None) -> str:
    """Décision SSVC déterministe (arbre simplifié, style CISA).

    Signaux : exploitation (active si KEV ; « poc » si EPSS ≥ 0,10 ; sinon aucune) et
    gravité (CVSS). Décisions, du moins au plus urgent : Track, Track*, Attend, Act.
    """
    c = float(cvss) if cvss is not None else 0.0
    e = float(epss) if epss is not None else 0.0
    if kev:
        exploit = "active"
    elif e >= 0.10:
        exploit = "poc"
    else:
        exploit = "none"
    high = c >= 7.0
    crit = c >= 9.0
    if exploit == "active":
        return "Act" if high else "Attend"
    if exploit == "poc":
        return "Attend" if high else "Track*"
    return "Track*" if crit else "Track"


_CLOSED = ("corrige", "resolu", "ferme", "accepte", "corrigee", "acceptee", "faux_positif")


@router.get("/vulnerabilities-enriched")
async def list_enriched(ctx: SecurityContext = Depends(require("vulnerabilities", Action.L))):
    """Vulnérabilités du périmètre avec leur enrichissement et l'état SLA."""
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as s:
        rows = (await s.execute(text(
            """
            SELECT v.id, v.client_id, v.audit_id, v.titre, v.cve, v.cwe, v.severite, v.cvss_score,
                   v.statut, v.sla_niveau, v.sla_echeance, v.tlp, v.created_at,
                   COALESCE(a.applications, v.applications) AS applications,
                   e.kev, e.kev_ransomware, e.kev_due_date,
                   e.epss_score, e.epss_percentile, e.ssvc_decision, e.vex_status,
                   e.enrichment_status, e.enrichment_source, e.enriched_at
            FROM vulnerability v
            LEFT JOIN vulnerability_enrichment e ON e.vulnerability_id = v.id
            LEFT JOIN audit a ON a.id = v.audit_id
            WHERE v.deleted_at IS NULL
            ORDER BY v.cvss_score DESC NULLS LAST, v.created_at DESC
            """
        ))).mappings().all()

    items = []
    for r in rows:
        d = dict(r)
        d["id"] = str(r["id"])
        d["client_id"] = str(r["client_id"])
        d["audit_id"] = str(r["audit_id"]) if r["audit_id"] else None
        d["applications"] = [str(a) for a in (r["applications"] or [])]
        # État SLA : en dépassement si échéance passée et vuln non close.
        overdue = bool(
            r["sla_echeance"] and str(r["statut"]) not in _CLOSED
            and r["sla_echeance"].isoformat() < _today()
        )
        d["sla_overdue"] = overdue
        d["created_at"] = r["created_at"].isoformat() if r["created_at"] else None
        for k in ("sla_echeance", "kev_due_date"):
            d[k] = r[k].isoformat() if r[k] else None
        for k in ("epss_score", "epss_percentile", "cvss_score"):
            d[k] = float(r[k]) if r[k] is not None else None
        d["enriched_at"] = r["enriched_at"].isoformat() if r["enriched_at"] else None
        items.append(d)
    return {"items": items}


def _today() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).date().isoformat()


class EnrichmentIn(BaseModel):
    kev: bool = False
    kev_ransomware: bool = False
    kev_date_added: str | None = None
    kev_due_date: str | None = None
    epss_score: float | None = None
    epss_percentile: float | None = None
    epss_date: str | None = None
    vex_status: str | None = None  # not_affected | affected | fixed | under_investigation


@router.get("/vulnerabilities/{vuln_id}/enrichment")
async def get_enrichment(
    vuln_id: uuid.UUID,
    ctx: SecurityContext = Depends(require("vulnerabilities", Action.L)),
):
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as s:
        # La vuln doit être visible (RLS) ; sinon 404 net.
        v = (await s.execute(text(
            "SELECT cvss_score FROM vulnerability WHERE id = :i AND deleted_at IS NULL"
        ), {"i": str(vuln_id)})).first()
        if v is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
        row = (await s.execute(text(
            "SELECT kev, kev_ransomware, kev_date_added, kev_due_date, epss_score, "
            "epss_percentile, epss_date, ssvc_decision, vex_status, enriched_at, "
            "enrichment_source, raw FROM vulnerability_enrichment WHERE vulnerability_id = :i"
        ), {"i": str(vuln_id)})).mappings().first()
    return {"enrichment": dict(row) if row else None}


@router.put("/vulnerabilities/{vuln_id}/enrichment")
async def put_enrichment(
    vuln_id: uuid.UUID,
    payload: EnrichmentIn,
    ctx: SecurityContext = Depends(require("vulnerabilities", Action.E)),
):
    """Crée/actualise l'enrichissement et recalcule la décision SSVC (CVSS+KEV+EPSS)."""
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as s:
        v = (await s.execute(text(
            "SELECT client_id, cvss_score FROM vulnerability WHERE id = :i AND deleted_at IS NULL"
        ), {"i": str(vuln_id)})).first()
        if v is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")

        ssvc = compute_ssvc(v.cvss_score, payload.kev, payload.epss_score)
        params = {
            "vid": str(vuln_id), "cid": str(v.client_id),
            "kev": payload.kev, "kevr": payload.kev_ransomware,
            "kda": payload.kev_date_added, "kdd": payload.kev_due_date,
            "es": payload.epss_score, "ep": payload.epss_percentile, "ed": payload.epss_date,
            "vex": payload.vex_status, "ssvc": ssvc,
        }
        # Upsert manuel (une ligne d'enrichissement par vulnérabilité).
        exists = (await s.execute(text(
            "SELECT 1 FROM vulnerability_enrichment WHERE vulnerability_id = :vid"
        ), {"vid": str(vuln_id)})).first()
        if exists:
            await s.execute(text(
                "UPDATE vulnerability_enrichment SET kev=:kev, kev_ransomware=:kevr, "
                "kev_date_added=:kda, kev_due_date=:kdd, epss_score=:es, "
                "epss_percentile=:ep, epss_date=:ed, vex_status=:vex, ssvc_decision=:ssvc, "
                "enrichment_status='manual', enriched_at=now(), "
                "enrichment_source='analyste', updated_at=now() "
                "WHERE vulnerability_id=:vid"
            ), params)
        else:
            await s.execute(text(
                "INSERT INTO vulnerability_enrichment "
                "(id, vulnerability_id, client_id, kev, kev_ransomware, kev_date_added, "
                " kev_due_date, epss_score, epss_percentile, epss_date, vex_status, "
                " ssvc_decision, enrichment_status, enriched_at, enrichment_source, "
                " created_at, updated_at) VALUES "
                "(gen_random_uuid(), :vid, :cid, :kev, :kevr, :kda, :kdd, :es, :ep, :ed, "
                " :vex, :ssvc, 'manual', now(), 'analyste', now(), now())"
            ), params)
        await journal_append(
            s, event_type="vulnerability.enriched", actor_id=ctx.user_id,
            client_id=str(v.client_id), subject=str(vuln_id),
            detail={"kev": payload.kev, "ssvc": ssvc, "vex": payload.vex_status},
        )
    return {"vulnerability_id": str(vuln_id), "ssvc_decision": ssvc}


@router.post("/vulnerabilities/{vuln_id}/enrich")
async def enrich_from_circl(
    vuln_id: uuid.UUID,
    ctx: SecurityContext = Depends(require("vulnerabilities", Action.E)),
):
    """Enrichit une vulnérabilité depuis CIRCL Vulnerability-Lookup (cahier §6, A.1/A.2).

    À partir du CVE du finding, appelle `{enrichment_base_url}/api/vulnerability/{cve}`,
    pré-remplit CVSS/CWE/description sur la vuln et met en cache EPSS/KEV + le reste
    (CAPEC, références, produits) sur l'enrichissement. Recalcule la décision SSVC.

    Dégradation gracieuse : si la source est injoignable (hors-ligne, engagement isolé),
    l'enrichissement passe en statut « differe » sans erreur — la saisie manuelle reste
    possible et l'appel pourra être rejoué plus tard.
    """
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as s:
        v = (await s.execute(text(
            "SELECT client_id, cve, cvss_score, cwe, description "
            "FROM vulnerability WHERE id = :i AND deleted_at IS NULL"
        ), {"i": str(vuln_id)})).first()
        if v is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
        if not v.cve:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="no_cve")

        base = settings.enrichment_base_url
        try:
            raw = await fetch_cve(v.cve, base_url=base)
        except EnrichmentUnavailable:
            # Hors-ligne / source indisponible → différé, pas d'échec dur.
            await _set_enrichment_status(s, vuln_id, v.client_id, "differe", base)
            await journal_append(
                s, event_type="vulnerability.enrich_deferred", actor_id=ctx.user_id,
                client_id=str(v.client_id), subject=str(vuln_id), detail={"cve": v.cve},
            )
            return {"status": "differe", "cve": v.cve,
                    "message": "Source d'enrichissement injoignable — enrichissement différé."}

        parsed = parse_circl(raw)
        if not parsed.get("found"):
            await _set_enrichment_status(s, vuln_id, v.client_id, "echec", base)
            return {"status": "echec", "cve": v.cve,
                    "message": "CVE introuvable sur la source d'enrichissement."}

        # EPSS : source dédiée (cve.circl.lu/api/epss) prioritaire sur l'agrégat principal,
        # qui ne porte pas l'EPSS de façon fiable (constat de terrain). Best-effort : un
        # échec ici ne bloque jamais l'enrichissement, on garde ce que parse_circl a trouvé.
        try:
            epss_row = await fetch_epss(v.cve, base_url=settings.enrichment_epss_url)
            epss_score, epss_pct = parse_epss_row(epss_row) if epss_row else (None, None)
            if epss_score is not None:
                parsed["epss_score"] = epss_score
                parsed["epss_percentile"] = epss_pct
        except EnrichmentUnavailable:
            pass

        # Pré-remplissage de la vulnérabilité (sans écraser une saisie existante).
        sets, params = [], {"i": str(vuln_id)}
        if parsed["cvss_score"] is not None and v.cvss_score is None:
            sets.append("cvss_score = :cs")
            params["cs"] = parsed["cvss_score"]
        if parsed["cvss_vector"]:
            sets.append("cvss_vector = :cv")
            params["cv"] = parsed["cvss_vector"]
        if parsed["cwe"] and not v.cwe:
            sets.append("cwe = :cw")
            params["cw"] = parsed["cwe"]
        if parsed["description"] and not v.description:
            sets.append("description = :de")
            params["de"] = parsed["description"]
        if sets:
            await s.execute(text(
                f"UPDATE vulnerability SET {', '.join(sets)}, updated_at = now() WHERE id = :i"
            ), params)

        # Décision SSVC à partir des signaux enrichis (CVSS effectif + KEV + EPSS).
        cvss_eff = parsed["cvss_score"] if parsed["cvss_score"] is not None else v.cvss_score
        ssvc = compute_ssvc(cvss_eff, parsed["kev"], parsed["epss_score"])
        cache = {
            "cvss_version": parsed["cvss_version"], "cvss_vector": parsed["cvss_vector"],
            "capec": parsed["capec"], "references": parsed["references"],
            "products": parsed["products"], "cpes": parsed.get("cpes", []),
        }
        await _upsert_enrichment(
            s, vuln_id, v.client_id,
            kev=parsed["kev"], kev_ransomware=parsed["kev_ransomware"],
            epss_score=parsed["epss_score"], epss_percentile=parsed["epss_percentile"],
            ssvc=ssvc, status="enrichi", source=base, raw=cache,
        )
        await journal_append(
            s, event_type="vulnerability.enriched", actor_id=ctx.user_id,
            client_id=str(v.client_id), subject=str(vuln_id),
            detail={"cve": v.cve, "source": base, "kev": parsed["kev"], "ssvc": ssvc},
        )
    return {
        "status": "enrichi", "cve": v.cve, "source": base, "ssvc_decision": ssvc,
        "cvss_score": parsed["cvss_score"], "cwe": parsed["cwe"],
        "epss_score": parsed["epss_score"], "kev": parsed["kev"],
        "capec": parsed["capec"], "references": parsed["references"],
    }


async def _set_enrichment_status(s, vuln_id, client_id, status_val, source):
    """Pose/actualise seulement le statut d'enrichissement (différé/échec)."""
    exists = (await s.execute(text(
        "SELECT 1 FROM vulnerability_enrichment WHERE vulnerability_id = :v"
    ), {"v": str(vuln_id)})).first()
    if exists:
        await s.execute(text(
            "UPDATE vulnerability_enrichment SET enrichment_status = :st, "
            "enrichment_source = :src, updated_at = now() WHERE vulnerability_id = :v"
        ), {"v": str(vuln_id), "st": status_val, "src": source})
    else:
        await s.execute(text(
            "INSERT INTO vulnerability_enrichment (id, vulnerability_id, client_id, "
            "enrichment_status, enrichment_source, raw, created_at, updated_at) VALUES "
            "(gen_random_uuid(), :v, :c, :st, :src, '{}'::jsonb, now(), now())"
        ), {"v": str(vuln_id), "c": str(client_id), "st": status_val, "src": source})


async def _upsert_enrichment(s, vuln_id, client_id, *, kev, kev_ransomware,
                             epss_score, epss_percentile, ssvc, status, source, raw):
    """Upsert complet de l'enrichissement (valeurs + cache brut + statut)."""
    import json as _json

    params = {
        "v": str(vuln_id), "c": str(client_id), "kev": kev, "kevr": kev_ransomware,
        "es": epss_score, "ep": epss_percentile, "ssvc": ssvc,
        "st": status, "src": source, "raw": _json.dumps(raw),
    }
    exists = (await s.execute(text(
        "SELECT 1 FROM vulnerability_enrichment WHERE vulnerability_id = :v"
    ), {"v": str(vuln_id)})).first()
    if exists:
        await s.execute(text(
            "UPDATE vulnerability_enrichment SET kev = :kev, kev_ransomware = :kevr, "
            "epss_score = :es, epss_percentile = :ep, ssvc_decision = :ssvc, "
            "enrichment_status = :st, enrichment_source = :src, enriched_at = now(), "
            "raw = CAST(:raw AS jsonb), updated_at = now() WHERE vulnerability_id = :v"
        ), params)
    else:
        await s.execute(text(
            "INSERT INTO vulnerability_enrichment (id, vulnerability_id, client_id, kev, "
            "kev_ransomware, epss_score, epss_percentile, ssvc_decision, enrichment_status, "
            "enrichment_source, enriched_at, raw, created_at, updated_at) VALUES "
            "(gen_random_uuid(), :v, :c, :kev, :kevr, :es, :ep, :ssvc, :st, :src, now(), "
            "CAST(:raw AS jsonb), now(), now())"
        ), params)
