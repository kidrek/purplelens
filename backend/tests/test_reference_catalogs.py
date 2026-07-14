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
async def test_unknown_catalog_raises():
    from app.db.session import service_session
    from app.reference.catalogs import import_catalog

    async with service_session("admin_service") as s:
        with pytest.raises(KeyError):
            await import_catalog(s, "inexistant")
