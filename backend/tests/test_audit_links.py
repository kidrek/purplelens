"""Applications cibles & auditeurs assignés sur l'Audit (cahier §2, entité Audits).

Deux familles :
  - Gardes déclaratives (sans base) : les champs existent, sont en liste blanche,
    et le modèle porte bien les colonnes ARRAY(UUID).
  - Règle d'intégrité (base migrée requise, TEST_DATABASE_URL) :
    « applications ciblées ∈ client de l'audit » et auditeurs = ressources humaines.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy.dialects.postgresql import ARRAY

from app.api.registry import spec_for
from app.models.business import Audit


def test_audit_writable_exposes_applications_and_auditeurs():
    spec = spec_for("audits")
    assert "applications" in spec.writable
    assert "auditeurs" in spec.writable
    # nom/period/seq restent dérivés serveur, jamais fournis par le client
    assert "nom" in spec.auto and "nom" not in spec.writable


def test_audit_model_columns_are_uuid_arrays():
    cols = Audit.__table__.columns
    assert isinstance(cols["applications"].type, ARRAY)
    assert isinstance(cols["auditeurs"].type, ARRAY)
    assert not cols["auditeurs"].nullable


# ── Règle d'intégrité (base réelle) ─────────────────────────────────────────
_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.skipif(not _URL, reason="TEST_DATABASE_URL non défini")
@pytest.mark.anyio
async def test_applications_must_belong_to_audit_client():
    """Une application d'un autre client est refusée en 422 (jamais un 500)."""
    from fastapi import HTTPException
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.api import service
    from app.models.business import Application, Organisation

    engine = create_async_engine(_URL.replace("postgresql://", "postgresql+asyncpg://"))
    async with AsyncSession(engine) as session:
        # Contexte RLS de service : sans app.role posé, la RLS refuse tout INSERT
        # (organisation exige un rôle créateur — cf. app_role_may_create_org).
        await session.execute(text("SELECT set_config('app.role', 'admin_service', true)"))
        await session.execute(text("SELECT set_config('app.user_id', '', true)"))
        await session.execute(text("SELECT set_config('app.client_scope', '', true)"))
        client_a = Organisation(nom="ClientA", code="clia", role="client")
        client_b = Organisation(nom="ClientB", code="clib", role="client")
        session.add_all([client_a, client_b])
        await session.flush()
        app_b = Application(client_id=client_b.id, nom="AppB", code="appb")
        session.add(app_b)
        await session.flush()

        with pytest.raises(HTTPException) as exc:
            await service._validate_audit_links(
                session, {"applications": [str(app_b.id)]}, client_id=client_a.id
            )
        assert exc.value.status_code == 422
        assert exc.value.detail == "application_not_in_audit_client"
        await session.rollback()
    await engine.dispose()


@pytest.mark.skipif(not _URL, reason="TEST_DATABASE_URL non défini")
@pytest.mark.anyio
async def test_auditeurs_must_be_existing_human_resources():
    from fastapi import HTTPException
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.api import service
    from app.models.business import Organisation, Ressource

    engine = create_async_engine(_URL.replace("postgresql://", "postgresql+asyncpg://"))
    async with AsyncSession(engine) as session:
        # Contexte RLS de service (cf. test ci-dessus) : requis pour l'INSERT organisation.
        await session.execute(text("SELECT set_config('app.role', 'admin_service', true)"))
        await session.execute(text("SELECT set_config('app.user_id', '', true)"))
        await session.execute(text("SELECT set_config('app.client_scope', '', true)"))
        org = Organisation(nom="Presta", code="prst", role="prestataire")
        session.add(org)
        await session.flush()
        scanner = Ressource(organisation_id=org.id, nom="Scanner X", type="logicielle")
        session.add(scanner)
        await session.flush()

        # Ressource inconnue → 422 unknown_auditeur
        with pytest.raises(HTTPException) as exc:
            await service._validate_audit_links(
                session, {"auditeurs": [str(uuid.uuid4())]}, client_id=None
            )
        assert exc.value.detail == "unknown_auditeur"

        # Ressource non humaine → 422 auditeur_not_human_resource
        with pytest.raises(HTTPException) as exc:
            await service._validate_audit_links(
                session, {"auditeurs": [str(scanner.id)]}, client_id=None
            )
        assert exc.value.detail == "auditeur_not_human_resource"
        await session.rollback()
    await engine.dispose()
