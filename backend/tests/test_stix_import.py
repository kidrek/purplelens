"""Import STIX 2.1 — aller-retour export→import (fonctions pures)."""
from __future__ import annotations

from app.deliverables.stix import bundle_to_scenarios, scenarios_to_bundle


def test_roundtrip_recovers_scenario():
    sc = {
        "id": "sc-1", "nom": "Emotet emulation", "tlp": "AMBER",
        "acteur_emule": "TA542", "techniques": ["T1566", "T1059"],
        "d3fend": ["D3-NTA"], "objectif": "Tester phishing->exec", "ioc": "bad.example.com",
    }
    bundle = scenarios_to_bundle([sc], {"T1566": "Phishing", "T1059": "Command Interpreter"})
    back = bundle_to_scenarios(bundle)
    assert len(back) == 1
    s0 = back[0]
    assert s0["nom"] == "Emotet emulation"
    assert s0["tlp"] == "AMBER"
    assert s0["acteur_emule"] == "TA542"
    assert s0["techniques"] == ["T1566", "T1059"]
    assert s0["d3fend"] == ["D3-NTA"]
    assert "bad.example.com" in (s0.get("notes_import") or "")


def test_bundle_without_grouping_aggregates():
    # Un bundle STIX tiers sans grouping : on agrège les attack-pattern.
    bundle = {
        "type": "bundle", "id": "bundle--x",
        "objects": [
            {"type": "attack-pattern", "id": "attack-pattern--1",
             "external_references": [{"source_name": "mitre-attack", "external_id": "T1190"}]},
            {"type": "attack-pattern", "id": "attack-pattern--2",
             "external_references": [{"source_name": "mitre-attack", "external_id": "T1078"}]},
        ],
    }
    back = bundle_to_scenarios(bundle)
    assert len(back) == 1
    assert set(back[0]["techniques"]) == {"T1190", "T1078"}


def test_multiple_groupings_yield_multiple_scenarios():
    scA = {"id": "a", "nom": "A", "tlp": "GREEN", "techniques": ["T1566"], "d3fend": []}
    scB = {"id": "b", "nom": "B", "tlp": "RED", "techniques": ["T1059"], "d3fend": []}
    bundle = scenarios_to_bundle([scA, scB])
    back = bundle_to_scenarios(bundle)
    assert {s["nom"] for s in back} == {"A", "B"}
