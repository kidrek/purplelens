"""Routes journal & administration (spec backend v2 §5/§6).

Le journal est en lecture seule pour tous les rôles (aucun C/E/S, admin compris).
L'administration des comptes (création, changement de rôle/scope, désactivation)
est journalisée et exige un step-up MFA — ce sont des actions à haut risque (§3.4).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db.session import auth_session, rls_session, service_session
from app.journal.chain import append as journal_append
from app.journal.chain import verify_chain
from app.security.context import SecurityContext
from app.security.matrix import GLOBAL_SCOPE_ROLES, ROLES, Action
from app.security.passwords import hash_password
from app.security.rbac import get_security_context, require, require_step_up

router = APIRouter(prefix="/api", tags=["admin"])


# ── Journal (lecture seule) ─────────────────────────────────────────────────
@router.get("/journal")
async def read_journal(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    ctx: SecurityContext = Depends(require("journal", Action.L)),
):
    # Le journal est une chaîne GLOBALE (hors RLS client — CLIENT_UNSCOPED_TABLES).
    # Durcissement P2 : on filtre en applicatif pour qu'un rôle cloisonné ne voie QUE
    # les entrées de son périmètre (évite la fuite inter-tenant des event/subject/detail).
    # Les rôles globaux (admin/manager/service) voient toute la chaîne.
    params: dict = {"l": limit, "o": offset}
    scope_filter = ""
    if ctx.role not in GLOBAL_SCOPE_ROLES:
        # Fail-closed cohérent avec la porte 4 : un scope vide ne voit rien.
        scope_filter = "WHERE client_id = ANY(CAST(:scope AS uuid[]))"
        params["scope"] = list(ctx.client_scope)
    async with rls_session(
        user_id=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope
    ) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT seq, id, event_type, actor_id, actor_label, client_id, "
                    "subject, detail, curr_hash, created_at FROM journal "
                    f"{scope_filter} ORDER BY seq DESC LIMIT :l OFFSET :o"
                ),
                params,
            )
        ).mappings().all()
    return {"items": [dict(r) for r in rows], "limit": limit, "offset": offset}


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
