"""Limitation de débit des routes sensibles (durcissement P1).

Fenêtre fixe adossée à Redis (déjà présent comme broker Celery). Clé par IP source +
nom de bucket. Objectif : freiner le bourrage d'identifiants et de codes TOTP sur
/login, /refresh, /step-up — complément de l'anti-rejeu TOTP et du message d'échec
uniforme.

Dégradation gracieuse : si Redis est indisponible, on n'ouvre AUCUNE brèche
d'autorisation (les portes applicatives restent en place) et on laisse passer pour
préserver la disponibilité ; l'incident Redis est visible côté supervision.
"""
from __future__ import annotations

import time

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.config import settings

_redis: aioredis.Redis | None = None


def _client() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis


def client_ip(request: Request) -> str:
    """IP source réelle derrière le reverse proxy (premier saut de X-Forwarded-For)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _allow(bucket: str, limit: int, window: int) -> bool:
    """True si la requête reste sous la limite pour la fenêtre courante."""
    r = _client()
    key = f"rl:{bucket}:{int(time.time()) // window}"
    try:
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, window)
        return count <= limit
    except Exception:
        # Redis KO : disponibilité préservée, contrôles applicatifs inchangés.
        return True


def rate_limit(name: str, *, limit: int, window: int):
    """Fabrique une dépendance FastAPI limitant `limit` requêtes / `window` s par IP."""

    async def _dep(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return  # désactivé (ex. runner de tests) — voir Settings.rate_limit_enabled
        ip = client_ip(request)
        if not await _allow(f"{name}:{ip}", limit, window):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate_limited",
                headers={"Retry-After": str(window)},
            )

    return _dep
