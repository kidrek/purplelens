"""« Ma fiche » — self-service de la ressource auditeur liée au compte (gated).

Prouve qu'un compte opérationnel peut se déclarer comme ressource (type humaine) dans
une organisation de son périmètre, se rendant ainsi sélectionnable comme auditeur, tout
en restant borné par le scope (org hors périmètre → 403).
"""
from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("asyncpg")
pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL requis")


@pytest.fixture(autouse=True)
async def _dispose_engine_between_tests():
    from app.db.session import engine
    try:
        await engine.dispose()
    except Exception:  # noqa: BLE001
        pass
    yield
    try:
        await engine.dispose()
    except Exception:  # noqa: BLE001
        pass


async def _seed_org_and_user(role: str = "operateur"):
    """Crée une organisation + un compte (scope = cette org) et retourne (org_id, user_id)."""
    from sqlalchemy import text

    from app.db.session import service_session

    org = str(uuid.uuid4())
    user = str(uuid.uuid4())
    async with service_session("admin_service") as s:
        await s.execute(text(
            "INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at) "
            "VALUES (:o,'Presta','PRST','prestataire','AMBER','actif',now(),now())"
        ), {"o": org})
        await s.execute(text(
            "INSERT INTO app_user (id,email,display_name,role,client_scope,status,created_at,updated_at) "
            "VALUES (:u,:e,'Op Test',:r,ARRAY[:o]::uuid[],'active',now(),now())"
        ), {"u": user, "e": f"{user}@purple.local", "r": role, "o": org})
    return org, user


async def _cleanup(org: str, user: str):
    from sqlalchemy import text

    from app.db.session import service_session
    async with service_session("admin_service") as s:
        await s.execute(text("DELETE FROM ressource WHERE app_user_id=:u"), {"u": user})
        await s.execute(text("DELETE FROM app_user WHERE id=:u"), {"u": user})
        await s.execute(text("DELETE FROM organisation WHERE id=:o"), {"o": org})


@pytest.mark.asyncio
async def test_profile_upsert_creates_linked_human_resource_in_scope():
    from app.api.routes.profile import MyResourceIn, my_resources, upsert_my_resource
    from tests.conftest import make_ctx

    org, user = await _seed_org_and_user()
    try:
        ctx = make_ctx("operateur", user_id=user, client_scope=[org])

        created = await upsert_my_resource(
            MyResourceIn(organisation_id=uuid.UUID(org), nom="Alice Auditrice",
                         role="auditeur", competences=["Red Team", "Pentest applicatif"],
                         contact="alice@presta.example"),
            ctx=ctx,
        )
        # Lien + type imposés par le serveur.
        assert created["app_user_id"] == user
        assert created["organisation_id"] == org
        assert created["type"] == "humaine"
        assert created["nom"] == "Alice Auditrice"
        assert created["competences"] == ["Red Team", "Pentest applicatif"]
        rid = created["id"]

        # Upsert idempotent : deuxième appel sur la même org → MÊME fiche, champs mis à jour.
        updated = await upsert_my_resource(
            MyResourceIn(organisation_id=uuid.UUID(org), nom="Alice A.", role="auditeur"),
            ctx=ctx,
        )
        assert updated["id"] == rid
        assert updated["nom"] == "Alice A."

        # Elle figure dans « mes fiches » (et donc dans la liste ressources du picker, même RLS).
        mine = await my_resources(ctx=ctx)
        assert [r["id"] for r in mine["resources"]] == [rid]
        assert mine["resources"][0]["type"] == "humaine"
    finally:
        await _cleanup(org, user)


@pytest.mark.asyncio
async def test_profile_upsert_rejects_out_of_scope_org():
    from fastapi import HTTPException

    from app.api.routes.profile import MyResourceIn, upsert_my_resource
    from tests.conftest import make_ctx

    org, user = await _seed_org_and_user()
    other_org = str(uuid.uuid4())  # organisation hors périmètre de l'utilisateur
    try:
        ctx = make_ctx("operateur", user_id=user, client_scope=[org])
        with pytest.raises(HTTPException) as exc:
            await upsert_my_resource(
                MyResourceIn(organisation_id=uuid.UUID(other_org), nom="Intrus"), ctx=ctx,
            )
        assert exc.value.status_code == 403
    finally:
        await _cleanup(org, user)
