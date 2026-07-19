"""Agrégats de la page Ressources — /analytics/ressources (gated, données réelles).

Vérifie les comptages (total, par type, par rôle, couverture des organisations), le
narrowing par les filtres (organisation / type / rôle), et l'étanchéité RLS.
"""
from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("asyncpg")
pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL requis")

_INS_ORG = (
    "INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at) "
    "VALUES (:id,:nom,:code,'client','AMBER','actif',now(),now())"
)
_INS_RES = (
    "INSERT INTO ressource (id,organisation_id,nom,type,role,created_at,updated_at) "
    "VALUES (gen_random_uuid(),:org,:nom,:type,:role,now(),now())"
)


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


@pytest.mark.asyncio
async def test_ressources_aggregates_and_filters():
    from sqlalchemy import text

    from app.api.routes.analytics import compute_ressources
    from app.db.session import service_session

    async with service_session("admin_service") as s:
        a, b = str(uuid.uuid4()), str(uuid.uuid4())
        await s.execute(text(_INS_ORG), {"id": a, "nom": "Res A", "code": "RESA"})
        await s.execute(text(_INS_ORG), {"id": b, "nom": "Res B", "code": "RESB"})
        # Org A : 2 humaines (soc, cert), 1 matérielle (sans rôle), 1 logicielle (voc).
        # Org B : 1 humaine (ciso), 1 documentaire (sans rôle).
        seed = [
            (a, "humaine", "soc"), (a, "humaine", "cert"), (a, "materielle", None),
            (a, "logicielle", "voc"), (b, "humaine", "ciso"), (b, "documentaire", None),
        ]
        for i, (org, ty, ro) in enumerate(seed):
            await s.execute(text(_INS_RES), {"org": org, "nom": f"R{i}", "type": ty, "role": ro})

        # Narrowé aux deux orgs semées (service_session voit tout : on isole nos données).
        d = await compute_ressources(s, org_ids=[a, b])
        assert d["total"] == 6
        assert d["by_type"] == {"humaine": 3, "materielle": 1, "logicielle": 1, "documentaire": 1}
        assert d["by_role"] == {"soc": 1, "cert": 1, "voc": 1, "ciso": 1}
        assert d["organisations"]["covered"] == 2
        assert d["organisations"]["total"] >= 2

        # Filtre type
        d2 = await compute_ressources(s, org_ids=[a, b], types=["humaine"])
        assert d2["total"] == 3
        assert d2["by_type"] == {"humaine": 3}
        assert d2["organisations"]["covered"] == 2  # humaine présente dans A et B

        # Filtre rôle
        d3 = await compute_ressources(s, org_ids=[a, b], roles=["soc"])
        assert d3["total"] == 1
        assert d3["by_role"] == {"soc": 1}
        assert d3["organisations"]["covered"] == 1  # soc seulement dans A

        # Filtre organisation
        d4 = await compute_ressources(s, org_ids=[a])
        assert d4["total"] == 4
        assert d4["organisations"]["covered"] == 1

        await s.execute(text("DELETE FROM ressource WHERE organisation_id = ANY(CAST(:ids AS uuid[]))"),
                        {"ids": [a, b]})
        await s.execute(text("DELETE FROM organisation WHERE id = ANY(CAST(:ids AS uuid[]))"),
                        {"ids": [a, b]})
        await s.commit()


@pytest.mark.asyncio
async def test_ressources_rls_isolation():
    """Un rôle cloisonné ne compte que les ressources de son périmètre : la ressource
    d'un autre client n'entre ni dans le total, ni dans la couverture."""
    from sqlalchemy import text

    from app.api.routes.analytics import compute_ressources
    from app.db.session import rls_session, service_session

    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    async with service_session("admin_service") as s:
        await s.execute(text(_INS_ORG), {"id": a, "nom": "Rls A", "code": "RLSA"})
        await s.execute(text(_INS_ORG), {"id": b, "nom": "Rls B", "code": "RLSB"})
        await s.execute(text(_INS_RES), {"org": a, "nom": "RA", "type": "humaine", "role": "soc"})
        await s.execute(text(_INS_RES), {"org": b, "nom": "RB", "type": "humaine", "role": "cert"})
        await s.commit()

    try:
        async with rls_session(user_id=str(uuid.uuid4()), role="auditeur", client_scope=[a]) as s:
            d = await compute_ressources(s)  # aucun filtre : seule la RLS borne le périmètre
            assert d["total"] == 1
            assert d["by_role"] == {"soc": 1}
            assert d["organisations"]["covered"] == 1
            assert d["organisations"]["total"] == 1  # seule l'org A est visible dans ce scope
    finally:
        async with service_session("admin_service") as s:
            await s.execute(text("DELETE FROM ressource WHERE organisation_id = ANY(CAST(:ids AS uuid[]))"),
                            {"ids": [a, b]})
            await s.execute(text("DELETE FROM organisation WHERE id = ANY(CAST(:ids AS uuid[]))"),
                            {"ids": [a, b]})
            await s.commit()
