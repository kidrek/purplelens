"""MFA — TOTP natif pour les comptes locaux, step-up sur actions à haut risque.
Spec backend v2 §1.2 / §3.4. Quand l'IdP assure la MFA, elle est déléguée (claim `amr`).
"""
from __future__ import annotations

import pyotp


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str, issuer: str = "Purple Cockpit") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)
