"""Sas d'ingestion — détection du type réel et de l'antivirus (cahier §6quater.2).

Le sas rejette : un fichier dont l'extension/annonce ment sur son type réel, et
tout contenu antivirus positif (au minimum EICAR quand ClamAV est indisponible).
On teste ici les fonctions pures ; l'intégration MinIO/ClamAV relève de la CI infra.
"""
from __future__ import annotations

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
