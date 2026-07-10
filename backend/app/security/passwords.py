"""Mots de passe des comptes locaux de repli (Argon2id) — spec backend v2 §1.1.

Comptes DÉSACTIVÉS par défaut (settings.local_accounts_enabled). Servent aux
déploiements sans IdP et aux comptes de service.
"""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()  # paramètres par défaut robustes (Argon2id)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _ph.verify(stored_hash, password)
    except VerifyMismatchError:
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _ph.check_needs_rehash(stored_hash)
