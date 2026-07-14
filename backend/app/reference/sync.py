"""Synchronisation en ligne des référentiels depuis les sources amont MITRE.

- ATT&CK Enterprise : bundle STIX 2.1 officiel (attack-stix-data). On retient les
  attack-pattern actifs (ni révoqués ni dépréciés) → ext_id, nom, tactique.
- D3FEND : ontologie JSON-LD officielle. On retient les nœuds portant un `d3fend-id`
  → ext_id, nom (libellé ou identifiant lisible).

Ces catalogues complets (≈700 techniques ATT&CK) remplacent le socle embarqué. La
dégradation est gracieuse : en cas d'indisponibilité réseau, l'appelant conserve le socle.
URLs et délai configurables (instances miroir / air-gap possibles).
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import settings


class SyncUnavailable(Exception):
    """Source amont injoignable → l'appelant retombe sur le socle embarqué."""


async def _fetch_json(url: str, timeout: float | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=timeout or settings.reference_sync_timeout_seconds,
                                     follow_redirects=True) as c:
            r = await c.get(url, headers={"Accept": "application/json"})
    except (httpx.HTTPError, OSError) as exc:
        raise SyncUnavailable(str(exc)) from exc
    if r.status_code >= 400:
        raise SyncUnavailable(f"HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError as exc:
        raise SyncUnavailable("réponse non-JSON") from exc


_STD_TACTICS = {
    "reconnaissance", "resource-development", "initial-access", "execution",
    "persistence", "privilege-escalation", "defense-evasion", "credential-access",
    "discovery", "lateral-movement", "collection", "command-and-control",
    "exfiltration", "impact",
}


def parse_attack(bundle: dict) -> list[dict]:
    """Extrait les techniques ATT&CK actives d'un bundle STIX → [{ext_id, name, tactic, tactics}].

    Une technique ATT&CK relève souvent de PLUSIEURS tactiques (ex. T1078 « Valid Accounts »
    → initial-access, persistence, privilege-escalation, defense-evasion). On conserve
    l'ensemble des tactiques standard rattachées (`tactics`) afin que la matrice affiche la
    technique dans chaque colonne concernée, comme le Navigator officiel. `tactic` reste la
    tactique primaire (première rattachée) pour la rétro-compatibilité.
    """
    out: list[dict] = []
    for o in bundle.get("objects", []):
        if not isinstance(o, dict) or o.get("type") != "attack-pattern":
            continue
        if o.get("revoked") or o.get("x_mitre_deprecated"):
            continue
        ext_id = next((r.get("external_id") for r in o.get("external_references", [])
                       if isinstance(r, dict) and r.get("source_name") == "mitre-attack"
                       and r.get("external_id")), None)
        if not ext_id:
            continue
        phases = [p.get("phase_name") for p in o.get("kill_chain_phases", [])
                  if isinstance(p, dict) and p.get("kill_chain_name") == "mitre-attack"]
        # Toutes les tactiques du jeu standard (ordre du bundle préservé, dédupliqué) ;
        # repli sur la première phase brute si aucune n'est standard.
        tactics = list(dict.fromkeys(p for p in phases if p in _STD_TACTICS))
        if not tactics and phases:
            tactics = [phases[0]]
        out.append({"ext_id": ext_id, "name": o.get("name") or ext_id,
                    "tactic": tactics[0] if tactics else None, "tactics": tactics})
    return out


_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _label_from_id(iri: str) -> str:
    local = iri.split(":")[-1].split("/")[-1].split("#")[-1]
    return _CAMEL.sub(" ", local).strip() or local


def parse_d3fend(doc: dict) -> list[dict]:
    """Extrait les techniques D3FEND (nœuds à `d3fend-id`) → [{ext_id, name}]."""
    graph = doc.get("@graph") or doc.get("graph") or []
    out: list[dict] = []
    seen: set[str] = set()
    for n in graph:
        if not isinstance(n, dict):
            continue
        # Le champ peut être "d3f:d3fend-id" (contexte compacté) ou "d3fend-id".
        ext_id = n.get("d3f:d3fend-id") or n.get("d3fend-id")
        if isinstance(ext_id, dict):
            ext_id = ext_id.get("@value")
        if not isinstance(ext_id, str) or not ext_id.startswith("D3-"):
            continue
        if ext_id in seen:
            continue
        seen.add(ext_id)
        label = n.get("rdfs:label") or n.get("label")
        if isinstance(label, dict):
            label = label.get("@value")
        name = label if isinstance(label, str) and label.strip() else _label_from_id(n.get("@id", ext_id))
        out.append({"ext_id": ext_id, "name": name})
    return out


def _attack_ext_id(o: dict) -> str | None:
    return next((r.get("external_id") for r in o.get("external_references", [])
                 if isinstance(r, dict) and r.get("source_name") == "mitre-attack"
                 and r.get("external_id")), None)


def parse_attack_groups(bundle: dict) -> list[dict]:
    """Extrait les acteurs (intrusion-set) et leurs TTPs du bundle enterprise-attack.

    Le même bundle STIX que `parse_attack` contient les groupes (`intrusion-set`) et les
    relations `intrusion-set --uses--> attack-pattern`. On en dérive, par acteur :
    { ext_id (Gxxxx), name, data:{aliases, techniques} } — techniques dédupliquées, ordre
    des relations préservé. Groupes/relations révoqués ou dépréciés ignorés.
    """
    groups: dict[str, dict] = {}       # id STIX intrusion-set -> acteur
    tech_by_stix: dict[str, str] = {}  # id STIX attack-pattern -> ext_id technique
    for o in bundle.get("objects", []):
        if not isinstance(o, dict) or o.get("revoked") or o.get("x_mitre_deprecated"):
            continue
        t = o.get("type")
        if t == "intrusion-set":
            ext_id = _attack_ext_id(o)
            if not ext_id:
                continue
            name = o.get("name") or ext_id
            aliases = [a for a in (o.get("aliases") or o.get("x_mitre_aliases") or [])
                       if isinstance(a, str) and a and a != name]
            groups[o.get("id")] = {"ext_id": ext_id, "name": name,
                                   "aliases": list(dict.fromkeys(aliases)), "techniques": []}
        elif t == "attack-pattern":
            ext_id = _attack_ext_id(o)
            if ext_id and o.get("id"):
                tech_by_stix[o["id"]] = ext_id
    for o in bundle.get("objects", []):
        if not isinstance(o, dict) or o.get("type") != "relationship":
            continue
        if o.get("relationship_type") != "uses" or o.get("revoked"):
            continue
        src, tgt = o.get("source_ref"), o.get("target_ref")
        g = groups.get(src) if isinstance(src, str) else None
        tech = tech_by_stix.get(tgt) if isinstance(tgt, str) else None
        if g and tech and tech not in g["techniques"]:
            g["techniques"].append(tech)
    return [{"ext_id": g["ext_id"], "name": g["name"],
             "data": {"aliases": g["aliases"], "techniques": g["techniques"]}}
            for g in groups.values()]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def parse_misp_actors(doc: dict, groups: list[dict] | None = None) -> list[dict]:
    """Extrait les acteurs du cluster MISP Galaxy `threat-actor` → [{ext_id, name, data}].

    MISP fournit l'identité de l'acteur et ses synonymes ; les TTPs ATT&CK sont résolues en
    croisant nom/alias avec les groupes MITRE (`groups`, issus de `parse_attack_groups`).
    Sans correspondance MITRE, `techniques` reste vide (partiel honnête — l'acteur enrichit
    tout de même le nommage et les alias pour la recherche fusionnée).
    """
    index: dict[str, list[str]] = {}
    for g in (groups or []):
        techs = g.get("data", {}).get("techniques", [])
        for key in [g.get("name", ""), *g.get("data", {}).get("aliases", [])]:
            index.setdefault(_norm(key), []).extend(techs)
    out: list[dict] = []
    for v in doc.get("values", []):
        if not isinstance(v, dict):
            continue
        name = v.get("value")
        if not name:
            continue
        meta = v.get("meta") or {}
        aliases = list(dict.fromkeys(
            a for a in (meta.get("synonyms") or []) if isinstance(a, str) and a and a != name))
        techniques: list[str] = []
        for key in [name, *aliases]:
            for t in index.get(_norm(key), []):
                if t not in techniques:
                    techniques.append(t)
        ext_id = str(v.get("uuid") or _norm(name))[:64]
        out.append({"ext_id": ext_id, "name": name,
                    "data": {"aliases": aliases, "techniques": techniques}})
    return out


async def fetch_attack(url: str | None = None, timeout: float | None = None) -> list[dict]:
    return parse_attack(await _fetch_json(url or settings.attack_stix_url, timeout))


async def fetch_d3fend(url: str | None = None, timeout: float | None = None) -> list[dict]:
    return parse_d3fend(await _fetch_json(url or settings.d3fend_ontology_url, timeout))


async def fetch_attack_groups(url: str | None = None, timeout: float | None = None) -> list[dict]:
    return parse_attack_groups(await _fetch_json(url or settings.attack_stix_url, timeout))


async def fetch_misp_actors(url: str | None = None, timeout: float | None = None) -> list[dict]:
    # Le mapping acteur→TTPs vient des groupes MITRE : on récupère aussi le bundle ATT&CK.
    doc = await _fetch_json(url or settings.misp_threat_actor_url, timeout)
    groups = parse_attack_groups(await _fetch_json(settings.attack_stix_url, timeout))
    return parse_misp_actors(doc, groups)


# Catalogues synchronisables en ligne et leur source.
SYNCABLE = {
    "attack": {"fetch": fetch_attack, "table": "ref_attack_technique", "has_tactic": True},
    "d3fend": {"fetch": fetch_d3fend, "table": "ref_d3fend", "has_tactic": False},
    "attack_groups": {"fetch": fetch_attack_groups, "table": "ref_attack_group",
                      "has_tactic": False, "has_data": True, "source": "attack.mitre.org"},
    "misp_actors": {"fetch": fetch_misp_actors, "table": "ref_misp_actor",
                    "has_tactic": False, "has_data": True, "source": "misp-galaxy"},
}


async def sync_catalog(session, catalog_id: str) -> int:
    """Récupère un catalogue en ligne et l'upsert en base. Retourne le nombre d'entrées.

    Lève SyncUnavailable si la source amont est injoignable (l'appelant peut alors se
    rabattre sur le socle embarqué).
    """
    from sqlalchemy import text

    spec = SYNCABLE.get(catalog_id)
    if spec is None:
        raise KeyError(catalog_id)
    rows = await spec["fetch"]()
    table = spec["table"]
    for r in rows:
        if spec.get("has_data"):
            data = r.get("data") or {}
            await session.execute(text(
                f"INSERT INTO {table} (id, ext_id, name, data) "
                "VALUES (gen_random_uuid(), :e, :n, CAST(:d AS jsonb)) "
                "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, "
                "data = EXCLUDED.data, updated_at = now()"
            ), {"e": r["ext_id"], "n": r["name"][:255], "d": json.dumps({
                "aliases": data.get("aliases", []), "techniques": data.get("techniques", []),
                "source": spec.get("source", "")})})
        elif spec["has_tactic"]:
            tactics = r.get("tactics") or ([r["tactic"]] if r.get("tactic") else [])
            await session.execute(text(
                f"INSERT INTO {table} (id, ext_id, name, tactic, data) "
                "VALUES (gen_random_uuid(), :e, :n, :t, CAST(:d AS jsonb)) "
                "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, "
                "tactic = EXCLUDED.tactic, data = EXCLUDED.data, updated_at = now()"
            ), {"e": r["ext_id"], "n": r["name"][:255], "t": r.get("tactic"),
                "d": json.dumps({"tactics": tactics})})
        else:
            await session.execute(text(
                f"INSERT INTO {table} (id, ext_id, name, data) "
                "VALUES (gen_random_uuid(), :e, :n, '{}') "
                "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, updated_at = now()"
            ), {"e": r["ext_id"], "n": r["name"][:255]})
    return len(rows)
