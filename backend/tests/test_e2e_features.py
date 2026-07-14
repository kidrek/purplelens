"""Recette HTTP des fonctionnalités de parité (consolidation).

Complète `test_e2e_http.py` : pilote l'application ASGI réelle (in-process, cookies de
session, matrice can(), RLS) sur les endpoints ajoutés lors de la mise à parité :
  - éditeur d'étapes d'exercice (chargement depuis scénario, réordonnancement, gardes) ;
  - couverture par application (agrégat + filtre client) ;
  - cockpit enrichi (bande kill-chain, tendance, filtre client) ;
  - contexte d'usage d'un scénario (respect du cloisonnement RLS).

Gated sur DATABASE_URL (base migrée requise).
"""
from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("httpx")
pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL requis")

import httpx  # noqa: E402


def _client() -> httpx.AsyncClient:
    from app.main import app

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://testserver"
    )


async def _mkuser(email: str, role: str, scope: list[str] | None = None) -> None:
    from sqlalchemy import text

    from app.db.session import auth_session
    from app.security.passwords import hash_password

    async with auth_session() as s:
        await s.execute(text("DELETE FROM app_user WHERE email = :e"), {"e": email})
        await s.execute(
            text(
                "INSERT INTO app_user (id,email,role,client_scope,status,mfa_enrolled,"
                "password_hash,created_at,updated_at) VALUES "
                "(gen_random_uuid(),:e,:r,CAST(:sc AS uuid[]),'active',false,:pw,now(),now())"
            ),
            {"e": email, "r": role, "sc": scope or [], "pw": hash_password("Recette!1")},
        )
        await s.commit()


async def _rmuser(email: str) -> None:
    from sqlalchemy import text

    from app.db.session import auth_session

    async with auth_session() as s:
        await s.execute(text("DELETE FROM app_user WHERE email = :e"), {"e": email})
        await s.commit()


async def _login(c: httpx.AsyncClient, email: str) -> httpx.Response:
    return await c.post("/api/auth/login", json={"email": email, "password": "Recette!1", "totp": None})


def _items(r: httpx.Response) -> list:
    d = r.json()
    return d if isinstance(d, list) else d.get("items", [])


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
async def test_exercise_steps_editor_http():
    """Chargement depuis un scénario + réordonnancement, avec gardes RBAC et cohérence."""
    tag = uuid.uuid4().hex[:6]
    adm, ciso = f"feat-adm-{tag}@purple.local", f"feat-ciso-{tag}@purple.local"
    await _mkuser(adm, "admin")
    await _mkuser(ciso, "ciso")
    try:
        async with _client() as ca, _client() as cc:
            assert (await _login(ca, adm)).status_code == 200
            assert (await _login(cc, ciso)).status_code == 200

            cid = (await ca.post("/api/organisations", json={
                "nom": f"Feat{tag}", "code": f"F{tag[:5].upper()}", "role": "client",
                "tlp_defaut": "AMBER", "statut": "actif"})).json()["id"]
            aud = (await ca.post("/api/audits", json={
                "client_id": cid, "categorie": "Purple", "statut": "en_cours",
                "tlp": "AMBER"})).json()
            ex = (await ca.post("/api/exercices", json={
                "client_id": cid, "audit_id": aud["id"], "statut": "en_cours",
                "tlp": "AMBER"})).json()
            # Modèle §A00.1 : le scénario est une CHAÎNE D'ÉTAPES ; `techniques` en est
            # dérivé côté serveur (le champ plat `techniques` n'est plus writable).
            sc = (await ca.post("/api/scenarios", json={
                "nom": f"Sc{tag}",
                "etapes": [{"technique": "T1566"}, {"technique": "T1059"}],
                "tlp": "AMBER"})).json()

            # Chargement : 1 étape par technique, ordonnées, verdict not_tested.
            r = await ca.post(f"/api/exercices/{ex['id']}/load-scenario",
                              json={"scenario_id": sc["id"]})
            assert r.status_code == 200 and r.json()["created"] == 2
            steps = sorted(_items(await ca.get(f"/api/attack_steps?exercise_id={ex['id']}")),
                           key=lambda s: s["ordre"])
            assert [s["technique"] for s in steps] == ["T1566", "T1059"]
            assert all(s["verdict"] == "not_tested" for s in steps)

            # Réordonnancement : inversion complète.
            ids = [s["id"] for s in reversed(steps)]
            r = await ca.post(f"/api/exercices/{ex['id']}/reorder", json={"step_ids": ids})
            assert r.status_code == 200
            steps2 = sorted(_items(await ca.get(f"/api/attack_steps?exercise_id={ex['id']}")),
                            key=lambda s: s["ordre"])
            assert [s["technique"] for s in steps2] == ["T1059", "T1566"]

            # Gardes : CISO (lecture seule) → 403 ; jeu d'étapes incohérent → 400.
            assert (await cc.post(f"/api/exercices/{ex['id']}/load-scenario",
                                  json={"scenario_id": sc["id"]})).status_code == 403
            assert (await ca.post(f"/api/exercices/{ex['id']}/reorder",
                                  json={"step_ids": [ids[0]]})).status_code == 400

            await ca.delete(f"/api/scenarios/{sc['id']}")
            await ca.delete(f"/api/organisations/{cid}")
    finally:
        await _rmuser(adm)
        await _rmuser(ciso)


@pytest.mark.asyncio
async def test_applications_coverage_http_with_client_filter():
    """Agrégat de couverture par application (lien uuid[]) + filtre de périmètre client."""
    tag = uuid.uuid4().hex[:6]
    adm = f"feat-cov-{tag}@purple.local"
    await _mkuser(adm, "admin")
    try:
        async with _client() as ca:
            assert (await _login(ca, adm)).status_code == 200
            c1 = (await ca.post("/api/organisations", json={
                "nom": f"CovA{tag}", "code": f"CA{tag[:4].upper()}", "role": "client",
                "tlp_defaut": "AMBER", "statut": "actif"})).json()["id"]
            c2 = (await ca.post("/api/organisations", json={
                "nom": f"CovB{tag}", "code": f"CB{tag[:4].upper()}", "role": "client",
                "tlp_defaut": "AMBER", "statut": "actif"})).json()["id"]
            app1 = (await ca.post("/api/applications", json={
                "client_id": c1, "nom": f"App{tag}", "code": f"AP{tag[:4].upper()}",
                "criticite": "haute", "tlp": "AMBER"})).json()
            (await ca.post("/api/applications", json={
                "client_id": c2, "nom": f"Other{tag}", "code": f"OT{tag[:4].upper()}",
                "criticite": "basse", "tlp": "AMBER"})).json()
            # Vulnérabilité critique ouverte liée à app1 (tableau d'ids).
            rv = await ca.post("/api/vulnerabilities", json={
                "client_id": c1, "titre": f"V{tag}", "severite": "critique",
                "statut": "nouveau", "applications": [app1["id"]], "tlp": "AMBER"})
            assert rv.status_code in (200, 201), rv.text

            cov = (await ca.get("/api/analytics/applications-coverage")).json()["items"]
            mine = next(a for a in cov if a["id"] == app1["id"])
            assert mine["vuln_total"] == 1 and mine["vuln_high"] == 1 and mine["vuln_open"] == 1
            assert mine["audited"] is False

            # Filtre client : seules les applications du client 1.
            cov1 = (await ca.get(f"/api/analytics/applications-coverage?client_id={c1}")).json()["items"]
            assert {a["id"] for a in cov1} == {app1["id"]}

            await ca.delete(f"/api/organisations/{c1}")
            await ca.delete(f"/api/organisations/{c2}")
    finally:
        await _rmuser(adm)


@pytest.mark.asyncio
async def test_cockpit_widgets_and_client_filter_http():
    """Le cockpit expose la bande kill-chain et la tendance ; le filtre client agrège juste."""
    tag = uuid.uuid4().hex[:6]
    adm = f"feat-kpi-{tag}@purple.local"
    await _mkuser(adm, "admin")
    try:
        async with _client() as ca:
            assert (await _login(ca, adm)).status_code == 200
            cid = (await ca.post("/api/organisations", json={
                "nom": f"Kpi{tag}", "code": f"KP{tag[:4].upper()}", "role": "client",
                "tlp_defaut": "AMBER", "statut": "actif"})).json()["id"]
            (await ca.post("/api/vulnerabilities", json={
                "client_id": cid, "titre": f"VK{tag}", "severite": "haute",
                "statut": "nouveau", "tlp": "AMBER"})).json()

            d = (await ca.get(f"/api/analytics/cockpit?client_id={cid}")).json()
            # Structure : les clés des widgets récents sont présentes.
            assert "tactic_coverage" in d and "trend" in d
            # Filtre : ce client n'a qu'une vulnérabilité.
            assert d["vulnerabilities"]["total"] == 1

            await ca.delete(f"/api/organisations/{cid}")
    finally:
        await _rmuser(adm)


@pytest.mark.asyncio
async def test_scenario_usage_respects_rls():
    """Le contexte d'usage d'un scénario est cloisonné : un auditeur limité au client A
    ne voit pas l'audit du client B qui référence le même scénario global."""
    tag = uuid.uuid4().hex[:6]
    adm, scoped = f"feat-usg-adm-{tag}@purple.local", f"feat-usg-aud-{tag}@purple.local"
    await _mkuser(adm, "admin")
    try:
        async with _client() as ca:
            assert (await _login(ca, adm)).status_code == 200
            ca_id = (await ca.post("/api/organisations", json={
                "nom": f"UsgA{tag}", "code": f"UA{tag[:4].upper()}", "role": "client",
                "tlp_defaut": "AMBER", "statut": "actif"})).json()["id"]
            cb_id = (await ca.post("/api/organisations", json={
                "nom": f"UsgB{tag}", "code": f"UB{tag[:4].upper()}", "role": "client",
                "tlp_defaut": "AMBER", "statut": "actif"})).json()["id"]
            sc = (await ca.post("/api/scenarios", json={
                "nom": f"ScU{tag}", "techniques": ["T1566"], "d3fend": [],
                "tlp": "AMBER"})).json()
            for c in (ca_id, cb_id):
                assert (await ca.post("/api/audits", json={
                    "client_id": c, "categorie": "Purple", "statut": "en_cours",
                    "scenario_id": sc["id"], "tlp": "AMBER"})).status_code in (200, 201)

            # Admin (multi-clients) voit les deux usages.
            u_all = (await ca.get(f"/api/analytics/scenario-usage/{sc['id']}")).json()
            assert len(u_all["audits"]) == 2

            # Auditeur limité au client A : un seul usage visible (RLS).
            await _mkuser(scoped, "auditeur", scope=[ca_id])
            async with _client() as cs:
                assert (await _login(cs, scoped)).status_code == 200
                u_a = (await cs.get(f"/api/analytics/scenario-usage/{sc['id']}")).json()
                assert len(u_a["audits"]) == 1
                assert u_a["audits"][0]["client_id"] == ca_id

            await ca.delete(f"/api/scenarios/{sc['id']}")
            await ca.delete(f"/api/organisations/{ca_id}")
            await ca.delete(f"/api/organisations/{cb_id}")
    finally:
        await _rmuser(adm)
        await _rmuser(scoped)
