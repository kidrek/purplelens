"""Schémas d'authentification (spec backend v2 §2/§3)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class LocalLoginRequest(BaseModel):
    """Connexion par compte local (repli — spec v2 §2.3, Argon2id)."""

    # `str` et non `EmailStr` : les domaines internes/réservés (ex. « .local »,
    # RFC 6761) sont légitimes ici et rejetés par EmailStr. L'identité réelle est
    # vérifiée par la recherche en base + Argon2id, pas par la forme de l'adresse.
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)
    totp: str | None = None  # exigé si MFA enrôlée (rôles opérationnels — D5)


class TokenResponse(BaseModel):
    """Jeton d'accès renvoyé au client (l'access token part surtout en cookie HttpOnly)."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    role: str
    mfa: bool
    display_name: str | None = None


class StepUpRequest(BaseModel):
    """Réauthentification MFA pour action à haut risque (spec v2 §3.4)."""

    totp: str = Field(min_length=6, max_length=8)


class OidcStart(BaseModel):
    """URL d'autorisation OIDC + paramètres PKCE (à conserver côté serveur/session)."""

    authorization_url: str
    state: str


class RefreshRequest(BaseModel):
    refresh_token: str


class WhoAmI(BaseModel):
    user_id: str
    email: str | None = None
    display_name: str | None = None
    role: str
    client_scope: list[str]
    mfa: bool
    is_multi_client: bool
