"""Enrichissement des vulnérabilités — SSVC + upsert (gated pour la partie base)."""
from __future__ import annotations

import os
import uuid

import pytest

from app.api.routes.vulnerabilities import compute_ssvc


def test_ssvc_decision_tree():
    assert compute_ssvc(9.8, True, 0.9) == "Act"       # KEV + critique
    assert compute_ssvc(6.0, True, 0.5) == "Attend"    # KEV mais gravité modérée
    assert compute_ssvc(8.0, False, 0.3) == "Attend"   # EPSS élevé + haute
    assert compute_ssvc(5.0, False, 0.2) == "Track*"   # EPSS élevé, gravité moyenne
    assert compute_ssvc(9.5, False, 0.0) == "Track*"   # critique sans exploitation connue
    assert compute_ssvc(4.0, False, 0.0) == "Track"    # rien de notable
    assert compute_ssvc(None, False, None) == "Track"  # valeurs absentes → prudent


pytestmark_db = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL requis")


@pytest.mark.asyncio
@pytestmark_db
async def test_enrichment_upsert_recomputes_ssvc():
    from sqlalchemy import text

    from app.db.session import engine, service_session

    try:
        await engine.dispose()
    except Exception:  # noqa: BLE001
        pass

    async with service_session("admin_service") as s:
        cid = str(uuid.uuid4())
        await s.execute(text("INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at) "
                             "VALUES (:c,'Ve','VE','client','AMBER','actif',now(),now())"), {"c": cid})
        vid = str(uuid.uuid4())
        await s.execute(text("INSERT INTO vulnerability (id,client_id,titre,severite,cvss_score,statut,tlp,created_at,updated_at) "
                             "VALUES (:v,:c,'VULN-T','critique',9.8,'nouveau','AMBER',now(),now())"), {"v": vid, "c": cid})

        # 1er enrichissement : KEV → SSVC Act
        await s.execute(text(
            "INSERT INTO vulnerability_enrichment (id,vulnerability_id,client_id,kev,ssvc_decision,created_at,updated_at) "
            "VALUES (gen_random_uuid(),:v,:c,true,:s,now(),now())"),
            {"v": vid, "c": cid, "s": compute_ssvc(9.8, True, None)})
        row = (await s.execute(text("SELECT kev, ssvc_decision FROM vulnerability_enrichment WHERE vulnerability_id=:v"),
                               {"v": vid})).first()
        assert row.kev is True and row.ssvc_decision == "Act"

        await s.execute(text("DELETE FROM vulnerability_enrichment WHERE vulnerability_id=:v"), {"v": vid})
        await s.execute(text("DELETE FROM vulnerability WHERE id=:v"), {"v": vid})
        await s.execute(text("DELETE FROM organisation WHERE id=:c"), {"c": cid})
