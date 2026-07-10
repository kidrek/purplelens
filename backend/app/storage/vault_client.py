"""Vault transit engine — hiérarchie de clés (cahier §6quater.3 / spec v2 §5.3).

Une KEK par client dans le transit engine. Elle NE QUITTE JAMAIS le coffre : les
opérations wrap/unwrap sont déléguées à Vault. L'API n'obtient qu'une DEK en clair,
en mémoire, le temps de servir une preuve autorisée — jamais une KEK.

Politiques Vault au plus juste : encrypt/decrypt sur les clés client, jamais export.
"""
from __future__ import annotations

import base64
import os

import hvac

from app.config import settings


def _client() -> hvac.Client:
    return hvac.Client(url=settings.vault_addr, token=settings.vault_token)


def kek_name(client_code: str) -> str:
    return f"kek-client-{client_code}"


def ensure_client_kek(client_code: str) -> str:
    """Crée (idempotent) la KEK d'un client dans le transit engine. Renvoie sa référence."""
    c = _client()
    name = kek_name(client_code)
    c.secrets.transit.create_key(
        name=name, exportable=False, allow_plaintext_backup=False, mount_point=settings.vault_transit_mount
    )
    return f"{settings.vault_transit_mount}/{name}"


def generate_dek() -> bytes:
    """Génère une DEK aléatoire 256 bits (jamais dérivée déterministe — condition du
    crypto-shredding, cahier §6quater.3)."""
    return os.urandom(32)


def wrap_dek(client_code: str, dek: bytes) -> tuple[str, int]:
    """Enveloppe une DEK avec la KEK client. Renvoie (ciphertext_vault, kek_version)."""
    c = _client()
    resp = c.secrets.transit.encrypt_data(
        name=kek_name(client_code),
        plaintext=base64.b64encode(dek).decode(),
        mount_point=settings.vault_transit_mount,
    )
    ciphertext = resp["data"]["ciphertext"]  # forme "vault:vN:...."
    version = int(ciphertext.split(":")[1][1:]) if ":" in ciphertext else 1
    return ciphertext, version


def unwrap_dek(client_code: str, wrapped: str) -> bytes:
    """Déballe une DEK. Le résultat n'existe qu'en mémoire, jamais journalisé."""
    c = _client()
    resp = c.secrets.transit.decrypt_data(
        name=kek_name(client_code),
        ciphertext=wrapped,
        mount_point=settings.vault_transit_mount,
    )
    return base64.b64decode(resp["data"]["plaintext"])


def rotate_kek(client_code: str) -> None:
    """Rotation de la KEK client : ré-enveloppe les DEK, ne re-chiffre pas les objets
    (spec v2 §3.4). Les DEK existantes restent lisibles via rewrap."""
    c = _client()
    c.secrets.transit.rotate_key(name=kek_name(client_code), mount_point=settings.vault_transit_mount)


def rewrap_dek(client_code: str, wrapped: str) -> tuple[str, int]:
    """Ré-enveloppe une DEK avec la dernière version de la KEK, sans exposer le clair."""
    c = _client()
    resp = c.secrets.transit.rewrap_data(
        name=kek_name(client_code), ciphertext=wrapped, mount_point=settings.vault_transit_mount
    )
    ct = resp["data"]["ciphertext"]
    version = int(ct.split(":")[1][1:]) if ":" in ct else 1
    return ct, version
