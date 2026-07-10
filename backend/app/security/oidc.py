"""OIDC — Authorization Code + PKCE contre Keycloak (spec backend v2 §1.1).

L'IdP prouve *qui vous êtes*. Le rôle et les clients rattachés NE viennent PAS de
l'IdP : ils sont gérés dans le produit (table app_user). Une claim de groupe peut
*proposer* un rôle par défaut à la première connexion, jamais l'imposer.
"""
from __future__ import annotations

import base64
import hashlib
import secrets

import httpx

from app.config import settings


def generate_pkce() -> tuple[str, str]:
    """Renvoie (code_verifier, code_challenge S256)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


async def _discovery() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{settings.oidc_issuer}/.well-known/openid-configuration")
        resp.raise_for_status()
        return resp.json()


async def authorization_url(*, state: str, code_challenge: str) -> str:
    conf = await _discovery()
    from urllib.parse import urlencode

    params = {
        "client_id": settings.oidc_client_id,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": settings.oidc_redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{conf['authorization_endpoint']}?{urlencode(params)}"


async def exchange_code(*, code: str, code_verifier: str) -> dict:
    """Échange le code d'autorisation contre les jetons OIDC (id_token, access_token)."""
    conf = await _discovery()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.oidc_redirect_uri,
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret,
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(conf["token_endpoint"], data=data)
        resp.raise_for_status()
        return resp.json()


async def userinfo(access_token: str) -> dict:
    conf = await _discovery()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            conf["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()
