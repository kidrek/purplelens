"""Provisioning WORM à la volée (cahier §6quater.6).

`put_locked_object` doit garantir l'immuabilité : si le bucket cible manque (le
provisioning nominal a échoué ou est en retard), il est créé AVEC Object Lock —
jamais sans, sous peine de rompre la garantie WORM. Un bucket déjà présent n'est
pas recréé (on ne peut de toute façon pas activer le lock après coup)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from app.storage import minio_client


def _lock_until():
    return datetime.now(UTC) + timedelta(days=3650)


def test_missing_bucket_is_created_with_object_lock(monkeypatch):
    mc = MagicMock()
    mc.bucket_exists.return_value = False
    monkeypatch.setattr(minio_client, "client", lambda: mc)

    minio_client.put_locked_object("purple-evidence-acme", "k", b"cipher", _lock_until())

    # Créé impérativement AVEC object_lock=True (WORM), jamais sans.
    mc.make_bucket.assert_called_once_with("purple-evidence-acme", object_lock=True)
    mc.put_object.assert_called_once()
    # Le put porte bien une rétention (Object Lock compliance).
    assert mc.put_object.call_args.kwargs.get("retention") is not None


def test_existing_bucket_is_not_recreated(monkeypatch):
    mc = MagicMock()
    mc.bucket_exists.return_value = True
    monkeypatch.setattr(minio_client, "client", lambda: mc)

    minio_client.put_locked_object("purple-evidence-acme", "k", b"cipher", _lock_until())

    mc.make_bucket.assert_not_called()
    mc.put_object.assert_called_once()
