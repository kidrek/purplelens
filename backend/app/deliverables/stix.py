"""Export STIX 2.1 des scénarios (cahier §5 — interopérabilité CTI).

Fonctions pures (sans I/O) → testables : un scénario est converti en un *bundle*
STIX 2.1 cohérent. Cartographie retenue :

  scénario           → grouping (contexte de la campagne émulée)
  acteur émulé       → intrusion-set
  technique ATT&CK   → attack-pattern (external_reference mitre-attack)
  contre-mesure D3FEND → course-of-action
  « intrusion-set uses attack-pattern » → relationship
  IOC / IOA          → note (texte libre de la maquette — pas toujours un motif STIX valide)
  marquage TLP       → object_marking_refs vers la marking-definition TLP standard

Les identifiants STIX sont DÉTERMINISTES (UUIDv5) : réexporter le même scénario produit
le même bundle (diffs stables, idempotence côté récepteur).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

_SPEC = "2.1"
# Namespace stable pour dériver des UUIDv5 déterministes propres au produit.
_NS = uuid.UUID("6f8c0b4a-1d2e-5f3a-9b7c-000000000042")

# Marking-definitions TLP standard (identifiants canoniques STIX 2.1).
_TLP = {
    "CLEAR": "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9",  # = WHITE
    "WHITE": "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9",
    "GREEN": "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",
    "AMBER": "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82",
    "RED": "marking-definition--5e57c739-391a-4eb3-b6be-7d15ca92d5ed",
}
_TLP_NAME = {"CLEAR": "TLP:WHITE", "WHITE": "TLP:WHITE", "GREEN": "TLP:GREEN",
             "AMBER": "TLP:AMBER", "RED": "TLP:RED"}


def _sid(kind: str, *parts: str) -> str:
    """Identifiant STIX déterministe : type--uuidv5(parties)."""
    return f"{kind}--{uuid.uuid5(_NS, kind + '|' + '|'.join(parts))}"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _tlp_marking(tlp: str) -> dict[str, Any]:
    tlp = (tlp or "AMBER").upper()
    mid = _TLP.get(tlp, _TLP["AMBER"])
    return {
        "type": "marking-definition", "spec_version": _SPEC, "id": mid,
        "created": "2017-01-20T00:00:00.000Z", "definition_type": "tlp",
        "name": _TLP_NAME.get(tlp, "TLP:AMBER"),
        "definition": {"tlp": _TLP_NAME.get(tlp, "TLP:AMBER").split(":")[1].lower()},
    }


def _mitre_url(ext_id: str) -> str:
    # Sous-technique T1059.001 → techniques/T1059/001
    base = ext_id.replace(".", "/")
    return f"https://attack.mitre.org/techniques/{base}"


def scenario_to_objects(
    scenario: dict[str, Any], technique_names: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Objets STIX (sans bundle) pour UN scénario. `technique_names` : map ext_id→nom
    du référentiel (facultatif ; à défaut, l'ext_id fait office de nom)."""
    names = technique_names or {}
    now = _now()
    sc_key = str(scenario.get("id") or scenario.get("nom"))
    tlp = (scenario.get("tlp") or "AMBER").upper()
    marking = _tlp_marking(tlp)
    markings = [marking["id"]]

    objects: list[dict[str, Any]] = [marking]
    obj_refs: list[str] = []

    def _add(o: dict[str, Any]) -> str:
        o.setdefault("spec_version", _SPEC)
        o.setdefault("created", now)
        o.setdefault("modified", now)
        o.setdefault("object_marking_refs", markings)
        objects.append(o)
        obj_refs.append(o["id"])
        return o["id"]

    # Acteur émulé → intrusion-set
    actor_id = None
    if scenario.get("acteur_emule"):
        actor_id = _add({
            "type": "intrusion-set", "id": _sid("intrusion-set", scenario["acteur_emule"]),
            "name": scenario["acteur_emule"],
            "description": f"Acteur émulé — scénario « {scenario.get('nom', '')} ».",
        })

    # Techniques ATT&CK → attack-pattern (+ relation uses)
    for code in scenario.get("techniques") or []:
        ap_id = _add({
            "type": "attack-pattern", "id": _sid("attack-pattern", code),
            "name": names.get(code, code),
            "external_references": [{
                "source_name": "mitre-attack", "external_id": code, "url": _mitre_url(code),
            }],
        })
        if actor_id:
            _add({
                "type": "relationship",
                "id": _sid("relationship", sc_key, "uses", code),
                "relationship_type": "uses", "source_ref": actor_id, "target_ref": ap_id,
            })

    # Contre-mesures D3FEND → course-of-action
    for d in scenario.get("d3fend") or []:
        _add({
            "type": "course-of-action", "id": _sid("course-of-action", d),
            "name": d, "description": f"Contre-mesure D3FEND {d}.",
        })

    # IOC / IOA → note (texte libre, non garanti comme motif STIX valide)
    io_bits = []
    if scenario.get("ioc"):
        io_bits.append(f"IOC : {scenario['ioc']}")
    if scenario.get("ioa"):
        io_bits.append(f"IOA : {scenario['ioa']}")
    if io_bits and obj_refs:
        _add({
            "type": "note", "id": _sid("note", sc_key, "io"),
            "content": "\n".join(io_bits), "object_refs": list(obj_refs),
        })

    # Le scénario lui-même → grouping (contexte liant l'ensemble)
    grouping = {
        "type": "grouping", "spec_version": _SPEC,
        "id": _sid("grouping", sc_key),
        "created": now, "modified": now, "object_marking_refs": markings,
        "name": scenario.get("nom", "Scénario"),
        "context": "unspecified",
        "object_refs": list(obj_refs) or [marking["id"]],
    }
    desc = []
    if scenario.get("objectif"):
        desc.append(scenario["objectif"])
    if scenario.get("type_engagement"):
        desc.append(f"Engagement : {scenario['type_engagement']}.")
    if scenario.get("sophistication"):
        desc.append(f"Sophistication : {scenario['sophistication']}.")
    if desc:
        grouping["description"] = " ".join(desc)
    objects.insert(0, grouping)  # en tête du bundle

    return objects


def scenarios_to_bundle(
    scenarios: list[dict[str, Any]], technique_names: dict[str, str] | None = None
) -> dict[str, Any]:
    """Assemble un bundle STIX 2.1 pour un ou plusieurs scénarios, en dédupliquant
    les objets partagés (mêmes techniques/marquages entre scénarios)."""
    seen: dict[str, dict[str, Any]] = {}
    for sc in scenarios:
        for o in scenario_to_objects(sc, technique_names):
            seen.setdefault(o["id"], o)  # 1re occurrence gagne (déterministe)
    return {
        "type": "bundle",
        "id": _sid("bundle", *sorted(str(s.get("id") or s.get("nom")) for s in scenarios)),
        "objects": list(seen.values()),
    }


def bundle_to_scenarios(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Import inverse : extrait un/des scénario(s) d'un bundle STIX 2.1.

    Miroir de `scenarios_to_bundle`. Tolérant : accepte un bundle produit par cet outil
    (grouping + attack-pattern + intrusion-set + course-of-action + note) comme un bundle
    STIX tiers raisonnable. On reconstruit un scénario par `grouping` ; à défaut de
    grouping, on agrège tout le bundle en un scénario unique.

    Ne réalise AUCUNE écriture : fonction pure → l'appelant décide de la persistance.
    """
    objects = bundle.get("objects") or []
    by_id = {o.get("id"): o for o in objects if isinstance(o, dict) and o.get("id")}

    def _ext_id(ap: dict[str, Any]) -> str | None:
        for ref in ap.get("external_references") or []:
            if ref.get("source_name") == "mitre-attack" and ref.get("external_id"):
                return ref["external_id"]
        return None

    def _tlp_of(obj: dict[str, Any]) -> str:
        for mref in obj.get("object_marking_refs") or []:
            m = by_id.get(mref) or {}
            name = str(m.get("name", "")).upper()
            for level in ("RED", "AMBER", "GREEN", "WHITE", "CLEAR"):
                if level in name:
                    return "CLEAR" if level == "WHITE" else level
        return "AMBER"

    def _scenario_from_refs(name: str, tlp: str, refs: list[str],
                            description: str | None) -> dict[str, Any]:
        techniques, d3fend, actor, ioc_ioa = [], [], None, []
        for rid in refs:
            o = by_id.get(rid) or {}
            t = o.get("type")
            if t == "attack-pattern":
                code = _ext_id(o)
                if code and code not in techniques:
                    techniques.append(code)
            elif t == "course-of-action":
                nm = o.get("name")
                if nm and nm not in d3fend:
                    d3fend.append(nm)
            elif t == "intrusion-set":
                actor = actor or o.get("name")
            elif t == "note" and o.get("content"):
                ioc_ioa.append(o["content"])
        sc: dict[str, Any] = {
            "nom": name, "tlp": tlp, "techniques": techniques, "d3fend": d3fend,
        }
        if actor:
            sc["acteur_emule"] = actor
        if description:
            sc["objectif"] = description
        notes = "\n".join(ioc_ioa).strip()
        if notes:
            sc["notes_import"] = notes
        return sc

    scenarios: list[dict[str, Any]] = []
    groupings = [o for o in objects if isinstance(o, dict) and o.get("type") == "grouping"]
    if groupings:
        for g in groupings:
            scenarios.append(_scenario_from_refs(
                g.get("name") or "Scénario importé", _tlp_of(g),
                g.get("object_refs") or [], g.get("description"),
            ))
    else:
        # Pas de grouping : agréger tous les attack-pattern en un scénario unique.
        all_refs = [o["id"] for o in objects if isinstance(o, dict) and o.get("id")]
        tlp = next((_tlp_of(o) for o in objects if o.get("object_marking_refs")), "AMBER")
        scenarios.append(_scenario_from_refs("Scénario importé (STIX)", tlp, all_refs, None))
    return scenarios
