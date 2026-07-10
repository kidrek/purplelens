"""Routes d'authentification & de session (spec backend v2 §2/§3).

Modèle : l'IdP (Keycloak) authentifie (OIDC+PKCE, D7) ; le PRODUIT décide du rôle
(D4). Comptes locaux Argon2id en repli (v2 §2.3). L'access token part en cookie
HttpOnly + SameSite ; le refresh token est opaque, rotatif, anti-rejeu.
"""
from __future__ import annotations

import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import text

from app.api.deps import ACCESS_COOKIE
from app.config import settings
from app.db.session import auth_session
from app.journal.chain import append as journal_append
from app.schemas.auth import (
    LocalLoginRequest,
    OidcStart,
    RefreshRequest,
    StepUpRequest,
    TokenResponse,
    WhoAmI,
)
from app.security.context import SecurityContext
from app.security.mfa import new_secret, provisioning_uri, verify_totp
from app.security.oidc import authorization_url, exchange_code, generate_pkce, userinfo
from app.security.passwords import verify_password
from app.security.rbac import get_security_context
from app.security.tokens import (
    issue_access_token,
    issue_refresh_token,
    revoke_user_tokens,
    rotate_refresh_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Magasin PKCE éphémère. En production : Redis avec TTL (voir docs/runbook).
# Le state OIDC ne doit jamais fuiter côté client au-delà de son usage anti-CSRF.
_PKCE_STORE: dict[str, str] = {}
_REFRESH_COOKIE = "pc_refresh"


def _set_session_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE, access, httponly=True, secure=True, samesite="strict",
        max_age=settings.access_token_ttl_seconds, path="/",
    )
    response.set_cookie(
        _REFRESH_COOKIE, refresh, httponly=True, secure=True, samesite="strict",
        max_age=settings.refresh_token_ttl_seconds, path="/api/auth",
    )


def _user_scope(row) -> list[str]:
    scope = row.client_scope or []
    return [str(c) for c in scope]


@router.post("/login", response_model=TokenResponse)
async def login(payload: LocalLoginRequest, response: Response, request: Request):
    """Connexion par compte local (repli). Argon2id + TOTP si MFA enrôlée."""
    async with auth_session() as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, email, role, client_scope, status, password_hash, "
                    "totp_secret, mfa_enrolled, display_name "
                    "FROM app_user WHERE lower(email)=lower(:e)"
                ),
                {"e": payload.email},
            )
        ).first()

        # Message d'échec uniforme : ne distingue pas compte inexistant / mauvais mot de passe.
        if row is None or row.status != "active" or not row.password_hash:
            await journal_append(
                session, event_type="auth.login.denied", actor_id=None,
                actor_label=payload.email, detail={"reason": "unknown_or_inactive"},
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

        if not verify_password(row.password_hash, payload.password):
            await journal_append(
                session, event_type="auth.login.denied", actor_id=str(row.id),
                detail={"reason": "bad_password"},
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

        if row.mfa_enrolled:
            if not payload.totp or not row.totp_secret or not verify_totp(row.totp_secret, payload.totp):
                await journal_append(
                    session, event_type="auth.login.denied", actor_id=str(row.id),
                    detail={"reason": "mfa_required_or_invalid"},
                )
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="mfa_required")

        auth_time = int(time.time())
        scope = _user_scope(row)
        access = issue_access_token(
            sub=str(row.id), role=row.role, client_scope=scope, mfa=bool(row.mfa_enrolled),
            auth_time=auth_time, email=row.email, display_name=row.display_name,
        )
        raw_refresh, _ = await issue_refresh_token(session, user_id=str(row.id))
        await journal_append(
            session, event_type="auth.login.ok", actor_id=str(row.id),
            detail={"role": row.role, "mfa": bool(row.mfa_enrolled)},
        )

    _set_session_cookies(response, access, raw_refresh)
    return TokenResponse(
        access_token=access, expires_in=settings.access_token_ttl_seconds,
        role=row.role, mfa=bool(row.mfa_enrolled), display_name=row.display_name,
    )


@router.get("/oidc/start", response_model=OidcStart)
async def oidc_start():
    """Démarre le flux OIDC+PKCE : renvoie l'URL d'autorisation Keycloak."""
    verifier, challenge = generate_pkce()
    state = secrets.token_urlsafe(24)
    _PKCE_STORE[state] = verifier  # associé au state, consommé une seule fois au callback
    url = await authorization_url(state=state, code_challenge=challenge)
    return OidcStart(authorization_url=url, state=state)


@router.get("/callback", response_model=TokenResponse)
async def oidc_callback(code: str, state: str, response: Response):
    """Callback OIDC : échange le code, provisionne l'utilisateur, ouvre la session.

    Le rôle vient du PRODUIT (table app_user), jamais de l'IdP (D4) : Keycloak ne
    fait qu'authentifier. Un `sub` inconnu → compte à provisionner par un admin.
    """
    verifier = _PKCE_STORE.pop(state, None)
    if verifier is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_state")

    tokens = await exchange_code(code=code, code_verifier=verifier)
    info = await userinfo(tokens["access_token"])
    external_sub = info.get("sub")

    async with auth_session() as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, email, role, client_scope, status, mfa_enrolled, display_name "
                    "FROM app_user WHERE external_sub = :sub"
                ),
                {"sub": external_sub},
            )
        ).first()

        # Rattachement automatique par e-mail VÉRIFIÉ : si le sub est inconnu mais
        # qu'un compte actif, pré-provisionné par un admin (rôle/scope déjà décidés
        # dans le produit — D4 respecté) et non encore lié (external_sub NULL), porte
        # exactement cet e-mail, on lie l'identité et on poursuit. Ainsi l'admin peut
        # créer le compte côté produit (email + rôle) et côté Keycloak (email + mdp
        # temporaire + OTP requis) sans avoir à recopier le sub à la main.
        if row is None and info.get("email") and info.get("email_verified", False):
            candidate = (
                await session.execute(
                    text(
                        "SELECT id, email, role, client_scope, status, mfa_enrolled, display_name "
                        "FROM app_user WHERE external_sub IS NULL "
                        "AND lower(email) = lower(:email) AND status = 'active'"
                    ),
                    {"email": info["email"]},
                )
            ).first()
            if candidate is not None:
                await session.execute(
                    text("UPDATE app_user SET external_sub=:sub, updated_at=now() WHERE id=:id"),
                    {"sub": external_sub, "id": str(candidate.id)},
                )
                await journal_append(
                    session, event_type="auth.oidc.linked", actor_id=str(candidate.id),
                    detail={"email": candidate.email},  # jamais le sub complet au journal
                )
                row = candidate

        if row is None or row.status != "active":
            await journal_append(
                session, event_type="auth.oidc.denied", actor_id=None,
                actor_label=info.get("email"), detail={"reason": "not_provisioned"},
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="account_not_provisioned")

        auth_time = int(time.time())
        scope = _user_scope(row)
        access = issue_access_token(
            sub=str(row.id), role=row.role, client_scope=scope, mfa=bool(row.mfa_enrolled),
            auth_time=auth_time, email=row.email, display_name=row.display_name,
        )
        raw_refresh, _ = await issue_refresh_token(session, user_id=str(row.id))
        await journal_append(
            session, event_type="auth.oidc.ok", actor_id=str(row.id),
            detail={"role": row.role},
        )

    _set_session_cookies(response, access, raw_refresh)
    return TokenResponse(
        access_token=access, expires_in=settings.access_token_ttl_seconds,
        role=row.role, mfa=bool(row.mfa_enrolled), display_name=row.display_name,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, body: RefreshRequest | None = None):
    """Rotation du refresh token. Rejeu détecté → toute la famille est brûlée."""
    raw = (body.refresh_token if body else None) or request.cookies.get(_REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="no_refresh_token")

    async with auth_session() as session:
        new_raw, user_id, statut = await rotate_refresh_token(session, raw_token=raw)
        if statut != "ok" or not new_raw or not user_id:
            await journal_append(
                session, event_type="auth.refresh.denied", actor_id=user_id,
                detail={"status": statut},
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=f"refresh_{statut}")

        row = (
            await session.execute(
                text(
                    "SELECT id, email, role, client_scope, mfa_enrolled, display_name "
                    "FROM app_user WHERE id = :id"
                ),
                {"id": user_id},
            )
        ).first()
        auth_time = int(time.time())
        scope = _user_scope(row)
        access = issue_access_token(
            sub=str(row.id), role=row.role, client_scope=scope, mfa=bool(row.mfa_enrolled),
            auth_time=auth_time, email=row.email, display_name=row.display_name,
        )

    _set_session_cookies(response, access, new_raw)
    return TokenResponse(
        access_token=access, expires_in=settings.access_token_ttl_seconds,
        role=row.role, mfa=bool(row.mfa_enrolled), display_name=row.display_name,
    )


@router.post("/step-up", response_model=TokenResponse)
async def step_up(
    payload: StepUpRequest,
    response: Response,
    ctx: SecurityContext = Depends(get_security_context),
):
    """Réauthentification MFA : réémet un access token à `auth_time` frais.

    Requis avant les actions à haut risque (crypto-shredding, legal hold, export,
    changement de rôle/scope — spec v2 §3.4). Le nouveau jeton porte un auth_time
    récent qui satisfait `require_step_up`.
    """
    async with auth_session() as session:
        row = (
            await session.execute(
                text("SELECT totp_secret, mfa_enrolled FROM app_user WHERE id = :id"),
                {"id": ctx.user_id},
            )
        ).first()
        if not row or not row.mfa_enrolled or not row.totp_secret \
                or not verify_totp(row.totp_secret, payload.totp):
            await journal_append(
                session, event_type="auth.stepup.denied", actor_id=ctx.user_id,
                detail={"reason": "invalid_totp"},
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_totp")

        auth_time = int(time.time())
        access = issue_access_token(
            sub=ctx.user_id, role=ctx.role, client_scope=ctx.client_scope, mfa=True,
            auth_time=auth_time, email=ctx.email, display_name=ctx.display_name,
        )
        await journal_append(
            session, event_type="auth.stepup.ok", actor_id=ctx.user_id, detail={},
        )

    response.set_cookie(
        ACCESS_COOKIE, access, httponly=True, secure=True, samesite="strict",
        max_age=settings.access_token_ttl_seconds, path="/",
    )
    return TokenResponse(
        access_token=access, expires_in=settings.access_token_ttl_seconds,
        role=ctx.role, mfa=True, display_name=ctx.display_name,
    )


# ── Enrôlement TOTP (comptes locaux) — D5 : MFA pour les rôles opérationnels ──
@router.post("/mfa/enroll")
async def mfa_enroll(ctx: SecurityContext = Depends(get_security_context)):
    """Démarre l'enrôlement TOTP du compte courant (session authentifiée requise).

    Génère un secret et le stocke, mais `mfa_enrolled` ne passe à vrai qu'après
    confirmation par un code valide (/mfa/confirm) — un enrôlement interrompu ne
    verrouille donc jamais le compte. Le secret n'est retourné qu'ici, une fois.
    """
    if not ctx.user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="unauthenticated")
    secret = new_secret()
    async with auth_session() as session:
        await session.execute(
            text("UPDATE app_user SET totp_secret=:s, updated_at=now() WHERE id=:id"),
            {"s": secret, "id": ctx.user_id},
        )
        await journal_append(
            session, event_type="auth.mfa.enroll_started", actor_id=ctx.user_id,
            detail={},  # jamais le secret dans le journal
        )
    return {
        "secret": secret,
        "otpauth_uri": provisioning_uri(secret, ctx.email or ctx.user_id),
    }


@router.post("/mfa/confirm", response_model=TokenResponse)
async def mfa_confirm(
    payload: StepUpRequest,
    response: Response,
    ctx: SecurityContext = Depends(get_security_context),
):
    """Confirme l'enrôlement avec un premier code TOTP valide.

    Active `mfa_enrolled` puis RÉÉMET la session (claim mfa=vrai, auth_time frais) :
    les actions à haut risque (step-up) deviennent possibles immédiatement, sans
    reconnexion.
    """
    if not ctx.user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="unauthenticated")
    async with auth_session() as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, email, role, client_scope, display_name, totp_secret "
                    "FROM app_user WHERE id=:id AND status='active'"
                ),
                {"id": ctx.user_id},
            )
        ).first()
        if row is None or not row.totp_secret or not verify_totp(row.totp_secret, payload.totp):
            await journal_append(
                session, event_type="auth.mfa.enroll_failed", actor_id=ctx.user_id,
                detail={"reason": "invalid_code"},
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_totp")
        await session.execute(
            text("UPDATE app_user SET mfa_enrolled=true, updated_at=now() WHERE id=:id"),
            {"id": ctx.user_id},
        )
        auth_time = int(time.time())
        scope = _user_scope(row)
        access = issue_access_token(
            sub=str(row.id), role=row.role, client_scope=scope, mfa=True,
            auth_time=auth_time, email=row.email, display_name=row.display_name,
        )
        raw_refresh, _ = await issue_refresh_token(session, user_id=str(row.id))
        await journal_append(
            session, event_type="auth.mfa.enrolled", actor_id=ctx.user_id, detail={},
        )
    _set_session_cookies(response, access, raw_refresh)
    return TokenResponse(
        access_token=access, expires_in=settings.access_token_ttl_seconds,
        role=row.role, mfa=True, display_name=row.display_name,
    )


@router.post("/logout")
async def logout(response: Response, ctx: SecurityContext = Depends(get_security_context)):
    async with auth_session() as session:
        await revoke_user_tokens(session, user_id=ctx.user_id)
        await journal_append(session, event_type="auth.logout", actor_id=ctx.user_id, detail={})
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(_REFRESH_COOKIE, path="/api/auth")
    return {"message": "logged_out"}


@router.get("/whoami", response_model=WhoAmI)
async def whoami(ctx: SecurityContext = Depends(get_security_context)):
    return WhoAmI(
        user_id=ctx.user_id, email=ctx.email, display_name=ctx.display_name,
        role=ctx.role, client_scope=ctx.client_scope, mfa=ctx.mfa,
        is_multi_client=ctx.is_multi_client,
    )
