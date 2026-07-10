"""Exercices Purple Team — composition de la chaîne d'étapes.

Deux opérations qui sortent du CRUD générique :
- charger les étapes depuis un scénario de menace (les techniques du scénario deviennent
  autant d'étapes d'attaque ordonnées) — accélère la mise en place d'un exercice ;
- réordonnancer la chaîne (l'ordre porte la logique de kill-chain).

Cloisonnement RLS : l'exercice et ses étapes doivent être dans le périmètre de l'appelant.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from app.db.session import rls_session
from app.journal.chain import append as journal_append
from app.security.context import SecurityContext
from app.security.matrix import Action
from app.security.rbac import require

router = APIRouter(prefix="/api/exercices", tags=["exercices"])


class LoadScenarioIn(BaseModel):
    scenario_id: uuid.UUID


@router.post("/{exercise_id}/load-scenario")
async def load_scenario(
    exercise_id: uuid.UUID,
    payload: LoadScenarioIn,
    ctx: SecurityContext = Depends(require("attack_steps", Action.C)),
):
    """Crée une étape d'attaque par technique du scénario, à la suite des étapes existantes.

    Les scénarios sont une bibliothèque globale ; l'exercice, lui, est cloisonné. On lit le
    client de l'exercice et on rattache les étapes à ce client (respect de la RLS).
    """
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as s:
        ex = (await s.execute(text(
            "SELECT client_id FROM purple_exercise WHERE id = :e AND deleted_at IS NULL"
        ), {"e": str(exercise_id)})).first()
        if ex is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="exercise_not_found")

        sc = (await s.execute(text(
            "SELECT nom, techniques FROM scenario WHERE id = :s AND deleted_at IS NULL"
        ), {"s": str(payload.scenario_id)})).first()
        if sc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="scenario_not_found")
        techniques = sc.techniques or []
        if not techniques:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="scenario_has_no_technique")

        # Noms des techniques (référentiel) pour intituler les étapes.
        names = dict((r.ext_id, r.name) for r in (await s.execute(text(
            "SELECT ext_id, name FROM ref_attack_technique WHERE ext_id = ANY(:codes)"
        ), {"codes": list(techniques)})).all())

        base = (await s.execute(text(
            "SELECT coalesce(max(ordre), 0) m FROM attack_step WHERE exercise_id = :e"
        ), {"e": str(exercise_id)})).scalar_one()

        created = 0
        for i, code in enumerate(techniques, start=1):
            titre = names.get(code) or code
            await s.execute(text(
                "INSERT INTO attack_step (id, exercise_id, client_id, ordre, technique, "
                " titre, verdict, created_at, updated_at) VALUES "
                "(gen_random_uuid(), :e, :c, :o, :t, :ti, 'not_tested', now(), now())"
            ), {"e": str(exercise_id), "c": str(ex.client_id), "o": base + i,
                "t": code, "ti": titre})
            created += 1

        await journal_append(
            s, event_type="exercise.steps_loaded", actor_id=ctx.user_id,
            client_id=str(ex.client_id), subject=str(exercise_id),
            detail={"scenario": sc.nom, "steps": created},
        )
    return {"exercise_id": str(exercise_id), "created": created}


class ReorderIn(BaseModel):
    step_ids: list[uuid.UUID]


@router.post("/{exercise_id}/reorder")
async def reorder_steps(
    exercise_id: uuid.UUID,
    payload: ReorderIn,
    ctx: SecurityContext = Depends(require("attack_steps", Action.E)),
):
    """Réassigne l'ordre des étapes selon la liste fournie (1..N)."""
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as s:
        # Ne réordonne que des étapes appartenant réellement à cet exercice (et visibles RLS).
        owned = {str(r.id) for r in (await s.execute(text(
            "SELECT id FROM attack_step WHERE exercise_id = :e"
        ), {"e": str(exercise_id)})).all()}
        given = [str(i) for i in payload.step_ids]
        if set(given) != owned:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="step_set_mismatch")
        for idx, sid in enumerate(given, start=1):
            await s.execute(text(
                "UPDATE attack_step SET ordre = :o, updated_at = now() WHERE id = :i"
            ), {"o": idx, "i": sid})
    return {"exercise_id": str(exercise_id), "reordered": len(given)}
