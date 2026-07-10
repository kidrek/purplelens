"""Chiffrement objet — AES-256-GCM (cahier §6quater.3).

- Nonce 96 bits (12 octets) UNIQUE par objet (et par vignette).
- AAD = id + audit_id + sha256_plaintext : lie cryptographiquement le binaire à SA
  ligne de métadonnées. Réassocier une preuve à un autre finding/audit ferait échouer
  le déchiffrement.

Invariant de sécurité (DAT §8) : la DEK en clair n'existe qu'en mémoire, le temps de
l'opération. Jamais journalisée, jamais sérialisée.
"""
from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12  # 96 bits


def build_aad(evidence_id: str, audit_id: str, sha256_plaintext: str) -> bytes:
    return f"{evidence_id}+{audit_id}+{sha256_plaintext}".encode()


def new_nonce() -> bytes:
    return os.urandom(NONCE_BYTES)


def encrypt(dek: bytes, plaintext: bytes, aad: bytes, nonce: bytes | None = None) -> tuple[bytes, bytes]:
    """Chiffre. Renvoie (ciphertext_avec_tag, nonce)."""
    if len(dek) != 32:
        raise ValueError("DEK must be 256 bits")
    nonce = nonce or new_nonce()
    ct = AESGCM(dek).encrypt(nonce, plaintext, aad)
    return ct, nonce


def decrypt(dek: bytes, ciphertext: bytes, aad: bytes, nonce: bytes) -> bytes:
    """Déchiffre. Lève une exception si l'AAD ou le tag ne correspondent pas."""
    return AESGCM(dek).decrypt(nonce, ciphertext, aad)
