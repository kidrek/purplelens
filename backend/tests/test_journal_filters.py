"""Journal : filtres serveur, KPI (/stats) et export JSON gardé (rôle global + step-up).

Pilote l'app ASGI réelle via httpx in-process (même approche que test_e2e_http) pour
verrouiller le contrat des nouveaux endpoints : filtrage décidé côté serveur, compteurs
KPI, et gating de l'export (backup manuel réservé aux rôles globaux + réauth récente).
Gated sur DATABASE_URL (base migrée requise).
"""
from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("httpx")
pytest.importorskip("pyotp")
pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL requis")

import httpx  # noqa: E402
import pyotp  # noqa: E402


def _client() -> httpx.AsyncClient:
    from app.main import app

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://testserver"
    )


async def _mkuser(
    email: str, role: str, scope: list[str] | None = None, totp_secret: str | None = None
) -> None:
    from sqlalchemy import text

    from app.db.session import auth_session
    from app.security.passwords import hash_password
    from app.security.secret_box import encrypt_secret

    enrolled = totp_secret is not None
    enc = encrypt_secret(totp_secret) if totp_secret else None
    async with auth_session() as s:
        await s.execute(text("DELETE FROM app_user WHERE email = :e"), {"e": email})
        await s.execute(
            text(
                "INSERT INTO app_user (id,email,role,client_scope,status,mfa_enrolled,"
                "totp_secret,password_hash,created_at,updated_at) VALUES "
                "(gen_random_uuid(),:e,:r,CAST(:sc AS uuid[]),'active',:m,:ts,:pw,now(),now())"
            ),
            {"e": email, "r": role, "sc": scope or [], "m": enrolled, "ts": enc,
             "pw": hash_password("Recette!1")},
        )
        await s.commit()


async def _rmuser(email: str) -> None:
    from sqlalchemy import text

    from app.db.session import auth_session

    async with auth_session() as s:
        await s.execute(text("DELETE FROM app_user WHERE email = :e"), {"e": email})
        await s.commit()


async def _login(c: httpx.AsyncClient, email: str, totp: str | None = None) -> httpx.Response:
    return await c.post("/api/auth/login", json={"email": email, "password": "Recette!1", "totp": totp})


async def _user_id(email: str) -> str | None:
    from sqlalchemy import text

    from app.db.session import auth_session

    async with auth_session() as s:
        r = (await s.execute(text("SELECT id FROM app_user WHERE email = :e"), {"e": email})).first()
        return str(r.id) if r else None


async def _seed(tag: str) -> None:
    """Sème trois entrées identifiables (subject=tag) dans la chaîne globale."""
    from app.db.session import service_session
    from app.journal.chain import append as jappend

    async with service_session("admin_service") as s:
        await jappend(s, event_type="auth.login.denied", actor_id=None,
                      actor_label="attaquant", subject=tag)
        await jappend(s, event_type="evidence.stored", actor_id=None,
                      actor_label="service:ingest", subject=tag)
        await jappend(s, event_type="deliverable.generated", actor_id=None,
                      actor_label="m.rodriguez", subject=tag)


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
async def test_journal_server_side_filters_and_stats():
    """Filtres domaine/résultat/recherche appliqués côté serveur + compteurs KPI."""
    tag = "jf-" + uuid.uuid4().hex[:8]
    await _seed(tag)
    email = f"recette-jf-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(email, "admin")
    try:
        async with _client() as c:
            await _login(c, email)

            # Recherche libre (q) + résultat=denied → seule l'entrée auth.login.denied du lot.
            denied = (await c.get(f"/api/journal?q={tag}&result=denied")).json()["items"]
            assert {e["event_type"] for e in denied} == {"auth.login.denied"}, denied

            # Domaine=evidence + recherche → seule evidence.stored.
            evd = (await c.get(f"/api/journal?q={tag}&domain=evidence")).json()["items"]
            assert {e["event_type"] for e in evd} == {"evidence.stored"}, evd

            # Domaine multiple (auth + deliverable) → les deux, jamais evidence.
            multi = (await c.get(f"/api/journal?q={tag}&domain=auth&domain=deliverable")).json()["items"]
            assert {e["event_type"] for e in multi} == {"auth.login.denied", "deliverable.generated"}, multi

            # Filtre acteur (multi-valeurs).
            act = (await c.get(f"/api/journal?q={tag}&actor=m.rodriguez")).json()["items"]
            assert {e["event_type"] for e in act} == {"deliverable.generated"}, act

            # KPI globaux : total et refus/échecs cohérents (>= le lot semé).
            stats = (await c.get("/api/journal/stats")).json()
            assert stats["total"] >= 3
            assert stats["denied"] >= 1
            assert stats["distinct_actors"] >= 1
    finally:
        await _rmuser(email)


@pytest.mark.asyncio
async def test_journal_actor_is_resolved_from_app_user():
    """La plupart des événements portent un actor_id (UUID) sans actor_label : la liste
    doit résoudre l'acteur via app_user (display_name → e-mail) et le filtre acteur doit
    s'aligner sur ce libellé résolu."""
    from app.db.session import service_session
    from app.journal.chain import append as jappend

    tag = "ja-" + uuid.uuid4().hex[:8]
    email = f"recette-jact-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(email, "admin")
    uid = await _user_id(email)
    async with service_session("admin_service") as s:
        # actor_id renseigné, actor_label absent → résolution attendue vers l'e-mail.
        await jappend(s, event_type="auth.login.ok", actor_id=uid, subject=tag)
    try:
        async with _client() as c:
            await _login(c, email)
            items = (await c.get(f"/api/journal?q={tag}")).json()["items"]
            assert items and items[0]["actor_label"] == email, items

            # Le filtre acteur cible le libellé résolu (ce que l'utilisateur sélectionne).
            f = (await c.get(f"/api/journal?q={tag}&actor={email}")).json()["items"]
            assert any(e["event_type"] == "auth.login.ok" for e in f), f
    finally:
        await _rmuser(email)


@pytest.mark.asyncio
async def test_journal_access_restricted_to_governance_roles():
    """Lecture du journal réservée à la gouvernance : operateur → 403 ; ciso → 200."""
    ope = f"recette-jrole-ope-{uuid.uuid4().hex[:6]}@purple.local"
    ciso = f"recette-jrole-ciso-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(ope, "operateur", scope=[str(uuid.uuid4())])
    await _mkuser(ciso, "ciso", scope=[str(uuid.uuid4())])
    try:
        async with _client() as c:
            await _login(c, ope)
            assert (await c.get("/api/journal")).status_code == 403
            assert (await c.get("/api/journal/stats")).status_code == 403
        async with _client() as c:
            await _login(c, ciso)
            assert (await c.get("/api/journal")).status_code == 200
            assert (await c.get("/api/journal/stats")).status_code == 200
    finally:
        await _rmuser(ope)
        await _rmuser(ciso)


@pytest.mark.asyncio
async def test_whoami_exposes_readable_entities():
    """/whoami projette la matrice : journal lisible pour admin, pas pour operateur —
    ce qui pilote le masquage du lien de menu côté client."""
    admin = f"recette-who-adm-{uuid.uuid4().hex[:6]}@purple.local"
    ope = f"recette-who-ope-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(admin, "admin")
    await _mkuser(ope, "operateur", scope=[str(uuid.uuid4())])
    try:
        async with _client() as c:
            await _login(c, admin)
            who = (await c.get("/api/auth/whoami")).json()
            assert "journal" in who["readable_entities"]
        async with _client() as c:
            await _login(c, ope)
            who = (await c.get("/api/auth/whoami")).json()
            assert "journal" not in who["readable_entities"]
            assert "scenarios" in who["readable_entities"]  # projection non vide
    finally:
        await _rmuser(admin)
        await _rmuser(ope)


@pytest.mark.asyncio
async def test_crud_event_populates_subject():
    """Les événements {entité}.create/.update/.delete portent l'id cible en subject
    (cohérence avec tous les autres événements ; colonne Sujet non vide en UI)."""
    email = f"recette-jsubj-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(email, "admin")
    try:
        async with _client() as c:
            await _login(c, email)
            sc = (await c.post("/api/scenarios", json={
                "nom": f"Subj-{uuid.uuid4().hex[:6]}", "tlp": "AMBER"})).json()
            sid = sc["id"]
            items = (await c.get(f"/api/journal?q={sid}")).json()["items"]
            create = [e for e in items if e["event_type"] == "scenarios.create"]
            assert create and create[0]["subject"] == sid, items
            await c.delete(f"/api/scenarios/{sid}")
    finally:
        await _rmuser(email)


@pytest.mark.asyncio
async def test_journal_export_gated_role_and_step_up():
    """Export : 403 pour un rôle cloisonné ; 401 step_up_required pour un admin sans réauth récente."""
    scoped = f"recette-jexp-scoped-{uuid.uuid4().hex[:6]}@purple.local"
    admin = f"recette-jexp-adm-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(scoped, "auditeur", scope=[str(uuid.uuid4())])
    await _mkuser(admin, "admin")  # sans MFA → step-up jamais frais
    try:
        async with _client() as c:
            await _login(c, scoped)
            r = await c.get("/api/journal/export?scope=full")
            assert r.status_code == 403, r.text  # rôle non global : refusé avant tout

        async with _client() as c:
            await _login(c, admin)
            r = await c.get("/api/journal/export?scope=full")
            assert r.status_code == 401, r.text
            assert "step_up" in r.text
    finally:
        await _rmuser(scoped)
        await _rmuser(admin)


@pytest.mark.asyncio
async def test_journal_export_success_is_self_logged_and_chain_stays_intact():
    """Admin MFA à réauth fraîche : export 200, dump ré-vérifiable (prev+curr hash),
    trace journal.export ajoutée, et chaîne toujours intacte après export."""
    secret = pyotp.random_base32()
    email = f"recette-jexp-ok-{uuid.uuid4().hex[:6]}@purple.local"
    await _mkuser(email, "admin", totp_secret=secret)
    try:
        async with _client() as c:
            code = pyotp.TOTP(secret).now()
            assert (await _login(c, email, totp=code)).status_code == 200

            # État de la chaîne AVANT export (la base de test partagée peut déjà porter
            # une rupture héritée d'autres tests : on vérifie que l'export n'en AJOUTE pas).
            before = (await c.get("/api/journal/verify")).json()

            r = await c.get("/api/journal/export?scope=full")
            assert r.status_code == 200, r.text
            dump = r.json()
            assert dump["scope"] == "full" and dump["count"] >= 1
            # Chaque entrée porte prev_hash ET curr_hash (re-vérification hors-ligne).
            assert all("prev_hash" in e and "curr_hash" in e for e in dump["entries"])
            assert "attachment" in r.headers.get("content-disposition", "")

            # L'export est lui-même scellé : une entrée journal.export apparaît.
            jr = (await c.get("/api/journal?domain=journal")).json()["items"]
            assert any(e["event_type"] == "journal.export" for e in jr), jr

            # La trace d'export ajoutée est un maillon valide : l'état de vérification
            # est inchangé (intacte reste intacte ; une rupture antérieure garde son rang).
            after = (await c.get("/api/journal/verify")).json()
            assert after == before, (before, after)
    finally:
        await _rmuser(email)
