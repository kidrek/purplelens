"""Fixtures partagées."""
from __future__ import annotations

import time

import pytest

from app.security.context import SecurityContext


def make_ctx(
    role: str,
    *,
    user_id: str = "11111111-1111-1111-1111-111111111111",
    client_scope: list[str] | None = None,
    mfa: bool = True,
    auth_time: int | None = None,
) -> SecurityContext:
    return SecurityContext(
        user_id=user_id,
        role=role,
        client_scope=client_scope or [],
        mfa=mfa,
        auth_time=auth_time if auth_time is not None else int(time.time()),
        email=f"{role}@purple.local",
        display_name=role.title(),
    )


@pytest.fixture
def ctx_factory():
    return make_ctx
