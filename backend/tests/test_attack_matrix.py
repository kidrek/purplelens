"""Matrice de couverture ATT&CK — agrégation sur base réelle (DAT §6, gated).

Tout se déroule dans UNE seule transaction à contexte RLS actif : les écritures non
committées sont visibles pour l'agrégation, et le contexte (app.role) n'est pas perdu
(SET LOCAL est transactionnel). Un commit intermédiaire viderait le contexte et, par
fail-closed, masquerait toutes les lignes.
"""
from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("asyncpg")

_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not _URL, reason="DATABASE_URL non défini")


@pytest.fixture(autouse=True)
async def _dispose_engine_between_tests():
    """Vide le pool du moteur avant/après chaque test (un event loop par test)."""
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
async def test_attack_matrix_aggregates_coverage():
    from sqlalchemy import text

    from app.api.routes.analytics import compute_attack_matrix
    from app.db.session import service_session

    tag = uuid.uuid4().hex[:3]
    t_used = f"T9{tag}"   # référencée ET exercée
    t_ref = f"T8{tag}"    # référencée, jamais touchée

    async with service_session("admin_service") as s:
        await s.execute(text(
            "INSERT INTO ref_attack_technique (id, ext_id, name, tactic, data) VALUES "
            "(gen_random_uuid(), :u, 'Used', 'execution', '{}'), "
            "(gen_random_uuid(), :r, 'RefOnly', 'impact', '{}') ON CONFLICT (ext_id) DO NOTHING"
        ), {"u": t_used, "r": t_ref})
        cid = str(uuid.uuid4())
        await s.execute(text(
            "INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at) "
            "VALUES (:c,'Mx','MX','client','AMBER','actif',now(),now())"), {"c": cid})
        aud = str(uuid.uuid4())
        await s.execute(text(
            "INSERT INTO audit (id,client_id,nom,categorie,statut,tlp,created_at,updated_at) "
            "VALUES (:a,:c,'A','Purple','en_cours','AMBER',now(),now())"), {"a": aud, "c": cid})
        exid = str(uuid.uuid4())
        await s.execute(text(
            "INSERT INTO purple_exercise (id,audit_id,client_id,nom,statut,tlp,created_at,updated_at) "
            "VALUES (:e,:a,:c,'E','en_cours','AMBER',now(),now())"), {"e": exid, "a": aud, "c": cid})
        await s.execute(text(
            "INSERT INTO attack_step (id,exercise_id,client_id,ordre,technique,verdict,created_at,updated_at) "
            "VALUES (gen_random_uuid(),:e,:c,1,:t,'alerted',now(),now())"),
            {"e": exid, "c": cid, "t": t_used})

        # Agrégation DANS la même transaction (contexte actif, écritures visibles).
        matrix = await compute_attack_matrix(s)

        flat = {t["ext_id"]: t for col in matrix["tactics"] for t in col["techniques"]}
        assert flat[t_used]["steps"] == 1
        assert flat[t_used]["best_verdict"] == "alerted"
        assert flat[t_used]["used"] is True
        assert flat[t_ref]["used"] is False
        assert matrix["summary"]["reference_total"] >= 2

        # Nettoyage explicite, dans l'ordre des dépendances (FK).
        await s.execute(text("DELETE FROM attack_step WHERE technique=:t"), {"t": t_used})
        await s.execute(text("DELETE FROM purple_exercise WHERE id=:e"), {"e": exid})
        await s.execute(text("DELETE FROM audit WHERE id=:a"), {"a": aud})
        await s.execute(text("DELETE FROM organisation WHERE id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM ref_attack_technique WHERE ext_id IN (:u,:r)"),
                        {"u": t_used, "r": t_ref})


@pytest.mark.asyncio
async def test_multi_tactic_technique_spans_columns():
    """Une technique multi-tactiques apparaît dans CHAQUE colonne (alignement Navigator).

    Les KPIs restent comptés une seule fois malgré la présence dans plusieurs colonnes.
    """
    from sqlalchemy import text

    from app.api.routes.analytics import compute_attack_matrix
    from app.db.session import service_session

    tag = uuid.uuid4().hex[:3]
    t_multi = f"T6{tag}"

    async with service_session("admin_service") as s:
        await s.execute(text(
            "INSERT INTO ref_attack_technique (id, ext_id, name, tactic, data) VALUES "
            "(gen_random_uuid(), :m, 'Multi', 'persistence', CAST(:d AS jsonb)) "
            "ON CONFLICT (ext_id) DO NOTHING"
        ), {"m": t_multi,
            "d": '{"tactics": ["persistence", "privilege-escalation", "defense-evasion"]}'})

        matrix = await compute_attack_matrix(s)
        cols_with = [col["tactic"] for col in matrix["tactics"]
                     if any(t["ext_id"] == t_multi for t in col["techniques"])]
        assert set(cols_with) == {"persistence", "privilege-escalation", "defense-evasion"}
        # Comptée une seule fois dans le total de référence (pas d'inflation multi-colonnes).
        occurrences = sum(1 for col in matrix["tactics"]
                          for t in col["techniques"] if t["ext_id"] == t_multi)
        assert occurrences == 3  # présence dans 3 colonnes, un seul objet logique

        await s.execute(text("DELETE FROM ref_attack_technique WHERE ext_id=:m"), {"m": t_multi})


@pytest.mark.asyncio
async def test_subtechnique_rolls_up_to_parent():
    """Une activité sur une sous-technique rend le parent « couvert » (cumul Navigator)."""
    from sqlalchemy import text

    from app.api.routes.analytics import compute_attack_matrix
    from app.db.session import service_session

    tag = uuid.uuid4().hex[:3]
    parent = f"T7{tag}"
    sub = f"{parent}.001"

    async with service_session("admin_service") as s:
        await s.execute(text(
            "INSERT INTO ref_attack_technique (id, ext_id, name, tactic, data) VALUES "
            "(gen_random_uuid(), :p, 'Parent', 'execution', '{}'), "
            "(gen_random_uuid(), :sb, 'Sub', 'execution', '{}') ON CONFLICT (ext_id) DO NOTHING"
        ), {"p": parent, "sb": sub})
        cid = str(uuid.uuid4())
        await s.execute(text(
            "INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at) "
            "VALUES (:c,'Rx','RX','client','AMBER','actif',now(),now())"), {"c": cid})
        aud = str(uuid.uuid4())
        await s.execute(text(
            "INSERT INTO audit (id,client_id,nom,categorie,statut,tlp,created_at,updated_at) "
            "VALUES (:a,:c,'A','Purple','en_cours','AMBER',now(),now())"), {"a": aud, "c": cid})
        exid = str(uuid.uuid4())
        await s.execute(text(
            "INSERT INTO purple_exercise (id,audit_id,client_id,nom,statut,tlp,created_at,updated_at) "
            "VALUES (:e,:a,:c,'E','en_cours','AMBER',now(),now())"), {"e": exid, "a": aud, "c": cid})
        # Activité uniquement sur la SOUS-technique.
        await s.execute(text(
            "INSERT INTO attack_step (id,exercise_id,client_id,ordre,technique,verdict,created_at,updated_at) "
            "VALUES (gen_random_uuid(),:e,:c,1,:t,'prevented',now(),now())"),
            {"e": exid, "c": cid, "t": sub})

        matrix = await compute_attack_matrix(s)
        parents = {t["ext_id"]: t for col in matrix["tactics"] for t in col["techniques"]}
        # Le parent apparaît comme technique (pas la sous-technique au 1er niveau).
        assert parent in parents and sub not in parents
        p = parents[parent]
        # Cumul : parent couvert et détecté grâce à la sous-technique.
        assert p["used"] is True and p["detected"] is True
        assert p["sub_count"] == 1 and p["sub_used"] == 1
        assert p["subtechniques"][0]["ext_id"] == sub

        await s.execute(text("DELETE FROM attack_step WHERE exercise_id=:e"), {"e": exid})
        await s.execute(text("DELETE FROM purple_exercise WHERE id=:e"), {"e": exid})
        await s.execute(text("DELETE FROM audit WHERE id=:a"), {"a": aud})
        await s.execute(text("DELETE FROM organisation WHERE id=:c"), {"c": cid})
        await s.execute(text("DELETE FROM ref_attack_technique WHERE ext_id IN (:p,:sb)"),
                        {"p": parent, "sb": sub})
