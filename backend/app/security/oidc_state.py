"""État éphémère du flux OIDC (PKCE verifier lié au `state`) — durcissement P2.

En mémoire (dict in-process), le verifier PKCE ne survivait pas au multi-worker : le
callback peut être servi par un worker différent de celui de /oidc/start, cassant le
flux (ou forçant un worker unique). On stocke l'état dans Redis avec un TTL, partagé
entre workers et expirant tout seul. Le `state` est consommé une seule fois (anti-rejeu).
"""
from __future__ import annotations

import redis.asyncio as aioredis

from app.config import settings

# TTL de l'aller-retour d'autorisation OIDC (l'utilisateur s'authentifie chez l'IdP).
_PKCE_TTL_SECONDS = 600  # 10 min

_redis: aioredis.Redis | None = None


def _client() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis


def _key(state: str) -> str:
    return f"oidc:pkce:{state}"


async def store_pkce(state: str, verifier: str) -> None:
    """Associe le code_verifier au state, avec expiration automatique."""
    await _client().set(_key(state), verifier, ex=_PKCE_TTL_SECONDS)


async def pop_pkce(state: str) -> str | None:
    """Récupère ET consomme le verifier (usage unique). None si inconnu/expiré."""
    r = _client()
    key = _key(state)
    verifier = await r.get(key)
    if verifier is not None:
        await r.delete(key)
    return verifier
