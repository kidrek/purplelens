"""Agrégation du cockpit — indicateurs sur données réelles (gated)."""
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


@pytest.mark.asyncio
async def test_cockpit_detection_rate_and_blind_spots():
    from sqlalchemy import text

    from app.api.routes.analytics import compute_cockpit
    from app.db.session import service_session

    async with service_session("admin_service") as s:
        cid = str(uuid.uuid4())
        await s.execute(text("INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at) "
                             "VALUES (:c,'Ck','CK','client','AMBER','actif',now(),now())"), {"c": cid})
        aud = str(uuid.uuid4())
        await s.execute(text("INSERT INTO audit (id,client_id,nom,categorie,statut,tlp,created_at,updated_at) "
                             "VALUES (:a,:c,'A','Purple','en_cours','AMBER',now(),now())"), {"a": aud, "c": cid})
        ex = str(uuid.uuid4())
        await s.execute(text("INSERT INTO purple_exercise (id,audit_id,client_id,nom,statut,tlp,created_at,updated_at) "
                             "VALUES (:e,:a,:c,'E','en_cours','AMBER',now(),now())"), {"e": ex, "a": aud, "c": cid})
        # 2 prévenu, 1 sans télémétrie, 1 non testé → détection = 2/3 = 67%, angle mort = 1
        for i, v in enumerate(["prevented", "prevented", "no_telemetry", "not_tested"]):
            await s.execute(text("INSERT INTO attack_step (id,exercise_id,client_id,ordre,technique,verdict,created_at,updated_at) "
                                 "VALUES (gen_random_uuid(),:e,:c,:o,:t,:v,now(),now())"),
                            {"e": ex, "c": cid, "o": i + 1, "t": f"T{9000 + i}", "v": v})

        d = await compute_cockpit(s)
        assert d["posture"]["tested"] >= 3
        assert d["posture"]["caught"] >= 2
        assert d["kpis"]["blind_spots"] >= 1
        assert d["kpis"]["detection_rate"] is not None
        assert "audits_by_type" in d and "journal" in d

        # Nettoyage (ordre FK)
        await s.execute(text("DELETE FROM attack_step WHERE exercise_id=:e"), {"e": ex})
        await s.execute(text("DELETE FROM purple_exercise WHERE id=:e"), {"e": ex})
        await s.execute(text("DELETE FROM audit WHERE id=:a"), {"a": aud})
        await s.execute(text("DELETE FROM organisation WHERE id=:c"), {"c": cid})


@pytest.mark.asyncio
async def test_cockpit_tactic_coverage_and_trend():
    """Bande kill-chain (états par tactique) et tendance de détection présentes."""
    from sqlalchemy import text

    from app.api.routes.analytics import compute_cockpit
    from app.db.session import service_session

    async with service_session("admin_service") as s:
        cid = str(uuid.uuid4())
        await s.execute(text(
            "INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at) "
            "VALUES (:c,'Kc','KCX','client','AMBER','actif',now(),now())"), {"c": cid})
        await s.execute(text(
            "INSERT INTO ref_attack_technique (id,ext_id,name,tactic,data) VALUES "
            "(gen_random_uuid(),'T9101','A','initial-access','{}'), "
            "(gen_random_uuid(),'T9102','B','impact','{}') ON CONFLICT (ext_id) DO NOTHING"))
        aud = str(uuid.uuid4())
        await s.execute(text(
            "INSERT INTO audit (id,client_id,nom,categorie,statut,tlp,created_at,updated_at) "
            "VALUES (:a,:c,'A','Purple','en_cours','AMBER',now(),now())"), {"a": aud, "c": cid})
        ex = str(uuid.uuid4())
        await s.execute(text(
            "INSERT INTO purple_exercise (id,audit_id,client_id,nom,date,statut,tlp,created_at,updated_at) "
            "VALUES (:e,:a,:c,'E',current_date,'en_cours','AMBER',now(),now())"), {"e": ex, "a": aud, "c": cid})
        # initial-access détecté ; impact joué mais sans télémétrie -> écart.
        await s.execute(text(
            "INSERT INTO attack_step (id,exercise_id,client_id,ordre,technique,verdict,created_at,updated_at) VALUES "
            "(gen_random_uuid(),:e,:c,1,'T9101','alerted',now(),now()), "
            "(gen_random_uuid(),:e,:c,2,'T9102','no_telemetry',now(),now())"), {"e": ex, "c": cid})

        d = await compute_cockpit(s, client_id=cid)
        tc = {t["tactic"]: t for t in d["tactic_coverage"]}
        assert tc["initial-access"]["state"] == "detected"
        assert tc["impact"]["state"] == "gap"
        # Ordre kill-chain : initial-access avant impact.
        order = [t["tactic"] for t in d["tactic_coverage"]]
        assert order.index("initial-access") < order.index("impact")
        # Tendance : au moins un point, caught/tested cohérents (1 détecté / 2 testés).
        assert d["trend"], "tendance vide"
        last = d["trend"][-1]
        assert last["tested"] == 2 and last["caught"] == 1 and last["pct"] == 50

        for t in ("attack_step", "purple_exercise", "audit"):
            await s.execute(text(f"DELETE FROM {t} WHERE client_id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM organisation WHERE id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM ref_attack_technique WHERE ext_id IN ('T9101','T9102')"))
        await s.commit()
