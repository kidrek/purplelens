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

import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
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


async def _fetch_bytes(url: str, timeout: float | None = None) -> bytes:
    """Récupère un contenu binaire (XML brut ou archive) depuis une source amont.

    Même politique de dégradation gracieuse que `_fetch_json` : toute erreur réseau/HTTP
    lève `SyncUnavailable` pour que l'appelant retombe sur le socle embarqué.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout or settings.reference_sync_timeout_seconds,
                                     follow_redirects=True) as c:
            r = await c.get(url)
    except (httpx.HTTPError, OSError) as exc:
        raise SyncUnavailable(str(exc)) from exc
    if r.status_code >= 400:
        raise SyncUnavailable(f"HTTP {r.status_code}")
    return r.content


def _local_name(tag: str) -> str:
    """Nom local d'une balise XML, sans son namespace (`{ns}Weakness` → `Weakness`)."""
    return tag.rsplit("}", 1)[-1]


def parse_capec(xml_bytes: bytes) -> list[dict]:
    """Extrait les patterns d'attaque du catalogue CAPEC complet (XML MITRE).

    On retient chaque `Attack_Pattern` non déprécié → ext_id `CAPEC-<ID>`, nom.
    Robuste au namespace par défaut du XML (match sur le nom local).
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise SyncUnavailable(f"XML CAPEC illisible: {exc}") from exc
    out: list[dict] = []
    for el in root.iter():
        if _local_name(el.tag) != "Attack_Pattern":
            continue
        if el.get("Status", "") in {"Deprecated", "Obsolete"}:
            continue
        ext, name = el.get("ID"), el.get("Name")
        if ext and name:
            out.append({"ext_id": f"CAPEC-{ext}", "name": name})
    return out


def parse_cwe(xml_bytes: bytes) -> list[dict]:
    """Extrait les faiblesses du dictionnaire CWE complet (XML MITRE).

    On retient chaque `Weakness` non dépréciée → ext_id `CWE-<ID>`, nom (on ignore les
    éléments `Category`/`View`). Robuste au namespace par défaut du XML.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise SyncUnavailable(f"XML CWE illisible: {exc}") from exc
    out: list[dict] = []
    for el in root.iter():
        if _local_name(el.tag) != "Weakness":
            continue
        if el.get("Status", "") in {"Deprecated", "Obsolete"}:
            continue
        ext, name = el.get("ID"), el.get("Name")
        if ext and name:
            out.append({"ext_id": f"CWE-{ext}", "name": name})
    return out


def _unzip_first_xml(raw: bytes) -> bytes:
    """Renvoie le premier membre `*.xml` d'une archive ZIP téléchargée."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            member = next(n for n in zf.namelist() if n.lower().endswith(".xml"))
            return zf.read(member)
    except (zipfile.BadZipFile, StopIteration, KeyError, OSError) as exc:
        raise SyncUnavailable(f"archive illisible: {exc}") from exc


_STD_TACTICS = {
    "reconnaissance", "resource-development", "initial-access", "execution",
    "persistence", "privilege-escalation", "defense-evasion", "credential-access",
    "discovery", "lateral-movement", "collection", "command-and-control",
    "exfiltration", "impact",
}
# Tactiques propres aux matrices Mobile et ICS (les autres recouvrent l'Enterprise).
# Mobile actuel : « stealth » et « defense-impairment » (les anciennes network-effects /
# remote-service-effects ont été retirées par MITRE).
_MOBILE_TACTICS = {"stealth", "defense-impairment"}
_ICS_TACTICS = {"evasion", "inhibit-response-function", "impair-process-control"}
_ALL_TACTICS = _STD_TACTICS | _MOBILE_TACTICS | _ICS_TACTICS

# Domaines ATT&CK et leurs identifiants STIX (source_name des références + kill_chain_name).
# La même clé sert au tag `data.domains` persisté en base.
_ATTACK_DOMAINS = {
    "enterprise": "mitre-attack",
    "mobile": "mitre-mobile-attack",
    "ics": "mitre-ics-attack",
}
_ATTACK_SOURCES = set(_ATTACK_DOMAINS.values())


def parse_attack(bundle: dict, domain: str = "enterprise") -> list[dict]:
    """Extrait les techniques ATT&CK actives d'un bundle STIX → [{ext_id, name, tactic,
    tactics, domains, description}].

    Prend en charge les trois matrices (Enterprise, Mobile, ICS) : l'`ext_id` (T-number) et
    les phases sont reconnus quel que soit le `source_name`/`kill_chain_name` du domaine
    (`mitre-attack`, `mitre-mobile-attack`, `mitre-ics-attack`). Une technique relève souvent
    de PLUSIEURS tactiques (ex. T1078 « Valid Accounts ») ; on conserve l'ensemble des
    tactiques MITRE connues (`tactics`, toutes matrices) afin que la matrice affiche la
    technique dans chaque colonne, comme le Navigator officiel. `tactic` reste la tactique
    primaire (première rattachée). `domains` marque la ou les matrices d'origine.
    """
    out: list[dict] = []
    for o in bundle.get("objects", []):
        if not isinstance(o, dict) or o.get("type") != "attack-pattern":
            continue
        if o.get("revoked") or o.get("x_mitre_deprecated"):
            continue
        ext_id = next((r.get("external_id") for r in o.get("external_references", [])
                       if isinstance(r, dict) and r.get("source_name") in _ATTACK_SOURCES
                       and r.get("external_id")), None)
        if not ext_id:
            continue
        phases = [p.get("phase_name") for p in o.get("kill_chain_phases", [])
                  if isinstance(p, dict) and p.get("kill_chain_name") in _ATTACK_SOURCES]
        # Toutes les tactiques MITRE connues (ordre du bundle préservé, dédupliqué) ;
        # repli sur la première phase brute si aucune n'est reconnue.
        tactics = list(dict.fromkeys(p for p in phases if p in _ALL_TACTICS))
        if not tactics and phases:
            tactics = [phases[0]]
        out.append({"ext_id": ext_id, "name": o.get("name") or ext_id,
                    "tactic": tactics[0] if tactics else None, "tactics": tactics,
                    "domains": [domain], "description": o.get("description")})
    return out


def _merge_technique(merged: dict[str, dict], t: dict) -> None:
    """Fusionne une technique dans l'index par ext_id : union des tactiques et des domaines
    (ordre préservé), nom/description existants conservés (Enterprise chargé en premier),
    `tactic` primaire recalculé sur les tactiques fusionnées."""
    cur = merged.get(t["ext_id"])
    if cur is None:
        merged[t["ext_id"]] = t
        return
    cur["tactics"] = list(dict.fromkeys([*cur.get("tactics", []), *t.get("tactics", [])]))
    cur["domains"] = list(dict.fromkeys([*cur.get("domains", []), *t.get("domains", [])]))
    cur["tactic"] = cur["tactics"][0] if cur["tactics"] else cur.get("tactic")
    if not cur.get("description") and t.get("description"):
        cur["description"] = t["description"]


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
    { ext_id (Gxxxx), name, data:{aliases, techniques, procedures} } — techniques
    dédupliquées, ordre des relations préservé. `procedures` mappe ext_id technique →
    description de la relation `uses` (les « procedure examples » : comment CET acteur
    emploie la technique), utilisée pour pré-remplir le contexte d'une étape offensive.
    Groupes/relations révoqués ou dépréciés ignorés.
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
                                   "aliases": list(dict.fromkeys(aliases)),
                                   "techniques": [], "procedures": {}}
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
        if g and tech:
            if tech not in g["techniques"]:
                g["techniques"].append(tech)
            desc = o.get("description")
            if isinstance(desc, str) and desc.strip() and tech not in g["procedures"]:
                g["procedures"][tech] = desc
    return [{"ext_id": g["ext_id"], "name": g["name"],
             "data": {"aliases": g["aliases"], "techniques": g["techniques"],
                      "procedures": g["procedures"]}}
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
    proc_index: dict[str, dict[str, str]] = {}  # norm(nom/alias) -> {ext_id tech: procédure}
    for g in (groups or []):
        techs = g.get("data", {}).get("techniques", [])
        procs = g.get("data", {}).get("procedures", {})
        for key in [g.get("name", ""), *g.get("data", {}).get("aliases", [])]:
            index.setdefault(_norm(key), []).extend(techs)
            proc_index.setdefault(_norm(key), {}).update(procs)
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
        procedures: dict[str, str] = {}
        for key in [name, *aliases]:
            for t in index.get(_norm(key), []):
                if t not in techniques:
                    techniques.append(t)
            for t, desc in proc_index.get(_norm(key), {}).items():
                procedures.setdefault(t, desc)
        ext_id = str(v.get("uuid") or _norm(name))[:64]
        out.append({"ext_id": ext_id, "name": name,
                    "data": {"aliases": aliases, "techniques": techniques,
                             "procedures": procedures}})
    return out


async def fetch_attack(url: str | None = None, timeout: float | None = None) -> list[dict]:
    """Techniques ATT&CK des trois matrices fusionnées dans le même catalogue.

    Enterprise est REQUIS (échec → SyncUnavailable → repli sur le socle embarqué). Mobile et
    ICS sont best-effort : une source injoignable est simplement ignorée (on conserve
    l'Enterprise déjà chargé). Fusion par ext_id (T-number) : union des tactiques et des
    domaines (`data.domains`).
    """
    merged: dict[str, dict] = {}
    for t in parse_attack(await _fetch_json(url or settings.attack_stix_url, timeout),
                          "enterprise"):
        merged[t["ext_id"]] = t
    for domain, source in (("mobile", settings.attack_mobile_stix_url),
                           ("ics", settings.attack_ics_stix_url)):
        try:
            extra = parse_attack(await _fetch_json(source, timeout), domain)
        except SyncUnavailable:
            continue  # matrice secondaire injoignable → on garde l'Enterprise
        for t in extra:
            _merge_technique(merged, t)
    return list(merged.values())


async def fetch_d3fend(url: str | None = None, timeout: float | None = None) -> list[dict]:
    return parse_d3fend(await _fetch_json(url or settings.d3fend_ontology_url, timeout))


async def fetch_attack_groups(url: str | None = None, timeout: float | None = None) -> list[dict]:
    return parse_attack_groups(await _fetch_json(url or settings.attack_stix_url, timeout))


async def fetch_misp_actors(url: str | None = None, timeout: float | None = None) -> list[dict]:
    # Le mapping acteur→TTPs vient des groupes MITRE : on récupère aussi le bundle ATT&CK.
    doc = await _fetch_json(url or settings.misp_threat_actor_url, timeout)
    groups = parse_attack_groups(await _fetch_json(settings.attack_stix_url, timeout))
    return parse_misp_actors(doc, groups)


async def fetch_capec(url: str | None = None, timeout: float | None = None) -> list[dict]:
    # CAPEC est publié en XML non compressé (capec_latest.xml).
    return parse_capec(await _fetch_bytes(url or settings.capec_xml_url, timeout))


async def fetch_cwe(url: str | None = None, timeout: float | None = None) -> list[dict]:
    # CWE est publié en XML compressé (cwec_latest.xml.zip) → décompression en mémoire.
    raw = await _fetch_bytes(url or settings.cwe_xml_zip_url, timeout)
    return parse_cwe(_unzip_first_xml(raw))


# Catalogues synchronisables en ligne et leur source.
SYNCABLE = {
    "attack": {"fetch": fetch_attack, "table": "ref_attack_technique", "has_tactic": True},
    "d3fend": {"fetch": fetch_d3fend, "table": "ref_d3fend", "has_tactic": False},
    "attack_groups": {"fetch": fetch_attack_groups, "table": "ref_attack_group",
                      "has_tactic": False, "has_data": True, "source": "attack.mitre.org"},
    "misp_actors": {"fetch": fetch_misp_actors, "table": "ref_misp_actor",
                    "has_tactic": False, "has_data": True, "source": "misp-galaxy"},
    # Catalogues « name-only » (branche else de sync_catalog) : dictionnaires complets MITRE.
    "capec": {"fetch": fetch_capec, "table": "ref_capec", "has_tactic": False},
    "cwe": {"fetch": fetch_cwe, "table": "ref_cwe", "has_tactic": False},
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
                "procedures": data.get("procedures", {}), "source": spec.get("source", "")})})
        elif spec["has_tactic"]:
            tactics = r.get("tactics") or ([r["tactic"]] if r.get("tactic") else [])
            await session.execute(text(
                f"INSERT INTO {table} (id, ext_id, name, tactic, data) "
                "VALUES (gen_random_uuid(), :e, :n, :t, CAST(:d AS jsonb)) "
                "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, "
                "tactic = EXCLUDED.tactic, data = EXCLUDED.data, updated_at = now()"
            ), {"e": r["ext_id"], "n": r["name"][:255], "t": r.get("tactic"),
                "d": json.dumps({"tactics": tactics, "description": r.get("description"),
                                 "domains": r.get("domains", [])})})
        else:
            await session.execute(text(
                f"INSERT INTO {table} (id, ext_id, name, data) "
                "VALUES (gen_random_uuid(), :e, :n, '{}') "
                "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, updated_at = now()"
            ), {"e": r["ext_id"], "n": r["name"][:255]})
    return len(rows)


async def sync_all_catalogs(session, *, prefer_online: bool = True) -> dict[str, dict]:
    """(Ré)synchronise tous les catalogues et retourne un récap par catalogue.

    Pour chaque catalogue : s'il est synchronisable (SYNCABLE) et que `prefer_online`,
    tente l'amont MITRE avec repli gracieux sur le socle embarqué en cas de source
    injoignable (SyncUnavailable) ; sinon charge directement le socle embarqué.

    Retourne `{cid: {"entries": n, "source": "upstream"|"fallback"|"embedded"}}`.
    Idempotent (upserts ON CONFLICT). Partagé par l'endpoint « Tout synchroniser »
    et le seed initial (bootstrap des conteneurs).
    """
    from app.reference.catalogs import CATALOGS, import_catalog

    result: dict[str, dict] = {}
    for cat in CATALOGS:
        cid = cat["id"]
        if prefer_online and cid in SYNCABLE:
            try:
                n = await sync_catalog(session, cid)
                source = "upstream"
            except SyncUnavailable:
                n = await import_catalog(session, cid)
                source = "fallback"
        else:
            n = await import_catalog(session, cid)
            source = "embedded"
        result[cid] = {"entries": n, "source": source}
    return result
