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
