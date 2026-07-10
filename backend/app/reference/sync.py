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
    """Extrait les techniques ATT&CK actives d'un bundle STIX → [{ext_id, name, tactic}]."""
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
        # Préférer une tactique du jeu standard (regroupement de matrice propre).
        tactic = next((p for p in phases if p in _STD_TACTICS), phases[0] if phases else None)
        out.append({"ext_id": ext_id, "name": o.get("name") or ext_id, "tactic": tactic})
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


async def fetch_attack(url: str | None = None, timeout: float | None = None) -> list[dict]:
    return parse_attack(await _fetch_json(url or settings.attack_stix_url, timeout))


async def fetch_d3fend(url: str | None = None, timeout: float | None = None) -> list[dict]:
    return parse_d3fend(await _fetch_json(url or settings.d3fend_ontology_url, timeout))


# Catalogues synchronisables en ligne et leur source.
SYNCABLE = {
    "attack": {"fetch": fetch_attack, "table": "ref_attack_technique", "has_tactic": True},
    "d3fend": {"fetch": fetch_d3fend, "table": "ref_d3fend", "has_tactic": False},
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
        if spec["has_tactic"]:
            await session.execute(text(
                f"INSERT INTO {table} (id, ext_id, name, tactic, data) "
                "VALUES (gen_random_uuid(), :e, :n, :t, '{}') "
                "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, "
                "tactic = EXCLUDED.tactic, updated_at = now()"
            ), {"e": r["ext_id"], "n": r["name"][:255], "t": r.get("tactic")})
        else:
            await session.execute(text(
                f"INSERT INTO {table} (id, ext_id, name, data) "
                "VALUES (gen_random_uuid(), :e, :n, '{}') "
                "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, updated_at = now()"
            ), {"e": r["ext_id"], "n": r["name"][:255]})
    return len(rows)
