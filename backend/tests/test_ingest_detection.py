"""Sas d'ingestion — détection du type réel et de l'antivirus (cahier §6quater.2).

Le sas rejette : un fichier dont l'extension/annonce ment sur son type réel, et
tout contenu antivirus positif (au minimum EICAR quand ClamAV est indisponible).
On teste ici les fonctions pures ; l'intégration MinIO/ClamAV relève de la CI infra.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import app.workers.tasks as tasks
from app.workers.tasks import _clamav_scan, _detect_mime

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PDF = b"%PDF-1.7\n" + b"\x00" * 32
ZIP = b"PK\x03\x04" + b"\x00" * 32
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 20
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def test_detects_true_type_by_signature():
    assert _detect_mime(PNG) == "image/png"
    assert _detect_mime(JPEG) == "image/jpeg"
    assert _detect_mime(PDF) == "application/pdf"
    assert _detect_mime(ZIP) == "application/zip"
    assert _detect_mime(WEBP) == "image/webp"


def test_lying_extension_is_caught_by_content():
    """Un exécutable renommé en .png n'a pas la signature PNG → type réel None (rejet)."""
    fake_png = b"MZ\x90\x00" + b"\x00" * 40  # en-tête PE (exécutable Windows)
    assert _detect_mime(fake_png) != "image/png"
    assert _detect_mime(fake_png) is None


def test_empty_and_garbage_are_unknown():
    assert _detect_mime(b"") is None
    assert _detect_mime(b"not a real file header") is None


def test_eicar_is_rejected_even_without_clamav():
    clean, verdict = _clamav_scan(EICAR)
    assert clean is False
    assert "Eicar" in verdict


def test_benign_content_passes_scan_when_clamav_absent():
    clean, verdict = _clamav_scan(PDF)
    # Sans ClamAV en environnement de test, le contenu bénin n'est pas bloqué.
    assert clean is True


# ── Robustesse du sas : un échec des étapes crypto/WORM ne doit JAMAIS laisser la
#    preuve bloquée en 'quarantined' — elle doit finir sur un état terminal 'rejected'.
def _fake_session():
    """Session synchrone factice : tout SELECT renvoie une ligne non-None."""
    return MagicMock()


def _patch_common(monkeypatch, session):
    @contextmanager
    def fake_ssync(role, **kw):  # remplace service_session_sync
        yield session

    monkeypatch.setattr(tasks, "service_session_sync", fake_ssync)
    # L'objet en quarantaine est un PNG valide → passe MIME + antivirus (étapes 1–4).
    monkeypatch.setattr(tasks.minio_client, "read_object", lambda b, k: PNG)


def test_crypto_worm_failure_rejects_instead_of_staying_quarantined(monkeypatch):
    """Régression : une exception aux étapes 5–10 (ici Vault indisponible) bascule la
    preuve en 'rejected' motivé, au lieu de la laisser silencieusement en quarantaine."""
    session = _fake_session()
    _patch_common(monkeypatch, session)

    def vault_down(*a, **k):
        raise RuntimeError("vault sealed")

    monkeypatch.setattr(tasks.vault_client, "unwrap_dek", vault_down)

    captured = {}

    def fake_reject(sess, eid, reason, qkey, *, av=None):
        captured.update(eid=eid, reason=reason, qkey=qkey)

    monkeypatch.setattr(tasks, "_reject", fake_reject)

    result = tasks.ingest_evidence.apply(
        args=["ev-1", "incoming/cli/ev-1"]
    ).get()

    assert result["status"] == "rejected"
    assert captured["eid"] == "ev-1"
    assert captured["reason"].startswith("ingest_failed:")
    assert "RuntimeError" in captured["reason"]
    # La transaction fautive a bien été purgée avant de sceller le rejet.
    session.rollback.assert_called_once()


def test_nominal_ingest_reaches_stored(monkeypatch):
    """Chemin nominal : aucune erreur → statut 'stored', jamais de rejet."""
    session = _fake_session()
    _patch_common(monkeypatch, session)

    monkeypatch.setattr(tasks.vault_client, "unwrap_dek", lambda code, w: b"\x00" * 32)
    monkeypatch.setattr(tasks.crypto, "build_aad", lambda *a: b"aad")
    monkeypatch.setattr(tasks.crypto, "new_nonce", lambda: b"\x00" * 12)
    monkeypatch.setattr(tasks.crypto, "encrypt", lambda *a: (b"cipher", b"\x00" * 12))
    monkeypatch.setattr(tasks.minio_client, "put_locked_object", lambda *a: None)
    monkeypatch.setattr(tasks.minio_client, "purge_quarantine", lambda *a: None)
    monkeypatch.setattr(tasks, "_seal", lambda *a, **k: "journal-1")

    rejected = MagicMock()
    monkeypatch.setattr(tasks, "_reject", rejected)

    result = tasks.ingest_evidence.apply(
        args=["ev-2", "incoming/cli/ev-2"]
    ).get()

    assert result["status"] == "stored"
    rejected.assert_not_called()
