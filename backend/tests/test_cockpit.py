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
async def test_cockpit_posture_uses_last_run_per_audit():
    """La posture ne compte que le dernier run de chaque audit (pool maquette).

    Un run ancien plein d'angles morts ne doit plus peser une fois rejoué :
    seules les étapes du run le plus récent alimentent verdicts/KPI/angles morts.
    """
    from sqlalchemy import text

    from app.api.routes.analytics import compute_cockpit
    from app.db.session import service_session

    async with service_session("admin_service") as s:
        cid = str(uuid.uuid4())
        await s.execute(text("INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at) "
                             "VALUES (:c,'Lr','LRX','client','AMBER','actif',now(),now())"), {"c": cid})
        aud = str(uuid.uuid4())
        await s.execute(text("INSERT INTO audit (id,client_id,nom,categorie,statut,tlp,created_at,updated_at) "
                             "VALUES (:a,:c,'A','Purple','en_cours','AMBER',now(),now())"), {"a": aud, "c": cid})
        old_ex, new_ex = str(uuid.uuid4()), str(uuid.uuid4())
        await s.execute(text("INSERT INTO purple_exercise (id,audit_id,client_id,nom,date,statut,tlp,created_at,updated_at) VALUES "
                             "(:o,:a,:c,'Run 1',current_date - 30,'clos','AMBER',now(),now()), "
                             "(:n,:a,:c,'Run 2',current_date,'en_cours','AMBER',now(),now())"),
                        {"o": old_ex, "n": new_ex, "a": aud, "c": cid})
        # Run ancien : 2 angles morts. Run récent : 1 prévenu + 1 alerté.
        await s.execute(text("INSERT INTO attack_step (id,exercise_id,client_id,ordre,technique,verdict,created_at,updated_at) VALUES "
                             "(gen_random_uuid(),:o,:c,1,'T9201','no_telemetry',now(),now()), "
                             "(gen_random_uuid(),:o,:c,2,'T9202','no_telemetry',now(),now()), "
                             "(gen_random_uuid(),:n,:c,1,'T9201','prevented',now(),now()), "
                             "(gen_random_uuid(),:n,:c,2,'T9202','alerted',now(),now())"),
                        {"o": old_ex, "n": new_ex, "c": cid})

        d = await compute_cockpit(s, client_id=cid)
        # Seul le run récent compte : 2 testées, 2 couvertes, 100 %, zéro angle mort.
        assert d["posture"]["tested"] == 2
        assert d["posture"]["caught"] == 2
        assert d["posture"]["verdicts"].get("no_telemetry", 0) == 0
        assert d["kpis"]["detection_rate"] == 100
        assert d["kpis"]["blind_spots"] == 0
        assert d["blind_tactics"] == []

        for t in ("attack_step", "purple_exercise", "audit"):
            await s.execute(text(f"DELETE FROM {t} WHERE client_id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM organisation WHERE id=:c"), {"c": cid})
        await s.commit()


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
            "(gen_random_uuid(),'T9102','B','impact','{}'), "
            "(gen_random_uuid(),'T9103','C','discovery','{}'), "
            "(gen_random_uuid(),'T9104','D','execution','{}') ON CONFLICT (ext_id) DO NOTHING"))
        aud = str(uuid.uuid4())
        await s.execute(text(
            "INSERT INTO audit (id,client_id,nom,categorie,statut,tlp,created_at,updated_at) "
            "VALUES (:a,:c,'A','Purple','en_cours','AMBER',now(),now())"), {"a": aud, "c": cid})
        ex, old_ex = str(uuid.uuid4()), str(uuid.uuid4())
        await s.execute(text(
            "INSERT INTO purple_exercise (id,audit_id,client_id,nom,date,statut,tlp,created_at,updated_at) VALUES "
            "(:e,:a,:c,'E',current_date,'en_cours','AMBER',now(),now()), "
            "(:o,:a,:c,'E-old',current_date - 30,'clos','AMBER',now(),now())"),
            {"e": ex, "o": old_ex, "a": aud, "c": cid})
        # Run courant : initial-access détecté ; impact joué mais sans télémétrie -> écart ;
        # execution jamais testée (not_tested) -> absente de la bande.
        # Run ancien : discovery testée mais rejouée depuis -> absente de la bande.
        await s.execute(text(
            "INSERT INTO attack_step (id,exercise_id,client_id,ordre,technique,verdict,created_at,updated_at) VALUES "
            "(gen_random_uuid(),:e,:c,1,'T9101','alerted',now(),now()), "
            "(gen_random_uuid(),:e,:c,2,'T9102','no_telemetry',now(),now()), "
            "(gen_random_uuid(),:e,:c,3,'T9104','not_tested',now(),now()), "
            "(gen_random_uuid(),:o,:c,1,'T9103','alerted',now(),now())"), {"e": ex, "o": old_ex, "c": cid})

        d = await compute_cockpit(s, client_id=cid)
        tc = {t["tactic"]: t for t in d["tactic_coverage"]}
        assert tc["initial-access"]["state"] == "detected"
        assert tc["impact"]["state"] == "gap"
        # Étape non testée : sa tactique n'apparaît pas dans la couverture.
        assert "execution" not in tc
        # Technique testée seulement dans un run ancien du même audit : hors pool.
        assert "discovery" not in tc
        # Ordre kill-chain : initial-access avant impact.
        order = [t["tactic"] for t in d["tactic_coverage"]]
        assert order.index("initial-access") < order.index("impact")
        # Tendance : au moins un point, caught/tested cohérents (1 détecté / 2 testés).
        assert d["trend"], "tendance vide"
        last = d["trend"][-1]
        assert last["tested"] == 2 and last["caught"] == 1 and last["pct"] == 50
        # Angles morts par tactique : l'étape impact sans télémétrie, ordre kill-chain.
        assert d["blind_tactics"] == [{"tactic": "impact", "count": 1}]

        for t in ("attack_step", "purple_exercise", "audit"):
            await s.execute(text(f"DELETE FROM {t} WHERE client_id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM organisation WHERE id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM ref_attack_technique WHERE ext_id IN ('T9101','T9102','T9103','T9104')"))
        await s.commit()


@pytest.mark.asyncio
async def test_application_posture_aggregates_and_scopes():
    """Posture agrégée d'une application : KPI, top audits (avec auditeur + détection),
    vulnérabilités actives triées du plus récent au plus ancien, et vocabulaire de statut
    correct (une vuln corrigée n'est plus active). Une app inconnue renvoie du vide."""
    from sqlalchemy import text

    from app.api.routes.analytics import compute_application_posture
    from app.db.session import service_session

    async with service_session("admin_service") as s:
        cid = str(uuid.uuid4())
        await s.execute(text("INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at) "
                             "VALUES (:c,'Ap','APX','client','AMBER','actif',now(),now())"), {"c": cid})
        await s.execute(text(
            "INSERT INTO ref_attack_technique (id,ext_id,name,tactic,data) VALUES "
            "(gen_random_uuid(),'T9301','A','initial-access','{}') ON CONFLICT (ext_id) DO NOTHING"))
        app = str(uuid.uuid4())
        await s.execute(text("INSERT INTO application (id,client_id,nom,code,criticite,statut,tlp,created_at,updated_at) "
                             "VALUES (:ap,:c,'Portail','PORT','critique','actif','AMBER',now(),now())"),
                        {"ap": app, "c": cid})
        res = str(uuid.uuid4())
        await s.execute(text("INSERT INTO ressource (id,organisation_id,nom,role,created_at,updated_at) "
                             "VALUES (:r,:c,'Alice Red','Red',now(),now())"), {"r": res, "c": cid})
        aud = str(uuid.uuid4())
        await s.execute(text("INSERT INTO audit (id,client_id,nom,categorie,statut,tlp,applications,auditeurs,date_fin,created_at,updated_at) "
                             "VALUES (:a,:c,'Audit Portail','purple_team','termine','AMBER',"
                             "ARRAY[:ap]::uuid[],ARRAY[:r]::uuid[],current_date,now(),now())"),
                        {"a": aud, "c": cid, "ap": app, "r": res})
        ex = str(uuid.uuid4())
        await s.execute(text("INSERT INTO purple_exercise (id,audit_id,client_id,nom,date,run_number,statut,tlp,created_at,updated_at) "
                             "VALUES (:e,:a,:c,'Run 1',current_date,1,'clos','AMBER',now(),now())"),
                        {"e": ex, "a": aud, "c": cid})
        # 2 prévenu, 1 sans télémétrie, 1 non testé → détection 2/3 = 67 %, angle mort = 1.
        for i, v in enumerate(["prevented", "prevented", "no_telemetry", "not_tested"]):
            await s.execute(text("INSERT INTO attack_step (id,exercise_id,client_id,ordre,technique,verdict,created_at,updated_at) "
                                 "VALUES (gen_random_uuid(),:e,:c,:o,'T9301',:v,now(),now())"),
                            {"e": ex, "c": cid, "o": i + 1, "v": v})
        # Vulns : critique ouverte (active, récente), haute en cours (active, ancienne),
        # critique corrigée (fermée → exclue malgré l'orthographe « corrigee »).
        v_open, v_mid, v_closed = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        await s.execute(text("INSERT INTO vulnerability (id,client_id,titre,severite,statut,applications,tlp,created_at,updated_at) VALUES "
                             "(:v1,:c,'RCE upload','critique','ouverte',ARRAY[:ap]::uuid[],'RED',now(),now()), "
                             "(:v2,:c,'XSS stockée','haute','en_cours',ARRAY[:ap]::uuid[],'RED',now() - interval '2 days',now()), "
                             "(:v3,:c,'IDOR','critique','corrigee',ARRAY[:ap]::uuid[],'RED',now() - interval '1 day',now())"),
                        {"v1": v_open, "v2": v_mid, "v3": v_closed, "c": cid, "ap": app})

        d = await compute_application_posture(s, app)
        assert d["kpis"]["detection_rate"] == 67
        assert d["kpis"]["blind_spots"] == 1
        assert d["kpis"]["vuln_critical_active"] == 1  # la corrigée n'est plus active
        assert d["kpis"]["audits"] == 1
        assert d["kpis"]["exercises"] == 1
        assert "T9301" in d["techniques"]
        assert {t["tactic"]: t["state"] for t in d["tactic_coverage"]}["initial-access"] == "detected"
        # Tendance : ≤ 5 exercices, un point ici.
        assert 1 <= len(d["trend"]) <= 5
        assert d["trend"][-1]["pct"] == 67
        # Posture segmentée du dernier exercice Purple (l'unique exercice ici).
        ple = d["posture_last_exercise"]
        assert ple is not None
        assert ple["tested"] == 3 and ple["caught"] == 2
        assert ple["blind"] == 1 and ple["pct"] == 67
        assert ple["verdicts"].get("prevented") == 2
        assert ple["exercise"]["run_number"] == 1
        # Top audits : auditeur résolu, détection du dernier run.
        assert len(d["top_audits"]) == 1
        ta = d["top_audits"][0]
        assert ta["auditeurs"] == ["Alice Red"]
        assert ta["detection_rate"] == 67
        # Vulns actives : la corrigée exclue, tri du plus récent au plus ancien.
        titres = [v["titre"] for v in d["active_vulns"]]
        assert titres == ["RCE upload", "XSS stockée"]

        # Application inconnue → aucune donnée.
        empty = await compute_application_posture(s, str(uuid.uuid4()))
        assert empty["kpis"]["audits"] == 0
        assert empty["top_audits"] == [] and empty["active_vulns"] == []
        assert empty["posture_last_exercise"] is None

        await s.execute(text("DELETE FROM attack_step WHERE client_id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM purple_exercise WHERE client_id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM vulnerability WHERE client_id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM audit WHERE client_id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM ressource WHERE organisation_id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM application WHERE client_id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM ref_attack_technique WHERE ext_id='T9301'"))
        await s.execute(text("DELETE FROM organisation WHERE id=:c"), {"c": cid})
        await s.commit()


@pytest.mark.asyncio
async def test_cockpit_journal_preview_gated_and_actor_resolved():
    """Aperçu du journal du cockpit : réservé aux rôles ayant journal:L (sinon vide),
    et acteur résolu via app_user (comme /journal)."""
    from sqlalchemy import text

    from app.api.routes.analytics import compute_cockpit
    from app.db.session import service_session
    from app.journal.chain import append as jappend

    async with service_session("admin_service") as s:
        uid = str(uuid.uuid4())
        email = f"cockpit-actor-{uuid.uuid4().hex[:6]}@purple.local"
        await s.execute(text(
            "INSERT INTO app_user (id,email,display_name,role,client_scope,status,"
            "mfa_enrolled,created_at,updated_at) VALUES "
            "(:id,:e,'Cockpit Actor','admin','{}','active',false,now(),now())"),
            {"id": uid, "e": email})
        # Entrée avec actor_id seul (pas d'actor_label) → doit résoudre vers le nom.
        await jappend(s, event_type="scenarios.create", actor_id=uid, subject=uid)

        # Rôle sans droit journal → aperçu vide.
        d_denied = await compute_cockpit(s, can_read_journal=False)
        assert d_denied["journal"] == []

        # Rôle autorisé → aperçu présent, acteur résolu.
        d_ok = await compute_cockpit(s, can_read_journal=True)
        mine = [j for j in d_ok["journal"] if j.get("actor") == "Cockpit Actor"]
        assert mine, d_ok["journal"]

        await s.execute(text("DELETE FROM app_user WHERE id=:id"), {"id": uid})
        await s.commit()
