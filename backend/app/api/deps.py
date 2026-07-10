"""Extraction du contexte de sécurité depuis l'access token (cookie HttpOnly ou header).

Aucune décision d'autorisation ici — seulement l'identification. Le contexte est
posé sur request.state pour les dépendances RBAC et la pose du contexte RLS.
"""
from __future__ import annotations

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.security.context import SecurityContext
from app.security.tokens import decode_access_token

ACCESS_COOKIE = "pc_access"


def _extract_token(request: Request) -> str | None:
    # Navigateur : cookie HttpOnly. Comptes de service : en-tête Authorization.
    cookie = request.cookies.get(ACCESS_COOKIE)
    if cookie:
        return cookie
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


class SecurityContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        token = _extract_token(request)
        if token:
            try:
                claims = decode_access_token(token)
                request.state.security_context = SecurityContext(
                    user_id=claims["sub"],
                    role=claims["role"],
                    client_scope=list(claims.get("client_scope") or []),
                    mfa=bool(claims.get("mfa")),
                    auth_time=int(claims.get("auth_time") or 0),
                    email=claims.get("email"),
                    display_name=claims.get("name"),
                )
            except jwt.PyJWTError:
                request.state.security_context = None
        else:
            request.state.security_context = None
        return await call_next(request)
