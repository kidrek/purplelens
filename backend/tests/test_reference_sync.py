"""Synchronisation des référentiels — parseurs ATT&CK/D3FEND (échantillons)."""
from __future__ import annotations

from app.reference.sync import (
    parse_attack,
    parse_attack_groups,
    parse_d3fend,
    parse_misp_actors,
)


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
        # Technique multi-tactiques : doit conserver TOUTES ses tactiques standard.
        {"type": "attack-pattern", "name": "Valid Accounts",
         "external_references": [{"source_name": "mitre-attack", "external_id": "T1078"}],
         "kill_chain_phases": [
             {"kill_chain_name": "mitre-attack", "phase_name": "defense-evasion"},
             {"kill_chain_name": "mitre-attack", "phase_name": "persistence"},
             {"kill_chain_name": "mitre-attack", "phase_name": "privilege-escalation"},
             {"kill_chain_name": "mitre-attack", "phase_name": "initial-access"}]},
        {"type": "attack-pattern", "name": "Revoked", "revoked": True,
         "external_references": [{"source_name": "mitre-attack", "external_id": "T9999"}]},
        {"type": "attack-pattern", "name": "Deprecated", "x_mitre_deprecated": True,
         "external_references": [{"source_name": "mitre-attack", "external_id": "T8888"}]},
        {"type": "intrusion-set", "name": "APT-X"},  # ignoré
    ]}
    out = parse_attack(bundle)
    by = {t["ext_id"]: t for t in out}
    assert set(by) == {"T1566", "T1055.011", "T1078"}  # révoqué/déprécié exclus
    assert by["T1566"]["tactic"] == "initial-access"
    assert by["T1566"]["tactics"] == ["initial-access"]
    # Tactique standard préférée à "stealth" (écartée de `tactics`).
    assert by["T1055.011"]["tactic"] == "privilege-escalation"
    assert by["T1055.011"]["tactics"] == ["privilege-escalation"]
    # Multi-tactiques : toutes conservées, primaire = première rattachée.
    assert by["T1078"]["tactics"] == [
        "defense-evasion", "persistence", "privilege-escalation", "initial-access"]
    assert by["T1078"]["tactic"] == "defense-evasion"


def test_parse_attack_groups_maps_uses_relationships():
    bundle = {"objects": [
        {"type": "intrusion-set", "id": "intrusion-set--a", "name": "APT29",
         "aliases": ["APT29", "Cozy Bear", "The Dukes"],
         "external_references": [{"source_name": "mitre-attack", "external_id": "G0016"}]},
        {"type": "attack-pattern", "id": "attack-pattern--p1",
         "external_references": [{"source_name": "mitre-attack", "external_id": "T1566"}]},
        {"type": "attack-pattern", "id": "attack-pattern--p2",
         "external_references": [{"source_name": "mitre-attack", "external_id": "T1059"}]},
        # Groupe révoqué : ignoré.
        {"type": "intrusion-set", "id": "intrusion-set--dead", "name": "Ghost", "revoked": True,
         "external_references": [{"source_name": "mitre-attack", "external_id": "G9999"}]},
        # Relations : deux `uses` valides (dont une dupliquée) + une non-`uses` ignorée.
        {"type": "relationship", "relationship_type": "uses",
         "source_ref": "intrusion-set--a", "target_ref": "attack-pattern--p1"},
        {"type": "relationship", "relationship_type": "uses",
         "source_ref": "intrusion-set--a", "target_ref": "attack-pattern--p2"},
        {"type": "relationship", "relationship_type": "uses",
         "source_ref": "intrusion-set--a", "target_ref": "attack-pattern--p1"},  # doublon
        {"type": "relationship", "relationship_type": "attributed-to",
         "source_ref": "intrusion-set--a", "target_ref": "attack-pattern--p2"},  # pas `uses`
    ]}
    out = parse_attack_groups(bundle)
    by = {g["ext_id"]: g for g in out}
    assert set(by) == {"G0016"}  # groupe révoqué exclu
    g = by["G0016"]
    assert g["name"] == "APT29"
    # L'alias identique au nom est écarté ; l'ordre des relations est préservé, dédupliqué.
    assert g["data"]["aliases"] == ["Cozy Bear", "The Dukes"]
    assert g["data"]["techniques"] == ["T1566", "T1059"]


def test_parse_misp_actors_resolves_techniques_by_alias():
    groups = [{"ext_id": "G0016", "name": "APT29",
               "data": {"aliases": ["Cozy Bear"], "techniques": ["T1566", "T1059"]}}]
    doc = {"values": [
        # Correspondance via l'alias « Cozy Bear » → hérite des TTPs d'APT29.
        {"value": "The Dukes", "uuid": "uuid-dukes",
         "meta": {"synonyms": ["Cozy Bear", "APT29"]}},
        # Aucune correspondance MITRE → techniques vides, mais l'acteur est conservé.
        {"value": "Unknown Crew", "uuid": "uuid-unknown", "meta": {"synonyms": ["Nobody"]}},
        {"value": ""},  # sans nom → ignoré
    ]}
    out = parse_misp_actors(doc, groups)
    by = {a["name"]: a for a in out}
    assert set(by) == {"The Dukes", "Unknown Crew"}
    assert by["The Dukes"]["ext_id"] == "uuid-dukes"
    assert by["The Dukes"]["data"]["techniques"] == ["T1566", "T1059"]
    assert by["Unknown Crew"]["data"]["techniques"] == []


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
