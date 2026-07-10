"""Accès base de données et POSE DU CONTEXTE RLS — le patron obligatoire (DAT §2.2).

À chaque requête HTTP, une dépendance FastAPI ouvre une transaction et pose :
    SET LOCAL app.user_id / app.role / app.client_scope
Les politiques RLS lisent ces GUC (voir schema_evidence.sql). Le rôle app_api est
NOBYPASSRLS : la RLS s'applique à lui, c'est le filet qui tient même si l'application
se trompe (spec backend v2 §3.3).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)

SessionMaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _format_scope(client_scope: list[str] | None) -> str:
    """Sérialise le scope en littéral tableau PostgreSQL. Vide => '' (tous, selon rôle)."""
    if not client_scope:
        return ""
    # uuid[] : '{uuid1,uuid2}'
    joined = ",".join(str(c) for c in client_scope)
    return "{" + joined + "}"


@asynccontextmanager
async def rls_session(
    *, user_id: str | None, role: str, client_scope: list[str] | None
) -> AsyncIterator[AsyncSession]:
    """Ouvre une session dont chaque transaction porte le contexte de sécurité RLS.

    SET LOCAL est transactionnel : le contexte disparaît au COMMIT/ROLLBACK, il ne
    peut pas fuiter vers une autre requête réutilisant la connexion du pool.
    """
    async with SessionMaker() as session:
        # Le contexte doit être posé DANS la transaction où les requêtes s'exécutent.
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": user_id or ""},
        )
        await session.execute(
            text("SELECT set_config('app.role', :role, true)"),
            {"role": role},
        )
        await session.execute(
            text("SELECT set_config('app.client_scope', :scope, true)"),
            {"scope": _format_scope(client_scope)},
        )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def auth_session() -> AsyncIterator[AsyncSession]:
    """Session d'amorçage pour l'authentification.

    Utilisée UNIQUEMENT pour les tables non cloisonnées (app_user, refresh_token,
    journal) avant qu'un contexte de sécurité n'existe. On pose tout de même un rôle
    de service neutre pour que les fonctions RLS ne lèvent pas sur GUC absent.
    """
    async with SessionMaker() as session:
        await session.execute(text("SELECT set_config('app.role', 'admin_service', true)"))
        await session.execute(text("SELECT set_config('app.user_id', '', true)"))
        await session.execute(text("SELECT set_config('app.client_scope', '', true)"))
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def service_session(role: str) -> AsyncIterator[AsyncSession]:
    """Session pour les comptes de service (jobs, report_render) — scope vide = tous clients
    dans la limite du rôle de service (voir politiques RLS audit_dek)."""
    async with rls_session(user_id=None, role=role, client_scope=None) as s:
        yield s
