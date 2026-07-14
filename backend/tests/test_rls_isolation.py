"""Isolation RLS de bout en bout (DAT §6, famille bloquante).

Nécessite une base PostgreSQL migrée. Fournir l'URL app_api via TEST_DATABASE_URL
(rôle NON-superuser, NOBYPASSRLS), sinon le test est ignoré. En CI, la base du
compose est utilisée.

Format attendu (psycopg) :
    postgresql://app_api:api@localhost:5432/purple
"""
from __future__ import annotations

import os
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not _URL, reason="TEST_DATABASE_URL non défini")

_UID = "11111111-1111-1111-1111-111111111111"


def _conn():
    return psycopg.connect(_URL, autocommit=True)


def _set_ctx(cur, role: str, scope: str) -> None:
    cur.execute("SELECT set_config('app.role', %s, false)", (role,))
    cur.execute("SELECT set_config('app.user_id', %s, false)", (_UID,))
    cur.execute("SELECT set_config('app.client_scope', %s, false)", (scope,))


@pytest.fixture
def two_clients():
    """Crée deux clients + un audit chacun via une connexion à contexte 'admin'
    (scope vide), puis nettoie."""
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, "admin", "")
        for cid, code in ((a, "TA"), (b, "TB")):
            cur.execute(
                "INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at)"
                " VALUES (%s,%s,%s,'client','AMBER','actif',now(),now())",
                (cid, f"Org {code}", code),
            )
            cur.execute(
                "INSERT INTO audit (id,client_id,nom,categorie,statut,tlp,created_at,updated_at)"
                " VALUES (gen_random_uuid(),%s,%s,'Purple','planifie','AMBER',now(),now())",
                (cid, f"AUD-{code}"),
            )
    yield a, b
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, "admin", "")
        cur.execute("DELETE FROM audit WHERE client_id = ANY(%s)", ([a, b],))
        cur.execute("DELETE FROM organisation WHERE id = ANY(%s)", ([a, b],))


def test_no_context_sees_nothing():
    """Fail-closed : une connexion app_api SANS contexte ne voit aucune ligne."""
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit")
        assert cur.fetchone()[0] == 0


def test_scope_isolates_clients(two_clients):
    a, b = two_clients
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, "auditeur", "{%s}" % a)
        cur.execute("SELECT nom FROM audit ORDER BY nom")
        assert [r[0] for r in cur.fetchall()] == ["AUD-TA"]

        _set_ctx(cur, "auditeur", "{%s}" % b)
        cur.execute("SELECT nom FROM audit ORDER BY nom")
        assert [r[0] for r in cur.fetchall()] == ["AUD-TB"]


def test_empty_scope_with_role_sees_all(two_clients):
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, "admin", "")
        cur.execute("SELECT nom FROM audit WHERE nom LIKE 'AUD-T%' ORDER BY nom")
        assert [r[0] for r in cur.fetchall()] == ["AUD-TA", "AUD-TB"]


@pytest.mark.parametrize("role", ["auditeur", "ciso", "voc", "cert"])
def test_empty_scope_non_global_role_sees_nothing(two_clients, role):
    """Durcissement P1 (fail-closed) : un rôle cloisonné dont le scope est accidentellement
    VIDE ne voit AUCUNE ligne — l'absence de scope n'est jamais « tous les clients »."""
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, role, "")  # scope vide + rôle non global
        cur.execute("SELECT count(*) FROM audit WHERE nom LIKE 'AUD-T%'")
        assert cur.fetchone()[0] == 0


def test_empty_scope_manager_still_sees_all(two_clients):
    """Contre-épreuve : manager (rôle global, spec §2.1) conserve la vue multi-clients."""
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, "manager", "")
        cur.execute("SELECT nom FROM audit WHERE nom LIKE 'AUD-T%' ORDER BY nom")
        assert [r[0] for r in cur.fetchall()] == ["AUD-TA", "AUD-TB"]


def test_with_check_blocks_cross_client_insert(two_clients):
    """La clause WITH CHECK empêche d'écrire dans un client hors scope."""
    a, b = two_clients
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, "auditeur", "{%s}" % a)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute(
                "INSERT INTO audit (id,client_id,nom,categorie,statut,tlp,created_at,updated_at)"
                " VALUES (gen_random_uuid(),%s,'PIRATE','Purple','planifie','AMBER',now(),now())",
                (b,),
            )


def test_scoped_role_can_insert_new_organisation():
    """Une organisation neuve n'existe dans AUCUN scope par construction (0009) — seul
    un contexte de sécurité établi est exigé à l'INSERT, pas l'appartenance au scope."""
    new_id = str(uuid.uuid4())
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, "auditeur", "{%s}" % str(uuid.uuid4()))  # scope à un tout autre client
        cur.execute(
            "INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at)"
            " VALUES (%s,'Org Test','ORGTEST','client','AMBER','actif',now(),now())",
            (new_id,),
        )
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, "admin", "")
        cur.execute("DELETE FROM organisation WHERE id = %s", (new_id,))


def test_no_context_cannot_insert_organisation():
    """Fail-closed : sans contexte de sécurité établi, l'INSERT sur organisation est refusé."""
    with _conn() as c, c.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute(
                "INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at)"
                " VALUES (gen_random_uuid(),'Org Sans Contexte','NOCTX','client','AMBER','actif',now(),now())"
            )


@pytest.mark.parametrize("role", ["voc", "ciso", "cert", "manager"])
def test_non_creator_role_cannot_insert_organisation(role):
    """Défense en profondeur (0010) : un rôle authentifié mais NON créateur d'organisation
    (matrice : seuls admin/auditeur ont organisations:C) est refusé par la RLS à l'INSERT,
    même si la porte 3 (matrice) était contournée. La couche 2 n'est jamais plus large
    que la couche 1."""
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, role, "")  # contexte établi, scope global — mais rôle non créateur
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute(
                "INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at)"
                " VALUES (gen_random_uuid(),'Org Interdite','FORBID','client','AMBER','actif',now(),now())"
            )


def test_admin_can_insert_organisation():
    """Contre-épreuve : le rôle admin (créateur autorisé) peut bien insérer (0010)."""
    new_id = str(uuid.uuid4())
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, "admin", "")
        cur.execute(
            "INSERT INTO organisation (id,nom,code,role,tlp_defaut,statut,created_at,updated_at)"
            " VALUES (%s,'Org Admin','ORGADM','client','AMBER','actif',now(),now())",
            (new_id,),
        )
        cur.execute("DELETE FROM organisation WHERE id = %s", (new_id,))


def test_journal_is_append_only():
    """Le trigger d'immuabilité rejette UPDATE/DELETE sur le journal."""
    with _conn() as c, c.cursor() as cur:
        _set_ctx(cur, "admin", "")
        jid = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO journal (id,event_type,prev_hash,curr_hash,detail,created_at)"
            " VALUES (%s,'test',%s,%s,'{}',now())",
            (jid, "0" * 64, "a" * 64),
        )
        with pytest.raises(psycopg.errors.RaiseException):
            cur.execute("UPDATE journal SET event_type='hack' WHERE id=%s", (jid,))
        with pytest.raises(psycopg.errors.RaiseException):
            cur.execute("DELETE FROM journal WHERE id=%s", (jid,))
