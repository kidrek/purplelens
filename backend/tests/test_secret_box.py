"""Durcissement P2 — chiffrement des secrets TOTP au repos (secret_box)."""
from __future__ import annotations

import pytest

from app.security import secret_box


def test_encrypt_decrypt_roundtrip():
    secret = "JBSWY3DPEHPK3PXP"  # secret TOTP base32 typique
    enc = secret_box.encrypt_secret(secret)
    assert enc.startswith("gcm1:")
    assert enc != secret
    assert secret_box.decrypt_secret(enc) == secret


def test_legacy_plaintext_is_passed_through():
    """Compat ascendante : un secret non préfixé (clair hérité) est renvoyé tel quel."""
    assert secret_box.decrypt_secret("PLAINLEGACYSECRET") == "PLAINLEGACYSECRET"
    assert secret_box.decrypt_secret(None) is None


def test_is_encrypted():
    assert secret_box.is_encrypted(secret_box.encrypt_secret("x"))
    assert not secret_box.is_encrypted("plain")
    assert not secret_box.is_encrypted(None)
    assert not secret_box.is_encrypted("")


def test_ciphertext_is_randomised_but_decrypts_equal():
    a = secret_box.encrypt_secret("same-secret")
    b = secret_box.encrypt_secret("same-secret")
    assert a != b  # nonce aléatoire → chiffrés distincts
    assert secret_box.decrypt_secret(a) == secret_box.decrypt_secret(b) == "same-secret"


def test_tampered_ciphertext_is_rejected():
    enc = secret_box.encrypt_secret("secret")
    tampered = enc[:-4] + ("AAAA" if not enc.endswith("AAAA") else "BBBB")
    with pytest.raises(Exception):
        secret_box.decrypt_secret(tampered)
