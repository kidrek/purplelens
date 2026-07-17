"""Import des catalogues de référence — idempotence et exhaustivité (gated)."""
from __future__ import annotations

import os

import pytest

pytest.importorskip("asyncpg")
pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL requis")


@pytest.fixture(autouse=True)
async def _dispose_engine_between_tests():
    """Pool du moteur async lié à l'event loop : pytest-asyncio ouvre un loop par test.
    On vide le pool avant/après pour éviter « attached to a different loop »."""
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
async def test_import_is_idempotent_and_counts_match():
    from app.db.session import service_session
    from app.reference.catalogs import CATALOGS, catalog_stats, import_catalog

    async with service_session("admin_service") as s:
        # Import deux fois : le second ne doit pas dupliquer (ext_id unique).
        counts1 = {c["id"]: await import_catalog(s, c["id"]) for c in CATALOGS}
        counts2 = {c["id"]: await import_catalog(s, c["id"]) for c in CATALOGS}
        assert counts1 == counts2

        stats = {c["id"]: c for c in await catalog_stats(s)}
        # OWASP Top 10 = 10, CWE Top 25 = 25 (catalogues complets).
        assert stats["owasp"]["count"] >= 10
        assert stats["cwe"]["count"] >= 25
        # Toutes les entrées du socle sont présentes en base.
        for cid, n in counts1.items():
            assert stats[cid]["count"] >= n
            assert stats[cid]["imported"] is True


@pytest.mark.asyncio
async def test_threat_actor_catalog_persists_techniques():
    """Le socle acteurs écrit bien aliases + techniques dans le `data` JSONB (branche has_data)."""
    import json

    from sqlalchemy import text

    from app.db.session import service_session
    from app.reference.catalogs import import_catalog

    async with service_session("admin_service") as s:
        await import_catalog(s, "attack_groups")
        row = (await s.execute(text(
            "SELECT name, data FROM ref_attack_group WHERE ext_id = 'G0016'"))).mappings().first()
    assert row is not None and row["name"] == "APT29"
    data = row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
    assert "T1566" in data["techniques"]
    assert "Cozy Bear" in data["aliases"]


@pytest.mark.asyncio
async def test_actor_techniques_flags_uncovered_and_counts_match():
    """`actor_techniques` retourne *toutes* les techniques de l'acteur : celles hors du
    catalogue importé sont marquées `covered=false` (jamais omises) → le total renvoyé
    correspond au `technique_count` affiché, évitant l'écart compteur/liste du panneau TTP."""
    import json

    from sqlalchemy import text

    from app.api.routes.reference import actor_techniques
    from app.db.session import service_session
    from app.reference.catalogs import import_catalog
    from tests.conftest import make_ctx

    async with service_session("admin_service") as s:
        # Socle des techniques : T1566 y figure, pas 'TZZZ9' (ext_id volontairement absent).
        await import_catalog(s, "attack")
        await s.execute(text(
            "INSERT INTO ref_attack_group (id, ext_id, name, data) "
            "VALUES (gen_random_uuid(), 'GTEST', 'Test Actor', CAST(:d AS jsonb)) "
            "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, data = EXCLUDED.data"
        ), {"d": json.dumps({"aliases": [], "techniques": ["T1566", "TZZZ9"]})})

    res = await actor_techniques("mitre:GTEST", ctx=make_ctx("admin"))
    techniques = res["techniques"]
    # Rien n'est omis : autant d'entrées que d'ext_id stockés sur l'acteur.
    assert len(techniques) == 2
    by_id = {t["ext_id"]: t for t in techniques}
    assert by_id["T1566"]["covered"] is True and by_id["T1566"]["name"] != "T1566"
    # Technique hors socle : présente mais marquée non couverte (nom = ext_id, tactic None).
    assert by_id["TZZZ9"]["covered"] is False
    assert by_id["TZZZ9"]["name"] == "TZZZ9" and by_id["TZZZ9"]["tactic"] is None


@pytest.mark.asyncio
async def test_actor_techniques_prefills_step_description():
    """`actor_techniques` fournit un résumé `description` par technique : priorité à la
    procédure propre à l'acteur (relation `uses`), repli sur la description générique de
    la technique ; marqueurs `(Citation: …)` retirés et résumé tronqué à 200 caractères."""
    import json

    from sqlalchemy import text

    from app.api.routes.reference import actor_techniques
    from app.db.session import service_session
    from tests.conftest import make_ctx

    long_generic = "Adversaries transfer tools onto a compromised host. " + "lorem " * 60 + "(Citation: Foo 2020)"
    async with service_session("admin_service") as s:
        # T1078 : contexte acteur (procédure) prioritaire ; T1105 : pas de procédure → repli
        # sur la description générique longue (teste troncature + nettoyage citation).
        await s.execute(text(
            "INSERT INTO ref_attack_technique (id, ext_id, name, tactic, data) "
            "VALUES (gen_random_uuid(), 'T1078', 'Valid Accounts', 'initial-access', CAST(:d AS jsonb)) "
            "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, data = EXCLUDED.data"
        ), {"d": json.dumps({"tactics": ["initial-access"], "description": "Generic valid-accounts text."})})
        await s.execute(text(
            "INSERT INTO ref_attack_technique (id, ext_id, name, tactic, data) "
            "VALUES (gen_random_uuid(), 'T1105', 'Ingress Tool Transfer', 'command-and-control', CAST(:d AS jsonb)) "
            "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, data = EXCLUDED.data"
        ), {"d": json.dumps({"tactics": ["command-and-control"], "description": long_generic})})
        await s.execute(text(
            "INSERT INTO ref_attack_group (id, ext_id, name, data) "
            "VALUES (gen_random_uuid(), 'GDESC', 'Desc Actor', CAST(:d AS jsonb)) "
            "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, data = EXCLUDED.data"
        ), {"d": json.dumps({"aliases": [], "techniques": ["T1078", "T1105"],
                             "procedures": {"T1078": "GDESC used stolen VPN credentials to log in. (Citation: Bar)"}})})

    res = await actor_techniques("mitre:GDESC", ctx=make_ctx("admin"))
    by_id = {t["ext_id"]: t for t in res["techniques"]}
    # Contexte acteur prioritaire, citation retirée.
    assert by_id["T1078"]["description"].startswith("GDESC used stolen VPN credentials")
    assert "Citation" not in by_id["T1078"]["description"]
    # Repli générique : tronqué (≤ 200 + « … ») et sans marqueur de citation.
    d1105 = by_id["T1105"]["description"]
    assert d1105.startswith("Adversaries transfer tools") and d1105.endswith("…")
    assert len(d1105) <= 203 and "Citation" not in d1105


@pytest.mark.asyncio
async def test_unknown_catalog_raises():
    from app.db.session import service_session
    from app.reference.catalogs import import_catalog

    async with service_session("admin_service") as s:
        with pytest.raises(KeyError):
            await import_catalog(s, "inexistant")
