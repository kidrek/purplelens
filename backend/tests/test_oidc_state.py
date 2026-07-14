"""Durcissement P2 — état PKCE OIDC stocké dans Redis (usage unique + TTL)."""
from __future__ import annotations

import asyncio

from app.security import oidc_state


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def set(self, key, value, ex=None):
        self.store[key] = value

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        self.store.pop(key, None)


def test_store_then_pop_is_single_use(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(oidc_state, "_client", lambda: fake)

    async def run():
        await oidc_state.store_pkce("state-123", "verifier-abc")
        # première consommation → valeur
        assert await oidc_state.pop_pkce("state-123") == "verifier-abc"
        # deuxième consommation → None (anti-rejeu du state)
        assert await oidc_state.pop_pkce("state-123") is None

    asyncio.run(run())


def test_pop_unknown_state_returns_none(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(oidc_state, "_client", lambda: fake)

    async def run():
        assert await oidc_state.pop_pkce("never-stored") is None

    asyncio.run(run())
