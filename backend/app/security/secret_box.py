"""Chiffrement symétrique des petits secrets applicatifs au repos (durcissement P2).

Utilisé pour le secret TOTP (`app_user.totp_secret`) : il ne doit pas dormir en clair en
base, sinon une fuite de dump SQL exposerait le second facteur de TOUS les comptes.

- Algorithme : AES-256-GCM (AAD de séparation de domaine).
- Clé : `TOTP_ENC_KEY` si fournie, sinon dérivée de `JWT_SIGNING_KEY` par hachage
  domaine-séparé (toujours disponible, pas de nouveau secret obligatoire).
- Format stocké : « gcm1:<nonce_b64>.<ct_b64> ». Une valeur SANS ce préfixe est traitée
  comme du clair hérité (compat ascendante : les secrets déjà enrôlés restent lisibles et
  sont ré-écrits chiffrés au prochain enrôlement/confirmation).
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

_PREFIX = "gcm1:"
_AAD = b"totp-secret"
_NONCE_BYTES = 12  # 96 bits (GCM)


def _key() -> bytes:
    raw = settings.totp_enc_key or settings.jwt_signing_key
    # Séparation de domaine : la clé de chiffrement des secrets n'est jamais la clé JWT brute.
    return hashlib.sha256(b"totp-enc:" + raw.encode("utf-8")).digest()  # 32 octets


def is_encrypted(stored: str | None) -> bool:
    return bool(stored) and stored.startswith(_PREFIX)


def encrypt_secret(plaintext: str) -> str:
    nonce = os.urandom(_NONCE_BYTES)
    ct = AESGCM(_key()).encrypt(nonce, plaintext.encode("utf-8"), _AAD)
    return f"{_PREFIX}{base64.b64encode(nonce).decode()}.{base64.b64encode(ct).decode()}"


def decrypt_secret(stored: str | None) -> str | None:
    """Déchiffre un secret. Renvoie tel quel un clair hérité (non préfixé) ou None."""
    if not is_encrypted(stored):
        return stored
    nonce_b64, ct_b64 = stored[len(_PREFIX):].split(".", 1)
    nonce = base64.b64decode(nonce_b64)
    ct = base64.b64decode(ct_b64)
    return AESGCM(_key()).decrypt(nonce, ct, _AAD).decode("utf-8")
