"""Durcissement P1 — anti-rejeu TOTP et limitation de débit des routes d'auth."""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pyotp
import pytest
from fastapi import HTTPException

from app.security import ratelimit
from app.security.mfa import consume_totp, matched_step


# ── Anti-rejeu TOTP ─────────────────────────────────────────────────────────
def test_consume_totp_accepts_valid_code():
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    step = consume_totp(secret, code, None)
    assert step == int(time.time()) // 30


def test_consume_totp_rejects_replay():
    """Le même code (même pas de temps) ne peut être consommé deux fois."""
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    step = consume_totp(secret, code, None)
    assert step is not None
    # Deuxième présentation avec last_step = step (déjà consommé) → rejeu refusé.
    assert consume_totp(secret, code, step) is None


def test_consume_totp_rejects_older_step():
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    step = matched_step(secret, code)
    # Un pas déjà dépassé (futur last_step) rend le code obsolète.
    assert consume_totp(secret, code, step + 5) is None


def test_consume_totp_rejects_wrong_code():
    secret = pyotp.random_base32()
    assert consume_totp(secret, "000000", None) is None
    assert consume_totp(secret, "", None) is None


# ── Rate limiting ───────────────────────────────────────────────────────────
class _FakeRedis:
    def __init__(self):
        self.store: dict[str, int] = {}

    async def incr(self, key):
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def expire(self, key, window):
        return True


def _req(ip="1.2.3.4", xff=None):
    headers = {"x-forwarded-for": xff} if xff else {}
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=ip))


def test_rate_limit_allows_under_limit_then_blocks(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(ratelimit, "_client", lambda: fake)
    monkeypatch.setattr(ratelimit.settings, "rate_limit_enabled", True)
    dep = ratelimit.rate_limit("login", limit=2, window=60)

    async def run():
        await dep(_req())  # 1
        await dep(_req())  # 2
        with pytest.raises(HTTPException) as exc:
            await dep(_req())  # 3 → 429
        assert exc.value.status_code == 429

    asyncio.run(run())


def test_rate_limit_is_per_ip(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(ratelimit, "_client", lambda: fake)
    monkeypatch.setattr(ratelimit.settings, "rate_limit_enabled", True)
    dep = ratelimit.rate_limit("login", limit=1, window=60)

    async def run():
        await dep(_req(ip="10.0.0.1"))
        # Une autre IP dispose de son propre compteur.
        await dep(_req(ip="10.0.0.2"))
        with pytest.raises(HTTPException):
            await dep(_req(ip="10.0.0.1"))

    asyncio.run(run())


def test_rate_limit_degrades_gracefully_when_redis_down(monkeypatch):
    class _Broken:
        async def incr(self, key):
            raise RuntimeError("redis down")

        async def expire(self, key, window):
            raise RuntimeError("redis down")

    monkeypatch.setattr(ratelimit, "_client", lambda: _Broken())
    monkeypatch.setattr(ratelimit.settings, "rate_limit_enabled", True)
    dep = ratelimit.rate_limit("login", limit=1, window=60)

    async def run():
        # Redis KO : disponibilité préservée, aucune exception levée.
        for _ in range(5):
            await dep(_req())

    asyncio.run(run())


def test_client_ip_prefers_forwarded_header():
    assert ratelimit.client_ip(_req(ip="172.0.0.1", xff="203.0.113.7, 10.0.0.1")) == "203.0.113.7"
    assert ratelimit.client_ip(_req(ip="172.0.0.1")) == "172.0.0.1"
