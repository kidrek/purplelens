"""Jetons de session (spec backend v2 §1.3).

- Access token : JWT signé court (~10 min) portant sub, role, client_scope[], mfa,
  auth_time. JAMAIS de secret ni de clé de chiffrement dedans.
- Refresh token : opaque, stocké côté serveur (haché), ROTATION à chaque usage.
  Détection de rejeu → invalidation de toute la FAMILLE (spec v2 §1.3).
"""
from __future__ import annotations

import hashlib
import secrets
import time
import uuid

import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

ALGORITHM = "HS256"


# ── Access token ────────────────────────────────────────────────────────────
def issue_access_token(
    *, sub: str, role: str, client_scope: list[str], mfa: bool, auth_time: int,
    email: str | None = None, display_name: str | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "role": role,
        "client_scope": client_scope,
        "mfa": mfa,
        "auth_time": auth_time,
        "email": email,
        "name": display_name,
        "iat": now,
        "exp": now + settings.access_token_ttl_seconds,
        "iss": "purple-cockpit",
    }
    return jwt.encode(payload, settings.jwt_signing_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token, settings.jwt_signing_key, algorithms=[ALGORITHM], issuer="purple-cockpit"
    )


# ── Refresh token (opaque, rotatif, anti-rejeu) ─────────────────────────────
def _hash_refresh(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def issue_refresh_token(
    session: AsyncSession, *, user_id: str, family_id: str | None = None
) -> tuple[str, str]:
    """Émet un refresh token. Renvoie (raw_token, family_id). Le brut n'est jamais stocké."""
    raw = secrets.token_urlsafe(48)
    family = family_id or str(uuid.uuid4())
    await session.execute(
        text(
            """
            INSERT INTO refresh_token (id, user_id, family_id, token_hash, status,
                                       expires_at, created_at)
            VALUES (gen_random_uuid(), :uid, :fam, :h, 'active',
                    now() + make_interval(secs => :ttl), now())
            """
        ),
        {
            "uid": user_id,
            "fam": family,
            "h": _hash_refresh(raw),
            "ttl": settings.refresh_token_ttl_seconds,
        },
    )
    return raw, family


async def rotate_refresh_token(
    session: AsyncSession, *, raw_token: str
) -> tuple[str | None, str | None, str]:
    """Consomme un refresh token et en émet un nouveau (rotation).

    Renvoie (nouveau_raw, user_id, statut). Statut :
      - 'ok'       : rotation réussie
      - 'replay'   : jeton déjà utilisé/révoqué → invalidation de la famille
      - 'invalid'  : inconnu ou expiré
    """
    h = _hash_refresh(raw_token)
    row = (
        await session.execute(
            text(
                "SELECT id, user_id, family_id, status, expires_at "
                "FROM refresh_token WHERE token_hash = :h FOR UPDATE"
            ),
            {"h": h},
        )
    ).first()

    if row is None:
        return None, None, "invalid"

    if row.status != "active":
        # Rejeu détecté : un token non-actif est présenté → on brûle la famille entière.
        await session.execute(
            text("UPDATE refresh_token SET status='revoked' WHERE family_id=:fam"),
            {"fam": row.family_id},
        )
        return None, row.user_id, "replay"

    # Marque l'ancien comme utilisé, émet le nouveau dans la même famille.
    await session.execute(
        text("UPDATE refresh_token SET status='rotated' WHERE id=:id"), {"id": row.id}
    )
    new_raw, _ = await issue_refresh_token(
        session, user_id=str(row.user_id), family_id=str(row.family_id)
    )
    return new_raw, str(row.user_id), "ok"


async def revoke_user_tokens(session: AsyncSession, *, user_id: str) -> None:
    """Révocation immédiate (désactivation compte, changement rôle/scope)."""
    await session.execute(
        text("UPDATE refresh_token SET status='revoked' WHERE user_id=:uid AND status='active'"),
        {"uid": user_id},
    )
