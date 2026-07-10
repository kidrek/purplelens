"""Repli du code court (cahier A000.2) — régression du 500 NotNullViolation.

Une application (ou une organisation) créée sans `code` reçoit un slug dérivé
du premier mot du nom, jamais un NULL (la colonne est NOT NULL car le code
sert de segment d'arborescence S3).
"""
from __future__ import annotations

from app.api import service
from app.api.registry import spec_for


def test_slug_first_word_lowercase_ascii():
    assert service._slug_code("Portail Client") == "portail"
    assert service._slug_code("Échange B2B") == "echange"  # accents translittérés
    assert service._slug_code("  API   Gateway ") == "api"


def test_slug_strips_unsafe_chars_for_s3_prefix():
    assert service._slug_code("Front/Office (v2)") == "frontoffice"
    assert service._slug_code("***") == "na"  # jamais vide
    assert service._slug_code(None) == "na"
    assert service._slug_code("") == "na"


def test_slug_truncated_to_column_size():
    assert len(service._slug_code("x" * 100)) <= 32


def test_fallback_applied_when_code_missing_or_empty():
    spec = spec_for("applications")
    for payload in ({"nom": "portail"}, {"nom": "portail", "code": None},
                    {"nom": "portail", "code": ""}):
        data = dict(payload)
        service._apply_code_fallback(spec, data)
        assert data["code"] == "portail"


def test_fallback_preserves_user_provided_code():
    spec = spec_for("applications")
    data = {"nom": "portail", "code": "PRT"}
    service._apply_code_fallback(spec, data)
    assert data["code"] == "PRT"


def test_fallback_on_update_uses_current_nom():
    """Un code vidé à l'édition est re-dérivé du nom courant de l'objet."""
    spec = spec_for("applications")
    data = {"code": ""}
    service._apply_code_fallback(spec, data, current_nom="Portail Client")
    assert data["code"] == "portail"


def test_fallback_declared_only_where_spec_requires_it():
    """A000.2 ne concerne que l'Organisation et l'Application."""
    assert spec_for("organisations").code_fallback is True
    assert spec_for("applications").code_fallback is True
    assert spec_for("audits").code_fallback is False
    # Entité sans champ code : le repli ne s'applique pas, et ne doit rien injecter.
    spec = spec_for("tickets")
    data = {"description": "x"}
    service._apply_code_fallback(spec, data)
    assert "code" not in data
