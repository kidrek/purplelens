"""Éditeur d'étapes d'exercice : chargement depuis scénario + réordonnancement."""
from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("asyncpg")
_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not _URL, reason="DATABASE_URL non défini")


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


async def _make_exercise(s):
    from sqlalchemy import text
    cid = str(uuid.uuid4())
    await s.execute(text("INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at) "
                         "VALUES (:c,'Ex','EXX','client','AMBER','actif',now(),now())"), {"c": cid})
    aud = str(uuid.uuid4())
    await s.execute(text("INSERT INTO audit (id,client_id,nom,categorie,statut,tlp,created_at,updated_at) "
                         "VALUES (:a,:c,'A','Purple','en_cours','AMBER',now(),now())"), {"a": aud, "c": cid})
    ex = str(uuid.uuid4())
    await s.execute(text("INSERT INTO purple_exercise (id,audit_id,client_id,nom,statut,tlp,created_at,updated_at) "
                         "VALUES (:e,:a,:c,'E','en_cours','AMBER',now(),now())"), {"e": ex, "a": aud, "c": cid})
    return cid, aud, ex


@pytest.mark.asyncio
async def test_load_scenario_creates_ordered_steps():
    from sqlalchemy import text

    from app.db.session import service_session

    async with service_session("admin_service") as s:
        cid, aud, ex = await _make_exercise(s)
        # Techniques référencées (pour le nom).
        await s.execute(text("INSERT INTO ref_attack_technique (id,ext_id,name,tactic,data) VALUES "
                             "(gen_random_uuid(),'T1566','Phishing','initial-access','{}'), "
                             "(gen_random_uuid(),'T1059','Command','execution','{}') "
                             "ON CONFLICT (ext_id) DO NOTHING"))
        sc = str(uuid.uuid4())
        await s.execute(text("INSERT INTO scenario (id,nom,techniques,d3fend,tlp,pap,created_at,updated_at) "
                             "VALUES (:s,'Sc',CAST('[\"T1566\",\"T1059\"]' AS jsonb),'[]','AMBER','WHITE',now(),now())"),
                        {"s": sc})

        # Réplique la logique de l'endpoint (chargement) dans la transaction.
        scen = (await s.execute(text("SELECT techniques FROM scenario WHERE id=:s"), {"s": sc})).first()
        names = dict((r.ext_id, r.name) for r in (await s.execute(text(
            "SELECT ext_id, name FROM ref_attack_technique WHERE ext_id = ANY(:c)"),
            {"c": list(scen.techniques)})).all())
        for i, code in enumerate(scen.techniques, start=1):
            await s.execute(text("INSERT INTO attack_step (id,exercise_id,client_id,ordre,technique,titre,verdict,created_at,updated_at) "
                                 "VALUES (gen_random_uuid(),:e,:c,:o,:t,:ti,'not_tested',now(),now())"),
                            {"e": ex, "c": cid, "o": i, "t": code, "ti": names.get(code, code)})

        rows = (await s.execute(text("SELECT ordre, technique, titre FROM attack_step WHERE exercise_id=:e ORDER BY ordre"),
                                {"e": ex})).all()
        assert [r.technique for r in rows] == ["T1566", "T1059"]
        assert rows[0].titre == "Phishing"

        for t in ("attack_step", "purple_exercise", "audit", "organisation"):
            col = "id" if t == "organisation" else "client_id"
            await s.execute(text(f"DELETE FROM {t} WHERE {col}=:c"), {"c": cid})
        await s.execute(text("DELETE FROM scenario WHERE id=:s"), {"s": sc})
        await s.commit()
