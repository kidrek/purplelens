"""Synchronisation des référentiels — parseurs ATT&CK/D3FEND (échantillons)."""
from __future__ import annotations

from app.reference.sync import parse_attack, parse_d3fend


def test_parse_attack_keeps_active_and_prefers_standard_tactic():
    bundle = {"objects": [
        {"type": "attack-pattern", "name": "Phishing",
         "external_references": [{"source_name": "mitre-attack", "external_id": "T1566"}],
         "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "initial-access"}]},
        {"type": "attack-pattern", "name": "EWM Injection",
         "external_references": [{"source_name": "mitre-attack", "external_id": "T1055.011"}],
         "kill_chain_phases": [
             {"kill_chain_name": "mitre-attack", "phase_name": "stealth"},
             {"kill_chain_name": "mitre-attack", "phase_name": "privilege-escalation"}]},
        {"type": "attack-pattern", "name": "Revoked", "revoked": True,
         "external_references": [{"source_name": "mitre-attack", "external_id": "T9999"}]},
        {"type": "attack-pattern", "name": "Deprecated", "x_mitre_deprecated": True,
         "external_references": [{"source_name": "mitre-attack", "external_id": "T8888"}]},
        {"type": "intrusion-set", "name": "APT-X"},  # ignoré
    ]}
    out = parse_attack(bundle)
    by = {t["ext_id"]: t for t in out}
    assert set(by) == {"T1566", "T1055.011"}  # révoqué/déprécié exclus
    assert by["T1566"]["tactic"] == "initial-access"
    # Tactique standard préférée à "stealth".
    assert by["T1055.011"]["tactic"] == "privilege-escalation"


def test_parse_d3fend_extracts_ids_and_names():
    doc = {"@graph": [
        {"@id": "d3f:DataInventory", "d3f:d3fend-id": "D3-DI",
         "d3f:definition": "…"},
        {"@id": "d3f:NetworkTrafficAnalysis", "d3f:d3fend-id": "D3-NTA",
         "rdfs:label": "Network Traffic Analysis"},
        {"@id": "d3f:SomeClass"},  # pas de d3fend-id → ignoré
    ]}
    out = parse_d3fend(doc)
    by = {t["ext_id"]: t["name"] for t in out}
    assert by["D3-NTA"] == "Network Traffic Analysis"  # label explicite
    assert by["D3-DI"] == "Data Inventory"  # dérivé du @id camelCase
    assert "D3-" not in "".join(k for k in by if not k.startswith("D3-"))
