"""Accès base synchrone pour les workers Celery.

Celery n'est pas asynchrone : on utilise un moteur SQLAlchemy sync (psycopg) plutôt
que le moteur async de l'API. Le worker pose lui aussi le contexte RLS (rôle de
service) : la défense en profondeur ne dépend pas du chemin d'accès.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# On réutilise l'URL API mais en pilote synchrone psycopg.
_sync_url = settings.database_url.replace("+asyncpg", "+psycopg")
_engine = create_engine(_sync_url, pool_pre_ping=True, future=True)
SyncSessionMaker = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False)


@contextmanager
def service_session_sync(role: str, *, client_scope: str = ""):
    """Session synchrone portant un contexte de service (RLS active)."""
    session = SyncSessionMaker()
    try:
        session.execute(text("SELECT set_config('app.role', :r, true)"), {"r": role})
        session.execute(text("SELECT set_config('app.user_id', '', true)"))
        session.execute(
            text("SELECT set_config('app.client_scope', :s, true)"), {"s": client_scope}
        )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
