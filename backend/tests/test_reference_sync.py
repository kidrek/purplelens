"""Synchronisation des référentiels — parseurs ATT&CK/D3FEND/CAPEC/CWE (échantillons)."""
from __future__ import annotations

import io
import zipfile

from app.reference.sync import (
    _merge_technique,
    _unzip_first_xml,
    parse_attack,
    parse_attack_groups,
    parse_capec,
    parse_cwe,
    parse_d3fend,
    parse_misp_actors,
)


def test_parse_attack_keeps_active_and_prefers_standard_tactic():
    bundle = {"objects": [
        {"type": "attack-pattern", "name": "Phishing", "description": "Adversaries send phishing.",
         "external_references": [{"source_name": "mitre-attack", "external_id": "T1566"}],
         "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "initial-access"}]},
        {"type": "attack-pattern", "name": "EWM Injection",
         "external_references": [{"source_name": "mitre-attack", "external_id": "T1055.011"}],
         "kill_chain_phases": [
             {"kill_chain_name": "mitre-attack", "phase_name": "not-a-real-tactic"},
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
    # La description générique de l'attack-pattern est remontée (pré-remplissage d'étape).
    assert by["T1566"]["description"] == "Adversaries send phishing."
    assert by["T1078"]["description"] is None  # absente → None, pas d'erreur
    # Tactique reconnue préférée à une phase non-MITRE (écartée de `tactics`).
    assert by["T1055.011"]["tactic"] == "privilege-escalation"
    assert by["T1055.011"]["tactics"] == ["privilege-escalation"]
    # Multi-tactiques : toutes conservées, primaire = première rattachée.
    assert by["T1078"]["tactics"] == [
        "defense-evasion", "persistence", "privilege-escalation", "initial-access"]
    assert by["T1078"]["tactic"] == "defense-evasion"
    # Domaine par défaut = enterprise.
    assert by["T1566"]["domains"] == ["enterprise"]


def test_parse_attack_mobile_domain_and_tactics():
    bundle = {"objects": [
        {"type": "attack-pattern", "name": "Download New Code at Runtime",
         "external_references": [{"source_name": "mitre-mobile-attack", "external_id": "T1407"}],
         "kill_chain_phases": [{"kill_chain_name": "mitre-mobile-attack", "phase_name": "defense-evasion"}]},
        # Tactique propre au Mobile (stealth) : doit être reconnue et conservée.
        {"type": "attack-pattern", "name": "Download New Code at Runtime (stealthy)",
         "external_references": [{"source_name": "mitre-mobile-attack", "external_id": "T1544"}],
         "kill_chain_phases": [{"kill_chain_name": "mitre-mobile-attack", "phase_name": "stealth"}]},
    ]}
    out = parse_attack(bundle, "mobile")
    by = {t["ext_id"]: t for t in out}
    assert set(by) == {"T1407", "T1544"}
    assert by["T1544"]["tactic"] == "stealth"  # tactique Mobile reconnue
    assert by["T1544"]["tactics"] == ["stealth"]
    assert by["T1407"]["domains"] == ["mobile"]


def test_parse_attack_ics_domain_and_tactics():
    bundle = {"objects": [
        {"type": "attack-pattern", "name": "Block Command Message",
         "external_references": [{"source_name": "mitre-ics-attack", "external_id": "T0803"}],
         "kill_chain_phases": [{"kill_chain_name": "mitre-ics-attack", "phase_name": "inhibit-response-function"}]},
    ]}
    out = parse_attack(bundle, "ics")
    assert out[0]["ext_id"] == "T0803"  # plage T0xxx propre à l'ICS
    assert out[0]["tactic"] == "inhibit-response-function"
    assert out[0]["domains"] == ["ics"]


def test_parse_attack_unknown_tactic_falls_back_to_first_phase():
    bundle = {"objects": [
        {"type": "attack-pattern", "name": "Odd",
         "external_references": [{"source_name": "mitre-attack", "external_id": "T4242"}],
         "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "made-up-tactic"}]},
    ]}
    out = parse_attack(bundle)
    assert out[0]["tactic"] == "made-up-tactic"  # garde-fou : jamais écartée en silence


def test_merge_technique_unions_domains_and_tactics():
    merged = {t["ext_id"]: t for t in parse_attack({"objects": [
        {"type": "attack-pattern", "name": "Valid Accounts",
         "external_references": [{"source_name": "mitre-attack", "external_id": "T1078"}],
         "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "persistence"}]},
    ]}, "enterprise")}
    # Même technique côté Mobile, tactique différente + nom alternatif.
    for t in parse_attack({"objects": [
        {"type": "attack-pattern", "name": "Valid Accounts (mobile)",
         "external_references": [{"source_name": "mitre-mobile-attack", "external_id": "T1078"}],
         "kill_chain_phases": [{"kill_chain_name": "mitre-mobile-attack", "phase_name": "defense-evasion"}]},
    ]}, "mobile"):
        _merge_technique(merged, t)
    m = merged["T1078"]
    assert m["domains"] == ["enterprise", "mobile"]          # union des domaines
    assert m["tactics"] == ["persistence", "defense-evasion"]  # union des tactiques
    assert m["tactic"] == "persistence"                        # primaire = première (Enterprise)
    assert m["name"] == "Valid Accounts"                       # nom Enterprise conservé


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
        # La procédure (description) propre à l'acteur est portée par la relation `uses`.
        {"type": "relationship", "relationship_type": "uses",
         "source_ref": "intrusion-set--a", "target_ref": "attack-pattern--p1",
         "description": "APT29 spearphishes targets."},
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
    # Procédures : seule la relation porteuse d'une description est indexée (par ext_id).
    assert g["data"]["procedures"] == {"T1566": "APT29 spearphishes targets."}


def test_parse_misp_actors_resolves_techniques_by_alias():
    groups = [{"ext_id": "G0016", "name": "APT29",
               "data": {"aliases": ["Cozy Bear"], "techniques": ["T1566", "T1059"],
                        "procedures": {"T1566": "APT29 spearphishes targets."}}}]
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
    # Le contexte acteur (procédures) est hérité du groupe MITRE correspondant.
    assert by["The Dukes"]["data"]["procedures"] == {"T1566": "APT29 spearphishes targets."}
    assert by["Unknown Crew"]["data"]["techniques"] == []
    assert by["Unknown Crew"]["data"]["procedures"] == {}


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


# XML CAPEC minimal avec namespace par défaut (comme la source MITRE).
_CAPEC_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Attack_Pattern_Catalog xmlns="http://capec.mitre.org/capec-3">
  <Attack_Patterns>
    <Attack_Pattern ID="66" Name="SQL Injection" Abstraction="Standard" Status="Stable"/>
    <Attack_Pattern ID="63" Name="Cross-Site Scripting (XSS)" Status="Draft"/>
    <Attack_Pattern ID="999" Name="Vieux pattern" Status="Deprecated"/>
    <Attack_Pattern Name="Sans ID" Status="Stable"/>
  </Attack_Patterns>
</Attack_Pattern_Catalog>"""


def test_parse_capec_extracts_ids_skips_deprecated_and_namespaced():
    out = parse_capec(_CAPEC_XML)
    by = {p["ext_id"]: p["name"] for p in out}
    assert set(by) == {"CAPEC-66", "CAPEC-63"}  # déprécié + sans ID exclus
    assert by["CAPEC-66"] == "SQL Injection"
    assert by["CAPEC-63"] == "Cross-Site Scripting (XSS)"


# XML CWE minimal : Weakness retenues, Category/View ignorées, namespace par défaut.
_CWE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Weakness_Catalog xmlns="http://cwe.mitre.org/cwe-7">
  <Weaknesses>
    <Weakness ID="79" Name="Cross-site Scripting (XSS)" Abstraction="Base" Status="Stable"/>
    <Weakness ID="89" Name="SQL Injection" Status="Stable"/>
    <Weakness ID="1000" Name="Retired weakness" Status="Obsolete"/>
  </Weaknesses>
  <Categories>
    <Category ID="200" Name="Information Exposure"/>
  </Categories>
  <Views>
    <View ID="699" Name="Software Development"/>
  </Views>
</Weakness_Catalog>"""


def test_parse_cwe_extracts_weaknesses_only_and_skips_obsolete():
    out = parse_cwe(_CWE_XML)
    by = {w["ext_id"]: w["name"] for w in out}
    assert set(by) == {"CWE-79", "CWE-89"}  # Category/View + Obsolete exclus
    assert by["CWE-79"] == "Cross-site Scripting (XSS)"


def test_unzip_first_xml_reads_zipped_catalog():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "ignore me")
        zf.writestr("cwec_v4.20.xml", _CWE_XML)
    assert _unzip_first_xml(buf.getvalue()) == _CWE_XML
    # Le parseur consomme bien le XML décompressé.
    assert {w["ext_id"] for w in parse_cwe(_unzip_first_xml(buf.getvalue()))} == {"CWE-79", "CWE-89"}
