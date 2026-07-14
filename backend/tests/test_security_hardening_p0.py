"""Tests anti-régression du sprint de durcissement P0.

Couvre trois correctifs de sécurité serveur-décidés :
  - Porte 2 (MFA) du moteur `can()` : un objet TLP RED/AMBER exige une session MFA.
  - `decode_access_token` : refus d'un JWT sans claims structurants (exp/iat/iss/sub).
  - `Settings` : refus au démarrage des secrets d'infrastructure faibles en production.
"""
from __future__ import annotations

import time

import jwt
import pytest

from app.config import Settings
from app.security.matrix import Action
from app.security.rbac import (
    _tlp_pap_compatible,
    can,
    requires_fresh_stepup_for_clear,
)
from app.security.tokens import decode_access_token, issue_access_token


# ── Porte 2 — MFA sur TLP sensible ──────────────────────────────────────────
def test_gate2_denies_sensitive_tlp_without_mfa(ctx_factory):
    """Accès en lecture à une preuve TLP:AMBER sans MFA → refusé à la porte 2."""
    ctx = ctx_factory("auditeur", mfa=False, client_scope=["c1"])
    record = {"client_id": "c1", "tlp": "AMBER"}
    decision = can(ctx, Action.L, "evidence", record)
    assert not decision.allowed
    assert decision.reason == "gate2_mfa_required"


@pytest.mark.parametrize("tlp", ["RED", "red", "AMBER", "TLP:AMBER+STRICT", "amber"])
def test_gate2_covers_red_and_amber_variants(ctx_factory, tlp):
    ctx = ctx_factory("auditeur", mfa=False, client_scope=["c1"])
    decision = can(ctx, Action.L, "evidence", {"client_id": "c1", "tlp": tlp})
    assert decision.reason == "gate2_mfa_required"


def test_gate2_passes_sensitive_tlp_with_mfa(ctx_factory):
    """Avec MFA, l'accès à un TLP sensible franchit la porte 2 (auditeur : evidence L)."""
    ctx = ctx_factory("auditeur", mfa=True, client_scope=["c1"])
    decision = can(ctx, Action.L, "evidence", {"client_id": "c1", "tlp": "RED"})
    assert decision.allowed


@pytest.mark.parametrize("tlp", ["GREEN", "CLEAR", "WHITE", "", None])
def test_gate2_ignored_for_non_sensitive_tlp(ctx_factory, tlp):
    """TLP non sensible : la porte 2 n'exige pas de MFA (auditeur : evidence L)."""
    ctx = ctx_factory("auditeur", mfa=False, client_scope=["c1"])
    decision = can(ctx, Action.L, "evidence", {"client_id": "c1", "tlp": tlp})
    assert decision.allowed


def test_gate2_bypassed_for_service_roles(ctx_factory):
    """Les rôles de service (non interactifs, sans MFA) ne sont jamais bloqués à la porte 2."""
    ctx = ctx_factory("report_render", mfa=False)
    decision = can(ctx, Action.L, "evidence", {"client_id": "c1", "tlp": "RED"})
    assert decision.reason != "gate2_mfa_required"


# ── Porte 4 — scope vide fail-closed (durcissement P1) ──────────────────────
def test_gate4_empty_scope_non_global_denied(ctx_factory):
    """Un rôle cloisonné au scope VIDE est refusé (l'absence de scope n'ouvre rien)."""
    ctx = ctx_factory("auditeur", client_scope=[], mfa=True)
    decision = can(ctx, Action.L, "audits", {"client_id": "c1"})
    assert not decision.allowed
    assert decision.reason == "gate4_empty_scope"


@pytest.mark.parametrize("role", ["admin", "manager"])
def test_gate4_empty_scope_global_role_allowed(ctx_factory, role):
    """admin/manager (rôles globaux) conservent l'accès multi-clients au scope vide."""
    ctx = ctx_factory(role, client_scope=[], mfa=True)
    assert can(ctx, Action.L, "audits", {"client_id": "c1"}).allowed


def test_gate4_explicit_scope_out_of_range_denied(ctx_factory):
    ctx = ctx_factory("auditeur", client_scope=["c2"], mfa=True)
    decision = can(ctx, Action.L, "audits", {"client_id": "c1"})
    assert not decision.allowed
    assert decision.reason == "gate4_client_scope"


def test_gate4_explicit_scope_in_range_allowed(ctx_factory):
    ctx = ctx_factory("auditeur", client_scope=["c1"], mfa=True)
    assert can(ctx, Action.L, "audits", {"client_id": "c1"}).allowed


# ── Porte 5 / step-up sur diffusion sensible (durcissement P1) ──────────────
@pytest.mark.parametrize("tlp", ["RED", "red", "TLP:RED", "TLP:RED+STRICT"])
def test_stepup_required_for_red_clear(tlp):
    assert requires_fresh_stepup_for_clear({"tlp": tlp})


@pytest.mark.parametrize("tlp", ["AMBER", "GREEN", "CLEAR", "", None])
def test_stepup_not_required_below_red(tlp):
    assert not requires_fresh_stepup_for_clear({"tlp": tlp})
    assert not requires_fresh_stepup_for_clear(None)


def test_gate5_report_render_requires_masking_for_secrets():
    assert not _tlp_pap_compatible({"contains_secrets": True}, "report_render")
    assert _tlp_pap_compatible({"contains_secrets": True, "masked": True}, "report_render")


def test_gate5_blocks_external_share_of_sensitive_unmasked():
    assert not _tlp_pap_compatible({"tlp": "RED"}, "external_share")
    assert not _tlp_pap_compatible({"tlp": "AMBER"}, "external_share")
    assert _tlp_pap_compatible({"tlp": "RED", "masked": True}, "external_share")
    assert _tlp_pap_compatible({"tlp": "GREEN"}, "external_share")


def test_gate5_internal_view_is_permissive():
    assert _tlp_pap_compatible({"tlp": "RED"}, "view")


# ── decode_access_token — claims structurants exigés ────────────────────────
def _forge(**claims) -> str:
    from app.config import settings

    return jwt.encode(claims, settings.jwt_signing_key, algorithm="HS256")


def test_decode_accepts_wellformed_token():
    tok = issue_access_token(
        sub="u1", role="admin", client_scope=[], mfa=True, auth_time=int(time.time())
    )
    claims = decode_access_token(tok)
    assert claims["sub"] == "u1"
    assert claims["role"] == "admin"


def test_decode_rejects_token_without_exp():
    tok = _forge(sub="u1", iat=int(time.time()), iss="purple-cockpit", role="admin")
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(tok)


def test_decode_rejects_token_without_iat():
    now = int(time.time())
    tok = _forge(sub="u1", exp=now + 600, iss="purple-cockpit", role="admin")
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(tok)


def test_decode_rejects_expired_token():
    now = int(time.time())
    tok = _forge(sub="u1", iat=now - 1200, exp=now - 600, iss="purple-cockpit", role="admin")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(tok)


def test_decode_rejects_wrong_issuer():
    now = int(time.time())
    tok = _forge(sub="u1", iat=now, exp=now + 600, iss="attacker", role="admin")
    with pytest.raises(jwt.InvalidIssuerError):
        decode_access_token(tok)


# ── Settings — secrets d'infrastructure en production ───────────────────────
_STRONG_JWT = "z9Q3" + "a" * 40  # aucun marqueur faible (change/example/default/dev-)


def _settings(monkeypatch, **overrides) -> Settings:
    """Construit un Settings en production avec des secrets forts, surchargeables."""
    env = {
        "ENVIRONMENT": "production",
        "JWT_SIGNING_KEY": _STRONG_JWT,
        "MINIO_ROOT_USER": "purple-minio-svc",
        "MINIO_ROOT_PASSWORD": "S7rong-Minio-Passphrase!",
        "VAULT_TOKEN": "hvs.prodtokenvalue",
        "OIDC_CLIENT_SECRET": "prod-oidc-confidential-secret",
        "VAULT_ADDR": "https://vault:8200",
    }
    env.update(overrides)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_production_accepts_strong_secrets(monkeypatch):
    s = _settings(monkeypatch)
    assert s.is_production


@pytest.mark.parametrize(
    "override",
    [
        {"MINIO_ROOT_USER": "minioadmin"},
        {"MINIO_ROOT_PASSWORD": "minioadmin"},
        {"MINIO_ROOT_PASSWORD": "change-me-minio"},
        {"VAULT_TOKEN": ""},
        {"VAULT_TOKEN": "change-me-vault-token"},
        {"OIDC_CLIENT_SECRET": ""},
        {"VAULT_ADDR": "http://vault:8200"},
    ],
)
def test_production_rejects_weak_secret(monkeypatch, override):
    with pytest.raises(ValueError):
        _settings(monkeypatch, **override)


def test_development_allows_defaults(monkeypatch):
    """Hors production, les valeurs de confort MinIO/Vault ne bloquent pas le démarrage."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("JWT_SIGNING_KEY", _STRONG_JWT)
    # MinIO/Vault laissés à leurs défauts (minioadmin, http, token vide).
    s = Settings(_env_file=None)
    assert not s.is_production
