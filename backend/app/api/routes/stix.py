"""Export STIX 2.1 des scénarios (cahier §5).

Les scénarios sont un référentiel CTI global (hors RLS client) ; l'accès reste gardé
par la matrice (L sur `scenarios`). L'export enrichit les techniques avec leur nom
depuis le référentiel ATT&CK, puis renvoie un bundle STIX 2.1 téléchargeable.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.db.session import rls_session
from app.deliverables.stix import bundle_to_scenarios, scenarios_to_bundle
from app.journal.chain import append as journal_append
from app.security.context import SecurityContext
from app.security.matrix import Action
from app.security.rbac import require

router = APIRouter(prefix="/api/stix", tags=["stix"])


async def _technique_names(session) -> dict[str, str]:
    rows = (await session.execute(
        text("SELECT ext_id, name FROM ref_attack_technique")
    )).all()
    return {r.ext_id: r.name for r in rows}


def _row_to_scenario(r) -> dict:
    return {
        "id": str(r.id), "nom": r.nom, "objectif": r.objectif,
        "acteur_emule": r.acteur_emule, "type_engagement": r.type_engagement,
        "sophistication": r.sophistication, "ioc": r.ioc, "ioa": r.ioa,
        "techniques": r.techniques or [], "d3fend": r.d3fend or [], "tlp": r.tlp,
    }


_COLS = ("id, nom, objectif, acteur_emule, type_engagement, sophistication, "
         "ioc, ioa, techniques, d3fend, tlp")


@router.get("/scenarios/{scenario_id}")
async def export_scenario(
    scenario_id: uuid.UUID,
    ctx: SecurityContext = Depends(require("scenarios", Action.L)),
):
    """Bundle STIX 2.1 d'un scénario."""
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        row = (await session.execute(
            text(f"SELECT {_COLS} FROM scenario WHERE id = :id AND deleted_at IS NULL"),
            {"id": str(scenario_id)},
        )).first()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
        names = await _technique_names(session)
        await journal_append(
            session, event_type="scenario.stix_export", actor_id=ctx.user_id,
            subject=str(scenario_id), detail={"scope": "single"},
        )
    bundle = scenarios_to_bundle([_row_to_scenario(row)], names)
    return JSONResponse(
        content=bundle,
        headers={"Content-Disposition": f'attachment; filename="scenario-{scenario_id}.stix.json"'},
    )


@router.get("/scenarios")
async def export_all_scenarios(
    ctx: SecurityContext = Depends(require("scenarios", Action.L)),
):
    """Bundle STIX 2.1 de tous les scénarios visibles."""
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        rows = (await session.execute(
            text(f"SELECT {_COLS} FROM scenario WHERE deleted_at IS NULL ORDER BY nom")
        )).all()
        names = await _technique_names(session)
        await journal_append(
            session, event_type="scenario.stix_export", actor_id=ctx.user_id,
            subject=None, detail={"scope": "all", "count": len(rows)},
        )
    bundle = scenarios_to_bundle([_row_to_scenario(r) for r in rows], names)
    return JSONResponse(
        content=bundle,
        headers={"Content-Disposition": 'attachment; filename="scenarios.stix.json"'},
    )


class StixImportIn(BaseModel):
    bundle: dict


@router.post("/import")
async def import_bundle(
    payload: StixImportIn,
    ctx: SecurityContext = Depends(require("scenarios", Action.C)),
):
    """Importe un bundle STIX 2.1 -> cree un/des scenario(s) dans la bibliotheque.

    Miroir de l'export. Les scenarios sont une bibliotheque partagee (non cloisonnee par
    client) : threat-emulation reutilisable. Reserve au droit de creation. Journalise.
    """
    if payload.bundle.get("type") != "bundle" or not isinstance(payload.bundle.get("objects"), list):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_bundle")

    parsed = bundle_to_scenarios(payload.bundle)
    if not parsed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="no_scenario_found")

    created = []
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as s:
        for sc in parsed:
            row = (await s.execute(text(
                "INSERT INTO scenario (id, nom, objectif, acteur_emule, techniques, "
                " d3fend, tlp, pap, notes, created_at, updated_at) VALUES "
                "(gen_random_uuid(), :nom, :obj, :actor, CAST(:tech AS jsonb), "
                " CAST(:d3f AS jsonb), :tlp, 'WHITE', :notes, now(), now()) RETURNING id"
            ), {
                "nom": sc["nom"], "obj": sc.get("objectif"),
                "actor": sc.get("acteur_emule"),
                "tech": json.dumps(sc.get("techniques") or []),
                "d3f": json.dumps(sc.get("d3fend") or []),
                "tlp": sc.get("tlp", "AMBER"),
                "notes": sc.get("notes_import") or None,
            })).first()
            # Étapes offensives : une ligne scenario_step par technique (ordre du bundle,
            # tactique dérivée du référentiel) — sinon l'éditeur d'étapes serait vide
            # alors que la colonne JSON `techniques` est remplie (deux stockages).
            if sc.get("techniques"):
                await s.execute(text(
                    "INSERT INTO scenario_step (id, scenario_id, ordre, technique, tactique, "
                    " created_at, updated_at) "
                    "SELECT gen_random_uuid(), :sid, t.ord - 1, t.tech, r.tactic, now(), now() "
                    "FROM jsonb_array_elements_text(CAST(:techs AS jsonb)) "
                    " WITH ORDINALITY AS t(tech, ord) "
                    "LEFT JOIN ref_attack_technique r ON r.ext_id = t.tech"
                ), {"sid": str(row.id), "techs": json.dumps(sc["techniques"])})
            created.append(str(row.id))
        await journal_append(
            s, event_type="stix.imported", actor_id=ctx.user_id, subject="scenarios",
            detail={"scenarios": len(created), "objects": len(payload.bundle.get("objects", []))},
        )
    return {"imported": len(created), "scenario_ids": created}
