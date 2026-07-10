"""Chiffrement enveloppe des preuves : intégrité et liaison AAD (cahier §6quater.4)."""
from __future__ import annotations

import os

import pytest

from app.storage import crypto


def test_roundtrip():
    dek = os.urandom(32)
    aad = crypto.build_aad("ev1", "aud1", "a" * 64)
    blob, nonce = crypto.encrypt(dek, b"preuve sensible", aad)
    assert crypto.decrypt(dek, blob, aad, nonce) == b"preuve sensible"


def test_wrong_aad_fails():
    """Changer un champ de l'AAD (ex : audit_id) casse le déchiffrement — liaison forte."""
    dek = os.urandom(32)
    aad = crypto.build_aad("ev1", "aud1", "a" * 64)
    blob, nonce = crypto.encrypt(dek, b"data", aad)
    tampered = crypto.build_aad("ev1", "aud_AUTRE", "a" * 64)
    with pytest.raises(Exception):
        crypto.decrypt(dek, blob, tampered, nonce)


def test_tampered_ciphertext_fails():
    dek = os.urandom(32)
    aad = crypto.build_aad("ev1", "aud1", "b" * 64)
    blob, nonce = crypto.encrypt(dek, b"data", aad)
    broken = bytearray(blob)
    broken[0] ^= 0xFF
    with pytest.raises(Exception):
        crypto.decrypt(dek, bytes(broken), aad, nonce)


def test_dek_must_be_256_bits():
    with pytest.raises(ValueError):
        crypto.encrypt(os.urandom(16), b"x", b"aad")
