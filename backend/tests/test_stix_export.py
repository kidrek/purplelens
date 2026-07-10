"""Export STIX 2.1 des scénarios — conformité OASIS + déterminisme."""
from __future__ import annotations

import pytest

from app.deliverables.stix import scenarios_to_bundle

_SC = {
    "id": "11111111-1111-1111-1111-111111111111",
    "nom": "APT-Démo", "objectif": "Accès initial par hameçonnage.",
    "acteur_emule": "FIN7", "type_engagement": "purple-team",
    "sophistication": "avancee", "ioc": "hash: abcd", "ioa": "PS encodé",
    "techniques": ["T1566", "T1059.001"], "d3fend": ["D3-NTA"], "tlp": "AMBER",
}
_NAMES = {"T1566": "Phishing", "T1059.001": "PowerShell"}


def test_bundle_is_valid_stix21():
    """Le bundle doit être parsable par la bibliothèque OASIS en mode strict."""
    stix2 = pytest.importorskip("stix2")
    bundle = scenarios_to_bundle([_SC], _NAMES)
    parsed = stix2.parse(bundle, allow_custom=False)  # lève si non conforme
    assert parsed.type == "bundle"
    types = {o["type"] for o in bundle["objects"]}
    assert {"grouping", "intrusion-set", "attack-pattern", "relationship"} <= types


def test_attack_pattern_has_mitre_reference():
    bundle = scenarios_to_bundle([_SC], _NAMES)
    aps = [o for o in bundle["objects"] if o["type"] == "attack-pattern"]
    ext = {a["external_references"][0]["external_id"] for a in aps}
    assert ext == {"T1566", "T1059.001"}
    sub = next(a for a in aps if a["external_references"][0]["external_id"] == "T1059.001")
    assert sub["external_references"][0]["url"].endswith("T1059/001")


def test_export_is_deterministic():
    """Réexporter le même scénario produit des identifiants identiques (UUIDv5)."""
    a = scenarios_to_bundle([_SC], _NAMES)
    b = scenarios_to_bundle([_SC], _NAMES)
    assert [o["id"] for o in a["objects"]] == [o["id"] for o in b["objects"]]


def test_tlp_marking_applied():
    bundle = scenarios_to_bundle([_SC], _NAMES)
    markings = [o for o in bundle["objects"] if o["type"] == "marking-definition"]
    assert markings and markings[0]["name"] == "TLP:AMBER"
    # Tout objet (hors la marking elle-même) porte le marquage.
    for o in bundle["objects"]:
        if o["type"] != "marking-definition":
            assert markings[0]["id"] in o.get("object_marking_refs", [])
