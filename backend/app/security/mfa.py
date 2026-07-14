"""MFA — TOTP natif pour les comptes locaux, step-up sur actions à haut risque.
Spec backend v2 §1.2 / §3.4. Quand l'IdP assure la MFA, elle est déléguée (claim `amr`).
"""
from __future__ import annotations

import hmac
import time

import pyotp

VALID_WINDOW = 1  # ±1 pas de 30 s (tolérance de dérive d'horloge)


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str, issuer: str = "Purple Cockpit") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    """Vérification simple (sans anti-rejeu). Conservée pour les cas non sensibles.
    Préférer `consume_totp` sur les chemins d'authentification (anti-rejeu)."""
    return pyotp.TOTP(secret).verify(code, valid_window=VALID_WINDOW)


def matched_step(secret: str, code: str, valid_window: int = VALID_WINDOW) -> int | None:
    """Renvoie l'index du pas de temps TOTP correspondant au code, ou None si aucun.

    Comparaison en temps constant sur toute la fenêtre (pas de court-circuit révélateur)."""
    if not secret or not code:
        return None
    totp = pyotp.TOTP(secret)
    interval = totp.interval
    now = int(time.time())
    result: int | None = None
    for offset in range(-valid_window, valid_window + 1):
        at = now + offset * interval
        # compare_digest sur chaque candidat ; on parcourt toute la fenêtre sans break
        # pour ne pas exposer par le timing quel pas a (ou non) matché.
        if hmac.compare_digest(str(totp.at(at)), str(code)):
            result = at // interval
    return result


def consume_totp(
    secret: str, code: str, last_step: int | None, valid_window: int = VALID_WINDOW
) -> int | None:
    """Vérifie un code TOTP avec anti-rejeu.

    Renvoie le pas de temps consommé (à persister dans `app_user.last_totp_step`) si le
    code est valide ET strictement postérieur au dernier pas déjà utilisé ; None sinon
    (code invalide OU rejeu d'un pas déjà consommé)."""
    step = matched_step(secret, code, valid_window)
    if step is None:
        return None
    if last_step is not None and step <= last_step:
        return None  # rejeu d'un code déjà accepté (ou antérieur)
    return step
