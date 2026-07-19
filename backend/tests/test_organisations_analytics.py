"""Agrégats de la page Organisations — /analytics/organisations (gated, données réelles).

Vérifie les comptages (total, par rôle / statut / secteur / TLP), la couverture transverse
(audit / application / ressource), le narrowing par les filtres, et l'étanchéité RLS.
"""
from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("asyncpg")
pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL requis")

_INS_ORG = (
    "INSERT INTO organisation (id,nom,code,role,secteur,tlp_defaut,statut,created_at,updated_at) "
    "VALUES (:id,:nom,:code,:role,:secteur,:tlp,:statut,now(),now())"
)
_INS_AUDIT = (
    "INSERT INTO audit (id,client_id,nom,categorie,created_at,updated_at) "
    "VALUES (gen_random_uuid(),:org,'A1','pentest',now(),now())"
)
_INS_APP = (
    "INSERT INTO application (id,client_id,nom,code,created_at,updated_at) "
    "VALUES (gen_random_uuid(),:org,'App1','APP1',now(),now())"
)
_INS_RES = (
    "INSERT INTO ressource (id,organisation_id,nom,created_at,updated_at) "
    "VALUES (gen_random_uuid(),:org,'R1',now(),now())"
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


async def _cleanup(ids):
    from sqlalchemy import text

    from app.db.session import service_session
    async with service_session("admin_service") as s:
        for tbl, col in (("audit", "client_id"), ("application", "client_id"),
                         ("ressource", "organisation_id")):
            await s.execute(text(f"DELETE FROM {tbl} WHERE {col} = ANY(CAST(:ids AS uuid[]))"), {"ids": ids})
        await s.execute(text("DELETE FROM organisation WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids})
        await s.commit()


@pytest.mark.asyncio
async def test_organisations_aggregates_and_filters():
    from sqlalchemy import text

    from app.api.routes.analytics import compute_organisations
    from app.db.session import rls_session, service_session

    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    async with service_session("admin_service") as s:
        # Org A : client / actif / industrie (nace_c) / AMBER — rattachée à 1 audit, 1 app, 1 ressource.
        # Org B : prestataire / inactif / finance (nace_k) / RED — sans rattachement (non couverte).
        await s.execute(text(_INS_ORG), {"id": a, "nom": "Org A", "code": "OANA",
                                         "role": "client", "secteur": "nace_c", "tlp": "AMBER", "statut": "actif"})
        await s.execute(text(_INS_ORG), {"id": b, "nom": "Org B", "code": "OBNA",
                                         "role": "prestataire", "secteur": "nace_k", "tlp": "RED", "statut": "inactif"})
        await s.execute(text(_INS_AUDIT), {"org": a})
        await s.execute(text(_INS_APP), {"org": a})
        await s.execute(text(_INS_RES), {"org": a})
        await s.commit()

    try:
        # Périmètre RLS borné à nos deux orgs → totaux déterministes.
        async with rls_session(user_id=str(uuid.uuid4()), role="auditeur", client_scope=[a, b]) as s:
            d = await compute_organisations(s)
            assert d["total"] == 2
            assert d["by_role"] == {"client": 1, "prestataire": 1}
            assert d["by_statut"] == {"actif": 1, "inactif": 1}
            assert d["by_secteur"] == {"nace_c": 1, "nace_k": 1}
            assert d["by_tlp"] == {"AMBER": 1, "RED": 1}
            assert d["coverage"] == {"audited": 1, "with_apps": 1, "with_ress": 1}

            # Filtre rôle : seule l'org cliente (couverte).
            d2 = await compute_organisations(s, roles=["client"])
            assert d2["total"] == 1
            assert d2["coverage"]["audited"] == 1

            # Filtre statut : seule l'org inactive (prestataire, non couverte).
            d3 = await compute_organisations(s, statuts=["inactif"])
            assert d3["total"] == 1
            assert d3["by_role"] == {"prestataire": 1}
            assert d3["coverage"]["audited"] == 0

            # Filtre secteur / TLP.
            assert (await compute_organisations(s, secteurs=["nace_k"]))["total"] == 1
            assert (await compute_organisations(s, tlps=["AMBER"]))["total"] == 1
    finally:
        await _cleanup([a, b])


@pytest.mark.asyncio
async def test_organisations_rls_isolation():
    """Un rôle cloisonné ne compte que les organisations de son périmètre : l'org d'un
    autre client n'entre ni dans le total, ni dans la couverture."""
    from sqlalchemy import text

    from app.api.routes.analytics import compute_organisations
    from app.db.session import rls_session, service_session

    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    async with service_session("admin_service") as s:
        await s.execute(text(_INS_ORG), {"id": a, "nom": "Rls A", "code": "RLAO",
                                         "role": "client", "secteur": "nace_c", "tlp": "AMBER", "statut": "actif"})
        await s.execute(text(_INS_ORG), {"id": b, "nom": "Rls B", "code": "RLBO",
                                         "role": "client", "secteur": "nace_k", "tlp": "RED", "statut": "actif"})
        await s.execute(text(_INS_AUDIT), {"org": a})
        await s.execute(text(_INS_AUDIT), {"org": b})
        await s.commit()

    try:
        async with rls_session(user_id=str(uuid.uuid4()), role="auditeur", client_scope=[a]) as s:
            d = await compute_organisations(s)  # aucun filtre : seule la RLS borne le périmètre
            assert d["total"] == 1
            assert d["by_role"] == {"client": 1}
            assert d["by_secteur"] == {"nace_c": 1}
            assert d["coverage"]["audited"] == 1  # l'audit de B est hors scope, invisible
    finally:
        await _cleanup([a, b])
