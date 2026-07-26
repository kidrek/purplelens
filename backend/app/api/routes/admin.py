"""Routes journal & administration (spec backend v2 §5/§6).

Le journal est en lecture seule pour tous les rôles (aucun C/E/S, admin compris).
L'administration des comptes (création, changement de rôle/scope, désactivation)
est journalisée et exige un step-up MFA — ce sont des actions à haut risque (§3.4).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import settings
from app.db.session import auth_session, rls_session, service_session
from app.journal.chain import append as journal_append
from app.journal.chain import verify_chain
from app.security.context import SecurityContext
from app.security.matrix import GLOBAL_SCOPE_ROLES, ROLES, Action
from app.security.passwords import hash_password
from app.security.rbac import get_security_context, require, require_step_up

router = APIRouter(prefix="/api", tags=["admin"])


# ── Journal : filtres métier (partagés liste / export) ──────────────────────
# Regroupement des event_type par domaine fonctionnel (préfixe.action). Les valeurs
# sont des motifs LIKE ; « scenario » agrège l'activité CTI (scénarios, exercices,
# import/export STIX, enrichissement de vulnérabilités).
_DOMAIN_PREFIXES: dict[str, list[str]] = {
    "auth": ["auth.%"],
    "evidence": ["evidence.%"],
    "deliverable": ["deliverable.%"],
    "admin": ["admin.%"],
    "reference": ["reference.%"],
    "scenario": ["scenario.%", "exercise.%", "stix.%", "vulnerability.%"],
    "journal": ["journal.%"],
}


def _journal_filters(
    *,
    q: str | None,
    domain: list[str] | None,
    result: str | None,
    actor: list[str] | None,
    date_from: str | None,
    date_to: str | None,
) -> tuple[list[str], dict]:
    """Construit les clauses WHERE (paramètres liés, jamais d'interpolation de valeur).

    Toutes les requêtes journal joignent `app_user u ON u.id = j.actor_id` pour résoudre
    l'acteur (libellé lisible) : les colonnes de `journal` sont donc préfixées `j.`, et le
    libellé résolu = COALESCE(j.actor_label, u.display_name, u.email).
    """
    clauses: list[str] = []
    params: dict = {}
    if q:
        clauses.append(
            "(j.event_type ILIKE :q OR coalesce(j.actor_label,'') ILIKE :q "
            "OR coalesce(u.display_name,'') ILIKE :q OR coalesce(u.email,'') ILIKE :q "
            "OR coalesce(j.subject,'') ILIKE :q)"
        )
        params["q"] = f"%{q}%"
    if domain:
        patterns: list[str] = []
        for d in domain:
            patterns.extend(_DOMAIN_PREFIXES.get(d, []))
        if patterns:
            clauses.append("j.event_type LIKE ANY(CAST(:domains AS text[]))")
            params["domains"] = patterns
    if result == "ok":
        clauses.append("j.event_type LIKE '%.ok'")
    elif result == "denied":
        clauses.append(
            "(j.event_type LIKE '%.denied' OR j.event_type LIKE '%.failed' "
            "OR j.event_type LIKE '%rejected%' OR j.event_type LIKE '%mismatch%')"
        )
    if actor:
        # Filtre sur le libellé RÉSOLU (ce que l'utilisateur voit et sélectionne).
        clauses.append(
            "COALESCE(j.actor_label, u.display_name, u.email) = ANY(CAST(:actors AS text[]))"
        )
        params["actors"] = actor
    if date_from:
        clauses.append("j.created_at >= CAST(:date_from AS timestamptz)")
        params["date_from"] = date_from
    if date_to:
        clauses.append("j.created_at <= CAST(:date_to AS timestamptz)")
        params["date_to"] = date_to
    return clauses, params


# Source commune : jointure de résolution de l'acteur (app_user n'a pas de RLS et est
# lisible par app_api). `actor_label` affiché = libellé stocké, sinon nom, sinon e-mail.
_JOURNAL_FROM = "journal j LEFT JOIN app_user u ON u.id = j.actor_id"
_ACTOR_LABEL_EXPR = "COALESCE(j.actor_label, u.display_name, u.email)"


def _scope_clause(ctx: SecurityContext, params: dict) -> list[str]:
    """Durcissement P2 : un rôle cloisonné ne voit QUE les entrées de son périmètre
    (évite la fuite inter-tenant des event/subject/detail). Fail-closed : scope vide → rien.
    Les rôles globaux (admin/manager/service) voient toute la chaîne."""
    if ctx.role in GLOBAL_SCOPE_ROLES:
        return []
    params["scope"] = list(ctx.client_scope)
    return ["j.client_id = ANY(CAST(:scope AS uuid[]))"]


# ── Journal (lecture seule) ─────────────────────────────────────────────────
@router.get("/journal")
async def read_journal(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None),
    domain: list[str] | None = Query(None),
    result: str | None = Query(None),
    actor: list[str] | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    ctx: SecurityContext = Depends(require("journal", Action.L)),
):
    # Le journal est une chaîne GLOBALE (hors RLS client — CLIENT_UNSCOPED_TABLES).
    params: dict = {"l": limit, "o": offset}
    clauses = _scope_clause(ctx, params)
    fclauses, fparams = _journal_filters(
        q=q, domain=domain, result=result, actor=actor,
        date_from=date_from, date_to=date_to,
    )
    clauses += fclauses
    params.update(fparams)
    where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT j.seq, j.id, j.event_type, j.actor_id, "
                    f"{_ACTOR_LABEL_EXPR} AS actor_label, j.client_id, "
                    f"j.subject, j.detail, j.curr_hash, j.created_at FROM {_JOURNAL_FROM} "
                    f"{where}ORDER BY j.seq DESC LIMIT :l OFFSET :o"
                ),
                params,
            )
        ).mappings().all()
    return {"items": [dict(r) for r in rows], "limit": limit, "offset": offset}


@router.get("/journal/stats")
async def journal_stats(
    ctx: SecurityContext = Depends(require("journal", Action.L)),
):
    """Compteurs globaux de la chaîne (scope-aware), indépendants des filtres/pagination —
    alimentent la rangée KPI de la page Journal."""
    params: dict = {}
    clauses = _scope_clause(ctx, params)
    where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        row = (
            await session.execute(
                text(
                    "SELECT count(*) AS total, "
                    f"count(DISTINCT {_ACTOR_LABEL_EXPR}) AS distinct_actors, "
                    "count(*) FILTER (WHERE j.event_type LIKE '%.denied' "
                    "OR j.event_type LIKE '%.failed' OR j.event_type LIKE '%rejected%' "
                    "OR j.event_type LIKE '%mismatch%') AS denied, "
                    f"max(j.created_at) AS last_at FROM {_JOURNAL_FROM} " + where
                ),
                params,
            )
        ).mappings().first()
    return {
        "total": row["total"],
        "distinct_actors": row["distinct_actors"],
        "denied": row["denied"],
        "last_at": row["last_at"].isoformat() if row["last_at"] else None,
    }


@router.get("/journal/export")
async def export_journal(
    scope: str = Query("full", pattern="^(full|filtered)$"),
    q: str | None = Query(None),
    domain: list[str] | None = Query(None),
    result: str | None = Query(None),
    actor: list[str] | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    ctx: SecurityContext = Depends(require("journal", Action.L)),
):
    """Backup manuel : dump JSON ré-vérifiable (prev_hash + curr_hash) de la chaîne.
    Réservé aux rôles globaux + step-up MFA (§3.4). L'export est lui-même journalisé."""
    if ctx.role not in GLOBAL_SCOPE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    if not ctx.step_up_fresh(settings.step_up_max_age_seconds):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="step_up_required",
            headers={"WWW-Authenticate": 'MFA realm="step-up"'},
        )
    params: dict = {}
    where = ""
    if scope == "filtered":
        fclauses, fparams = _journal_filters(
            q=q, domain=domain, result=result, actor=actor,
            date_from=date_from, date_to=date_to,
        )
        params.update(fparams)
        where = f"WHERE {' AND '.join(fclauses)} " if fclauses else ""
    async with service_session("job_integrity") as session:
        # Jointure présente uniquement pour le filtre acteur (WHERE) ; le SELECT reste
        # sur les colonnes BRUTES de journal — le dump doit rester ré-vérifiable.
        rows = (
            await session.execute(
                text(
                    "SELECT j.seq, j.id, j.event_type, j.actor_id, j.actor_label, "
                    "j.client_id, j.subject, j.detail, j.prev_hash, j.curr_hash, "
                    f"j.created_at FROM {_JOURNAL_FROM} "
                    f"{where}ORDER BY j.seq ASC"
                ),
                params,
            )
        ).mappings().all()
    entries = []
    for r in rows:
        e = dict(r)
        e["id"] = str(e["id"]) if e["id"] is not None else None
        e["actor_id"] = str(e["actor_id"]) if e["actor_id"] is not None else None
        e["client_id"] = str(e["client_id"]) if e["client_id"] is not None else None
        e["created_at"] = e["created_at"].isoformat() if e["created_at"] else None
        entries.append(e)
    # Auto-journalisation de l'export (haut risque) — scelle la trace de sortie.
    async with auth_session() as jsession:
        await journal_append(
            jsession, event_type="journal.export", actor_id=ctx.user_id,
            detail={"scope": scope, "count": len(entries)},
        )
    stamp = datetime.now(UTC)
    payload = {
        "generated_at": stamp.isoformat(),
        "scope": scope,
        "count": len(entries),
        "genesis": "0" * 64,
        "entries": entries,
    }
    filename = f"journal-export-{scope}-{stamp.strftime('%Y%m%dT%H%M%SZ')}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/journal/verify")
async def verify_journal(
    ctx: SecurityContext = Depends(require("journal", Action.L)),
):
    """Recalcule la chaîne de hachage et signale la première rupture éventuelle."""
    async with service_session("job_integrity") as session:
        intact, break_at = await verify_chain(session)
    return {"intact": intact, "break_at_seq": break_at}


# ── Administration des comptes ──────────────────────────────────────────────
class UserCreate(BaseModel):
    email: str = Field(min_length=3)  # str (pas EmailStr) : domaines internes .local admis
    display_name: str | None = None
    role: str
    client_scope: list[uuid.UUID] = []
    external_sub: str | None = None
    password: str | None = None  # compte local de repli (optionnel)


class RoleChange(BaseModel):
    role: str
    client_scope: list[uuid.UUID] | None = None


def _check_role(role: str) -> None:
    if role not in ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="unknown_role")


@router.get("/admin/users")
async def list_users(ctx: SecurityContext = Depends(get_security_context)):
    """Liste des comptes (admin uniquement). Jamais de secret dans la réponse :
    ni hash de mot de passe, ni secret TOTP, ni sub OIDC complet — seulement
    l'indication qu'une liaison SSO existe."""
    if ctx.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    async with auth_session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, email, display_name, role, client_scope, status, "
                    "mfa_enrolled, (external_sub IS NOT NULL) AS sso_linked, created_at "
                    "FROM app_user ORDER BY created_at"
                )
            )
        ).all()
    return [
        {
            "id": str(r.id), "email": r.email, "display_name": r.display_name,
            "role": r.role, "client_scope": [str(c) for c in (r.client_scope or [])],
            "status": r.status, "mfa_enrolled": bool(r.mfa_enrolled),
            "sso_linked": bool(r.sso_linked),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/admin/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    ctx: SecurityContext = Depends(require("journal", Action.L)),  # base : authentifié
    _step: SecurityContext = Depends(require_step_up("user.create")),
):
    """Provisionne un compte. Réservé à l'admin (matrice) + step-up MFA."""
    if ctx.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    _check_role(payload.role)
    pw_hash = hash_password(payload.password) if payload.password else None
    scope = [str(c) for c in payload.client_scope]
    new_id = str(uuid.uuid4())
    async with auth_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO app_user
                  (id, external_sub, email, display_name, role, client_scope, status,
                   mfa_enrolled, password_hash, created_at, updated_at)
                VALUES
                  (:id, :sub, :email, :dn, :role, CAST(:scope AS uuid[]), 'active',
                   false, :pw, now(), now())
                """
            ),
            {
                "id": new_id, "sub": payload.external_sub, "email": payload.email,
                "dn": payload.display_name, "role": payload.role,
                # asyncpg attend une LISTE Python pour un uuid[], jamais un littéral
                # textuel '{...}' (même correctif que le seed).
                "scope": scope,
                "pw": pw_hash,
            },
        )
        await journal_append(
            session, event_type="admin.user.create", actor_id=ctx.user_id,
            subject=new_id, detail={"role": payload.role, "scope": scope},
        )
    return {"id": new_id, "email": payload.email, "role": payload.role}


@router.put("/admin/users/{user_id}/role")
async def change_role(
    user_id: uuid.UUID,
    payload: RoleChange,
    ctx: SecurityContext = Depends(require("journal", Action.L)),
    _step: SecurityContext = Depends(require_step_up("user.role_change")),
):
    """Changement de rôle/scope : haut risque → step-up + révocation des sessions."""
    if ctx.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    _check_role(payload.role)
    async with auth_session() as session:
        if payload.client_scope is not None:
            scope = [str(c) for c in payload.client_scope]
            await session.execute(
                text(
                    "UPDATE app_user SET role=:r, client_scope=CAST(:s AS uuid[]), "
                    "updated_at=now() WHERE id=:id"
                ),
                {"r": payload.role, "s": scope, "id": str(user_id)},
            )
        else:
            await session.execute(
                text("UPDATE app_user SET role=:r, updated_at=now() WHERE id=:id"),
                {"r": payload.role, "id": str(user_id)},
            )
        # Révoque les jetons en cours : le nouveau périmètre s'applique à la prochaine connexion.
        await session.execute(
            text("UPDATE refresh_token SET status='revoked' WHERE user_id=:id AND status='active'"),
            {"id": str(user_id)},
        )
        await journal_append(
            session, event_type="admin.user.role_change", actor_id=ctx.user_id,
            subject=str(user_id), detail={"new_role": payload.role},
        )
    return {"id": str(user_id), "role": payload.role}


@router.post("/admin/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: uuid.UUID,
    ctx: SecurityContext = Depends(require("journal", Action.L)),
    _step: SecurityContext = Depends(require_step_up("user.deactivate")),
):
    if ctx.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    async with auth_session() as session:
        await session.execute(
            text("UPDATE app_user SET status='disabled', updated_at=now() WHERE id=:id"),
            {"id": str(user_id)},
        )
        await session.execute(
            text("UPDATE refresh_token SET status='revoked' WHERE user_id=:id"),
            {"id": str(user_id)},
        )
        await journal_append(
            session, event_type="admin.user.deactivate", actor_id=ctx.user_id,
            subject=str(user_id), detail={},
        )
    return {"id": str(user_id), "status": "disabled"}
