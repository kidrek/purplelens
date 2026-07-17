"""Dérivation du bloc engagement (lettre d'engagement / NDA) — fonction pure.

Miroir serveur de `engagementDefaults` du drawer d'audit : on vérifie que les 18
clés attendues sont produites, que le contenu varie selon la catégorie
(pentest / red_team / bas) et que périmètre, acteur émulé et références client
sont bien intégrés.
"""
from __future__ import annotations

from app.api.engagement_defaults import build_engagement_defaults

# Les 18 clés du bloc engagement (cf. ENTITY_FIELDS.engagement côté front).
_EXPECTED_KEYS = {
    "objectifs", "perimetre_inclus", "perimetre_exclus", "regles_engagement",
    "fenetres_test", "contacts_autorisation", "contacts_urgence", "sow", "ref_nda",
    "niveau_intensite", "livrables_attendus", "clauses_legales", "nda_objet",
    "nda_duree", "nda_traitement", "nda_restitution", "nda_droit",
}


def test_produces_all_expected_keys():
    out = build_engagement_defaults({}, client_nom="Acme")
    assert _EXPECTED_KEYS.issubset(out.keys())
    # Chaque champ « lines » est une liste, les champs texte des chaînes non vides.
    assert isinstance(out["objectifs"], list) and out["objectifs"]
    assert isinstance(out["perimetre_exclus"], list) and out["perimetre_exclus"]
    assert isinstance(out["regles_engagement"], str) and out["regles_engagement"]


def test_perimetre_and_client_are_woven_in():
    out = build_engagement_defaults(
        {"categorie": "pentest", "client_id": "x"},
        client_nom="Éléphant Bleu",
        app_names=["Portail RH", "API Paie"],
    )
    assert out["perimetre_inclus"] == ["Portail RH", "API Paie"]
    # Le périmètre lisible apparaît dans les objectifs et l'objet NDA.
    assert "Portail RH, API Paie" in out["objectifs"][0]
    assert "Portail RH, API Paie" in out["nda_objet"]
    # Code client normalisé (diacritiques retirés) dans SOW / NDA.
    assert "ELEPHANTBLEU" in out["sow"]
    assert out["ref_nda"].startswith("NDA-ELEPHANTBLEU-")


def test_red_team_mentions_emulated_actor():
    out = build_engagement_defaults(
        {"categorie": "red_team"}, client_nom="Acme", acteur_emule="FIN7",
    )
    assert any("FIN7" in o for o in out["objectifs"])
    assert any("Red Team" in liv for liv in out["livrables_attendus"])


def test_category_changes_objectives_and_deliverables():
    pentest = build_engagement_defaults({"categorie": "pentest"}, client_nom="Acme")
    bas = build_engagement_defaults({"categorie": "bas"}, client_nom="Acme")
    assert pentest["objectifs"] != bas["objectifs"]
    assert pentest["livrables_attendus"] != bas["livrables_attendus"]
    # Catégorie inconnue → repli pentest.
    fallback = build_engagement_defaults({"categorie": "wat"}, client_nom="Acme")
    assert fallback["objectifs"] == pentest["objectifs"]


def test_test_window_derived_from_dates():
    with_dates = build_engagement_defaults(
        {"date_debut": "2026-09-01", "date_fin": "2026-09-15"}, client_nom="Acme",
    )
    assert with_dates["fenetres_test"][0] == "2026-09-01 → 2026-09-15"
    assert with_dates["sow"].startswith("SOW-2026-")
    without = build_engagement_defaults({}, client_nom="Acme")
    assert without["fenetres_test"] and "à convenir" in without["fenetres_test"][0]
