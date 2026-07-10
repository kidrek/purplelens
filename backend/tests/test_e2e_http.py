"""Recette bout-en-bout au niveau HTTP (DAT Phase 6).

Pilote l'application ASGE réelle via httpx (in-process, sans serveur réseau) et exerce
le cycle de requête complet : middleware de contexte, cookies de session, matrice can(),
RLS PostgreSQL. Ce test verrouille les classes de défauts d'INTÉGRATION que les tests à
session directe ne voient pas — précisément celles rencontrées en déploiement :
  - login par e-mail à domaine interne « .local » (ne doit PAS être un 422) ;
  - contrat du champ TOTP (`totp`, pas `otp`) ;
  - coercition des dates/horodatages ISO envoyés en chaîne ;
  - portée client (uuid[]) transmise correctement ;
  - cloisonnement RLS observé à travers l'API, pas seulement en base.

Gated sur DATABASE_URL (base migrée requise) ; joué en CI sur le service Postgres.
"""
from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("httpx")
pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL requis")

import httpx  # noqa: E402


def _client() -> httpx.AsyncClient:
    # base_url HTTPS : le cookie de session est Secure → httpx ne le renverrait pas en
    # http simple. In-process via ASGITransport (aucun port réseau ouvert).
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
    """Le moteur async est créé à l'import (pool partagé). pytest-asyncio ouvre un
    event loop par test : sans dispose, les connexions du pool restent liées au loop
    d'un test précédent (« attached to a different loop »). On vide le pool avant ET
    après chaque test e2e pour repartir d'un pool propre lié au loop courant."""
    from app.db.session import engine
    try:
        await engine.dispose()
    except Exception:  # noqa: BLE001 — connexions d'un loop mort : on les jette
        pass
    yield
    try:
        await engine.dispose()
    except Exception:  # noqa: BLE001
        pass


@pytest.mark.asyncio
async def test_login_contract_and_full_lifecycle():
    """Login (.local, TOTP=null) → CRUD complet avec auto-nommage, SLA et dates."""
    email = f"recette-admin-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(email, "admin")
    try:
        async with _client() as c:
            # Login : e-mail .local accepté (pas de 422), TOTP null accepté.
            r = await _login(c, email)
            assert r.status_code == 200, r.text
            who = await c.get("/api/auth/whoami")
            assert who.status_code == 200 and who.json()["role"] == "admin"

            # Mauvais mot de passe → 401 (et non 422) : la validation ne masque pas l'auth.
            bad = await c.post("/api/auth/login", json={"email": email, "password": "x", "totp": None})
            assert bad.status_code == 401

            org = (await c.post("/api/organisations", json={
                "nom": "Recette", "code": f"REC{uuid.uuid4().hex[:4]}", "role": "client",
                "tlp_defaut": "AMBER", "statut": "actif"})).json()
            cid = org["id"]

            # Audit : référence auto {TYPE}_{AAAAMM}-{NN}_{CLIENT}_{APP} (cahier §A000.1),
            # période issue de la date de début (2026-08 → 202608). Catégorie inconnue → AUD.
            aud = (await c.post("/api/audits", json={
                "client_id": cid, "categorie": "red_team", "statut": "planifie",
                "date_debut": "2026-08-01", "date_fin": "2026-08-15", "tlp": "AMBER"})).json()
            assert aud["nom"].startswith("REDTEAM_202608-"), aud
            assert aud["date_debut"] == "2026-08-01"

            # Vulnérabilité : référence auto VULN_{AAAAMM}-{NN}_... + SLA dérivé du CVSS.
            vul = (await c.post("/api/vulnerabilities", json={
                "client_id": cid, "severite": "haute", "cvss_score": 8.1,
                "description": "XSS", "techniques": ["T1059"], "tlp": "AMBER"})).json()
            assert vul.get("titre", "").startswith("VULN_") or vul.get("nom", "").startswith("VULN_")
            assert vul.get("sla_niveau"), vul

            # Actions d'audit + filtrage par audit_id.
            await c.post("/api/audit_actions", json={
                "client_id": cid, "audit_id": aud["id"], "ptes_phase": "exploitation",
                "titre": "SQLi", "statut": "ouvert"})
            f = _items(await c.get(f"/api/audit_actions?audit_id={aud['id']}"))
            assert len(f) == 1 and f[0]["titre"] == "SQLi"

            # Exercice + étape horodatée (datetime-local naïf → coercition UTC).
            ex = (await c.post("/api/exercices", json={
                "client_id": cid, "audit_id": aud["id"], "statut": "en_cours", "tlp": "AMBER"})).json()
            st = await c.post("/api/attack_steps", json={
                "client_id": cid, "exercise_id": ex["id"], "ordre": 1, "technique": "T1566",
                "titre": "Phish", "verdict": "alerted", "horodatage": "2026-08-02T09:00",
                "horodatage_detection": "2026-08-02T09:05"})
            assert st.status_code in (200, 201), st.text

            # Édition + suppression.
            up = await c.put(f"/api/audits/{aud['id']}", json={"statut": "en_cours"})
            assert up.status_code in (200, 204)
            await c.delete(f"/api/audits/{aud['id']}")
            await c.delete(f"/api/organisations/{cid}")
    finally:
        await _rmuser(email)


@pytest.mark.asyncio
async def test_rbac_denies_non_admin_user_management():
    """Un rôle non-admin ne peut ni lister ni créer des comptes (porte can())."""
    email = f"recette-aud-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(email, "auditeur")
    try:
        async with _client() as c:
            assert (await _login(c, email)).status_code == 200
            assert (await c.get("/api/admin/users")).status_code == 403
    finally:
        await _rmuser(email)


@pytest.mark.asyncio
async def test_rls_isolation_over_http():
    """Un auditeur cloisonné sur le client A ne voit pas les audits du client B."""
    admin = f"recette-adm-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(admin, "admin")
    aud_email = None
    try:
        async with _client() as c:
            await _login(c, admin)
            a = (await c.post("/api/organisations", json={"nom": "A", "code": f"A{uuid.uuid4().hex[:4]}", "role": "client", "tlp_defaut": "AMBER", "statut": "actif"})).json()
            b = (await c.post("/api/organisations", json={"nom": "B", "code": f"B{uuid.uuid4().hex[:4]}", "role": "client", "tlp_defaut": "AMBER", "statut": "actif"})).json()
            aa = (await c.post("/api/audits", json={"client_id": a["id"], "categorie": "P", "statut": "planifie", "tlp": "AMBER"})).json()
            ab = (await c.post("/api/audits", json={"client_id": b["id"], "categorie": "P", "statut": "planifie", "tlp": "AMBER"})).json()

        # Auditeur cloisonné sur A uniquement.
        aud_email = f"recette-scoped-{uuid.uuid4().hex[:6]}@purple.local"
        await _mkuser(aud_email, "auditeur", scope=[a["id"]])
        async with _client() as c2:
            await _login(c2, aud_email)
            seen = _items(await c2.get("/api/audits"))
            seen_ids = {x["id"] for x in seen}
            assert aa["id"] in seen_ids, "doit voir l'audit de son client A"
            assert ab["id"] not in seen_ids, "ne doit PAS voir l'audit du client B (RLS)"

        # Nettoyage (admin).
        async with _client() as c:
            await _login(c, admin)
            await c.delete(f"/api/audits/{aa['id']}")
            await c.delete(f"/api/audits/{ab['id']}")
            await c.delete(f"/api/organisations/{a['id']}")
            await c.delete(f"/api/organisations/{b['id']}")
    finally:
        await _rmuser(admin)
        if aud_email:
            await _rmuser(aud_email)


@pytest.mark.asyncio
async def test_stix_export_over_http():
    """Export STIX d'un scénario : bundle STIX 2.1 conforme (validé OASIS)."""
    stix2 = pytest.importorskip("stix2")
    email = f"recette-stix-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(email, "admin")
    try:
        async with _client() as c:
            await _login(c, email)
            sc = (await c.post("/api/scenarios", json={
                "nom": f"Rec-{uuid.uuid4().hex[:6]}", "acteur_emule": "APT-R",
                "type_engagement": "purple-team", "techniques": ["T1566"], "tlp": "AMBER"})).json()
            r = await c.get(f"/api/stix/scenarios/{sc['id']}")
            assert r.status_code == 200, r.text
            bundle = r.json()
            stix2.parse(bundle, allow_custom=False)  # conformité OASIS stricte
            assert bundle["type"] == "bundle"
            await c.delete(f"/api/scenarios/{sc['id']}")
    finally:
        await _rmuser(email)
