"""Coercition de types et liste blanche de filtrage (vue de détail Audit)."""
from __future__ import annotations

from datetime import UTC, date

from app.api import service
from app.api.registry import spec_for


def test_iso_string_coerced_to_date():
    """Un champ Date reçu en chaîne ISO devient un objet date (asyncpg l'exige)."""
    spec = spec_for("audit_milestones")
    out = service._coerce_types(spec, {"date_prevue": "2026-09-01", "livrable": "Rapport"})
    assert out["date_prevue"] == date(2026, 9, 1)
    assert out["livrable"] == "Rapport"  # les chaînes non-date restent intactes


def test_invalid_date_left_untouched():
    """Une date mal formée n'est pas convertie (le serveur renverra une 4xx, jamais un 500)."""
    spec = spec_for("audit_milestones")
    out = service._coerce_types(spec, {"date_prevue": "pas-une-date"})
    assert out["date_prevue"] == "pas-une-date"


def test_clean_payload_coerces_and_whitelists():
    spec = spec_for("audits")
    out = service._clean_payload(
        spec, {"date_debut": "2026-08-01", "categorie": "Purple", "champ_interdit": "x"}
    )
    assert out["date_debut"] == date(2026, 8, 1)
    assert "champ_interdit" not in out  # liste blanche writable


def test_naive_datetime_gets_utc():
    """Un datetime-local naïf (input navigateur) devient timezone-aware (UTC)."""
    spec = spec_for("attack_steps")
    out = service._coerce_types(spec, {"horodatage": "2026-07-05T14:30"})
    assert out["horodatage"].tzinfo is not None
    assert out["horodatage"].utcoffset() == UTC.utcoffset(None)


def test_filterable_whitelist_declared():
    """Les colonnes filtrables sont des clés étrangères sûres, jamais des colonnes libres."""
    assert "audit_id" in spec_for("audit_actions").filterable
    assert "audit_id" in spec_for("audit_milestones").filterable
    assert "exercise_id" in spec_for("attack_steps").filterable
    # Un champ de contenu libre ne doit pas être filtrable (pas de critère arbitraire).
    assert "titre" not in spec_for("audit_actions").filterable
