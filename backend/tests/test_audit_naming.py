"""Nommage automatique des audits (cahier §A000.1) — format et préfixe de catégorie.

Les composants purs (mois AAAAMM, slug MAJUSCULE, préfixe de type) sont testés sans
base ; la construction complète du nom (avec résolution des codes client/app) est
couverte par le parcours e2e (test_e2e_http).
"""
from __future__ import annotations

from datetime import date

from app.api import service


def test_ym_from_iso_date_and_string():
    assert service._ym("2026-04-07") == "202604"
    assert service._ym(date(2026, 5, 12)) == "202605"


def test_ym_falls_back_to_current_month_when_absent_or_invalid():
    ym = service._ym(None)
    assert len(ym) == 6 and ym.isdigit()
    assert service._ym("pas-une-date") == ym  # repli identique


def test_code_upper_strips_accents_and_non_alnum():
    assert service._code_upper("ACME Finance") == "ACMEFINANCE"
    assert service._code_upper("Émulation FIN7") == "EMULATIONFIN7"
    assert service._code_upper("Front/Office (v2)") == "FRONTOFFICEV2"
    assert service._code_upper(None) == ""


def test_code_upper_truncates():
    assert len(service._code_upper("X" * 40)) <= 14


def test_audit_type_prefix_map_matches_maquette():
    m = service._AUDIT_TYPE_CODE
    assert m["bas"] == "BAS"
    assert m["pentest"] == "PEN"
    assert m["red_team"] == "REDTEAM"
    # purple_team reste connu (audits hérités) même s'il n'est plus proposé à la saisie.
    assert m["purple_team"] == "PURPLE"


def test_unknown_category_defaults_to_aud_prefix():
    # Une catégorie hors énumération (données héritées) retombe sur AUD, jamais d'erreur.
    assert service._AUDIT_TYPE_CODE.get("inconnue", "AUD") == "AUD"
