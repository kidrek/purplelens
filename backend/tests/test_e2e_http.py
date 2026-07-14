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

            # Exercice : référence auto PURPL_{AAAAMM}-{NN}_{CLIENT}_{APP} (APP via l'audit lié),
            # période issue de la date de l'exercice (2026-08 → 202608).
            ex = (await c.post("/api/exercices", json={
                "client_id": cid, "audit_id": aud["id"], "date": "2026-08-02",
                "statut": "en_cours", "tlp": "AMBER"})).json()
            assert ex["nom"].startswith("PURPL_202608-"), ex
            # Étape horodatée (datetime-local naïf → coercition UTC).
            st = await c.post("/api/attack_steps", json={
                "client_id": cid, "exercise_id": ex["id"], "ordre": 1, "technique": "T1566",
                "titre": "Phish", "verdict": "alerted", "horodatage": "2026-08-02T09:00",
                "horodatage_detection": "2026-08-02T09:05"})
            assert st.status_code in (200, 201), st.text
            step = st.json()

            # Scénario (catalogue CTI global) : nom descriptif conservé + référence auto SCEN_{AAAAMM}-{NN}.
            scen = (await c.post("/api/scenarios", json={
                "nom": "Émulation FIN7", "type_engagement": "purple-team", "tlp": "AMBER"})).json()
            assert scen["nom"] == "Émulation FIN7", scen
            assert scen.get("reference", "").startswith("SCEN_"), scen

            # Ticket de détection : rattachement à une étape OBLIGATOIRE ; référence auto
            # TICK_{AAAAMM}-{NN}_{CLIENT}_{APP}_{TECHNIQUE} (client/app de l'audit lié).
            tk = (await c.post("/api/tickets", json={
                "client_id": cid, "source_attack_step_id": step["id"],
                "technique_attack": "T1566", "priorite": "P2", "statut": "ouvert"})).json()
            assert tk.get("reference", "").startswith("TICK_"), tk
            assert tk["reference"].endswith("_T1566"), tk

            # Un ticket sans étape liée est refusé (422 ticket_requires_step).
            no_step = await c.post("/api/tickets", json={
                "client_id": cid, "technique_attack": "T1071", "priorite": "P3", "statut": "ouvert"})
            assert no_step.status_code == 422, no_step.text

            # Actions d'audit DÉRIVÉES du scénario lié : un scénario doté d'étapes, puis un
            # audit qui le référence → une action PTES par technique, phase mappée depuis la
            # tactique (reconnaissance→reconnaissance, execution→exploitation).
            scen_steps = (await c.post("/api/scenarios", json={
                "nom": "Chaîne dérivation", "tlp": "AMBER", "etapes": [
                    {"technique": "T1595", "tactique": "reconnaissance", "description": "Scan"},
                    {"technique": "T1059.001", "tactique": "execution", "commande": "powershell"},
                ]})).json()
            aud2 = (await c.post("/api/audits", json={
                "client_id": cid, "categorie": "pentest", "statut": "planifie",
                "date_debut": "2026-08-05", "scenario_id": scen_steps["id"], "tlp": "AMBER"})).json()
            acts = _items(await c.get(f"/api/audit_actions?audit_id={aud2['id']}"))
            by_tech = {a["technique_attack"]: a for a in acts}
            assert set(by_tech) == {"T1595", "T1059.001"}, acts
            assert by_tech["T1595"]["ptes_phase"] == "reconnaissance", acts
            assert by_tech["T1059.001"]["ptes_phase"] == "exploitation", acts

            # Exercice créé sur cet audit (scénario doté d'étapes) → chaîne d'étapes semée
            # automatiquement depuis le scénario (une étape 'not_tested' par technique).
            exo2 = (await c.post("/api/exercices", json={
                "client_id": cid, "audit_id": aud2["id"], "date": "2026-08-06",
                "statut": "planifie", "tlp": "AMBER"})).json()
            exo2_steps = _items(await c.get(f"/api/attack_steps?exercise_id={exo2['id']}"))
            assert {s["technique"] for s in exo2_steps} == {"T1595", "T1059.001"}, exo2_steps
            assert all(s["verdict"] == "not_tested" for s in exo2_steps), exo2_steps

            # Changement de scénario (partage T1059.001, ajoute T1071) → dédoublonnage :
            # seule la technique nouvelle est ajoutée (total = 3, pas 4).
            scen2 = (await c.post("/api/scenarios", json={
                "nom": "Chaîne dérivation 2", "tlp": "AMBER", "etapes": [
                    {"technique": "T1059.001", "tactique": "execution"},
                    {"technique": "T1071", "tactique": "command-and-control"},
                ]})).json()
            up2 = await c.put(f"/api/audits/{aud2['id']}", json={"scenario_id": scen2["id"]})
            assert up2.status_code in (200, 204), up2.text
            acts2 = _items(await c.get(f"/api/audit_actions?audit_id={aud2['id']}"))
            assert len(acts2) == 3, acts2
            assert "T1071" in {a["technique_attack"] for a in acts2}, acts2
            await c.delete(f"/api/audits/{aud2['id']}")

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
async def test_journal_read_is_client_filtered_for_scoped_role():
    """Durcissement P2 : le journal (chaîne globale) est filtré par périmètre — un rôle
    cloisonné ne voit QUE les entrées de son client, jamais celles d'un autre."""
    from sqlalchemy import text

    from app.db.session import service_session
    from app.journal.chain import append as jappend

    tag = uuid.uuid4().hex[:6]
    ca, cb = str(uuid.uuid4()), str(uuid.uuid4())
    async with service_session("admin_service") as s:
        for cid, code in ((ca, f"JA{tag[:4]}"), (cb, f"JB{tag[:4]}")):
            await s.execute(
                text(
                    "INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,"
                    "created_at,updated_at) VALUES (:c,:n,:code,'client','AMBER','actif',"
                    "now(),now())"
                ),
                {"c": cid, "n": f"Org {code}", "code": code},
            )
        await jappend(s, event_type="test.j.a", actor_id=None, client_id=ca, subject="A")
        await jappend(s, event_type="test.j.b", actor_id=None, client_id=cb, subject="B")

    email = f"recette-journ-{tag}@purple.local"
    await _mkuser(email, "auditeur", scope=[ca])
    try:
        async with _client() as c:
            await _login(c, email)
            items = (await c.get("/api/journal")).json()["items"]
            seen = {it["client_id"] for it in items if it.get("client_id")}
            assert ca in seen, "doit voir les entrées de son client"
            assert cb not in seen, "ne doit PAS voir les entrées d'un autre client (P2)"
    finally:
        await _rmuser(email)
        async with service_session("admin_service") as s:
            await s.execute(
                text("DELETE FROM organisation WHERE id = ANY(:ids)"), {"ids": [ca, cb]}
            )


@pytest.mark.asyncio
async def test_refresh_denied_for_deactivated_account():
    """Durcissement P2 : un compte désactivé ne peut plus prolonger sa session (/refresh)."""
    from sqlalchemy import text

    from app.db.session import auth_session

    email = f"recette-deact-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(email, "auditeur", scope=[str(uuid.uuid4())])
    try:
        async with _client() as c:
            assert (await _login(c, email)).status_code == 200  # cookie refresh posé
            async with auth_session() as s:
                await s.execute(
                    text("UPDATE app_user SET status='disabled' WHERE email = :e"),
                    {"e": email},
                )
                await s.commit()
            # Le refresh (cookie encore valide) doit désormais être refusé.
            resp = await c.post("/api/auth/refresh")
            assert resp.status_code == 401
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


@pytest.mark.asyncio
async def test_stix_import_creates_offensive_steps():
    """Import STIX : les techniques du bundle deviennent aussi des lignes scenario_step
    (sinon l'éditeur d'étapes offensives reste vide alors que la colonne JSON est remplie)."""
    email = f"recette-stix-imp-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(email, "admin")
    try:
        async with _client() as c:
            await _login(c, email)
            bundle = {
                "type": "bundle", "id": "bundle--import-steps",
                "objects": [
                    {"type": "attack-pattern", "id": "attack-pattern--1",
                     "external_references": [{"source_name": "mitre-attack", "external_id": "T1190"}]},
                    {"type": "attack-pattern", "id": "attack-pattern--2",
                     "external_references": [{"source_name": "mitre-attack", "external_id": "T1078"}]},
                ],
            }
            r = await c.post("/api/stix/import", json={"bundle": bundle})
            assert r.status_code == 200, r.text
            sid = r.json()["scenario_ids"][0]

            sc = (await c.get(f"/api/scenarios/{sid}")).json()
            steps = (await c.get(f"/api/scenario_steps?scenario_id={sid}")).json()
            rows = steps if isinstance(steps, list) else steps.get("items", [])
            rows.sort(key=lambda s: s.get("ordre") or 0)
            # Une étape par technique, dans l'ordre de la colonne JSON dérivée du bundle.
            assert [s["technique"] for s in rows] == sc["techniques"]
            assert [s["ordre"] for s in rows] == list(range(len(sc["techniques"])))

            await c.delete(f"/api/scenarios/{sid}")
    finally:
        await _rmuser(email)
