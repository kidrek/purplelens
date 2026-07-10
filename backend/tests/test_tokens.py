"""Jetons d'accès et fraîcheur step-up (spec v2 §3.4)."""
from __future__ import annotations

import time

from app.security.tokens import decode_access_token, issue_access_token
from tests.conftest import make_ctx


def test_access_token_roundtrip():
    tok = issue_access_token(
        sub="u1", role="auditeur", client_scope=["c1"], mfa=True,
        auth_time=int(time.time()), email="a@b.c", display_name="A",
    )
    claims = decode_access_token(tok)
    assert claims["sub"] == "u1"
    assert claims["role"] == "auditeur"
    assert claims["client_scope"] == ["c1"]
    assert claims["iss"] == "purple-cockpit"


def test_step_up_fresh_true_when_recent():
    ctx = make_ctx("admin", mfa=True, auth_time=int(time.time()))
    assert ctx.step_up_fresh(300)


def test_step_up_stale_when_old():
    ctx = make_ctx("admin", mfa=True, auth_time=int(time.time()) - 600)
    assert not ctx.step_up_fresh(300)


def test_step_up_requires_mfa():
    ctx = make_ctx("admin", mfa=False, auth_time=int(time.time()))
    assert not ctx.step_up_fresh(300)


def test_multi_client_flags():
    assert make_ctx("admin", client_scope=[]).is_multi_client
    assert make_ctx("manager", client_scope=["c1"]).is_multi_client
    assert not make_ctx("auditeur", client_scope=["c1"]).is_multi_client
