"""
Service D3FEND — synchronisation du mapping ATT&CK → D3FEND.

Source : ontologie TTL officielle D3FEND sur GitHub
  https://raw.githubusercontent.com/d3fend/d3fend-ontology/master/src/ontology/d3fend-protege.ttl

Pourquoi le TTL et pas le d3fend.json officiel ?
  Le fichier d3fend.mitre.org/ontologies/d3fend.json est une ontologie de définitions
  (classes OWL, propriétés, individus). Les mappings ATT&CK→D3FEND sont calculés par
  inférence OWL côté MITRE (raisonneur) et ne sont pas présents dans ce fichier.

Algorithme de mapping :
  Le TTL encode les relations via des restrictions OWL :
    - Technique ATT&CK → owl:someValuesFrom → DigitalArtifact (ce qu'elle utilise)
    - Technique D3FEND → owl:someValuesFrom → DigitalArtifact (ce qu'elle défend)
  En croisant via la hiérarchie de classes OWL (expansion 1 niveau pour ATT&CK,
  2 niveaux pour D3FEND), on reconstitue les mappings inférés par MITRE.
"""

import json
import re
import urllib.request
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.d3fend import D3fendMapping
from app.models.referentials import ReferentialMeta

D3FEND_REF_NAME = "d3fend"

D3FEND_TTL_URL = (
    "https://raw.githubusercontent.com/d3fend/d3fend-ontology"
    "/master/src/ontology/d3fend-protege.ttl"
)
D3FEND_JSON_URL = "https://d3fend.mitre.org/ontologies/d3fend.json"  # référence affichée

CATEGORY_MAP = {
    "Detect":   "detect",  "detect":   "detect",  "Detection":  "detect",
    "Harden":   "harden",  "harden":   "harden",  "Hardening":  "harden",
    "Isolate":  "isolate", "isolate":  "isolate", "Isolation":  "isolate",
    "Deceive":  "deceive", "deceive":  "deceive", "Deception":  "deceive",
    "Evict":    "evict",   "evict":    "evict",   "Eviction":   "evict",
    "Restore":  "restore", "restore":  "restore", "Restoration":"restore",
}
_CAT_WORDS    = set(CATEGORY_MAP.keys())
_EXCL_SUFX    = (
    "Technique", "Tactic", "Ontology", "Property",
    "Class", "Individual", "Restriction",
)


def _normalize_category(raw: str) -> str:
    return CATEGORY_MAP.get(raw, raw.lower().strip()) if raw else ""


def _camel_to_label(s: str) -> str:
    return re.sub(r"([A-Z])", r" \1", s).strip()


def _extract_d3f_id(d3f_tech: str) -> str:
    return d3f_tech.split(":")[-1].strip() if ":" in d3f_tech else d3f_tech.strip()


# ── Parser TTL (source principale) ────────────────────────────────────────────

def _parse_ttl(content: str) -> list[dict]:
    """
    Parse l'ontologie TTL D3FEND et retourne les mappings ATT&CK→D3FEND.

    Étapes :
      1. Construire la hiérarchie de classes (parent_map) et les catégories D3FEND.
      2. Pour chaque bloc :
           - ATT&CK T1xxx → extraire les artefacts + expansion 1 niveau
           - D3FEND (d3fend-id) → extraire les artefacts + expansion 2 niveaux
      3. Croiser : si artefacts ATT&CK ∩ artefacts D3FEND ≠ ∅ → mapping.
    """
    blocks = re.split(r"\n(?=:\w)", content)

    # Étape 1 : hiérarchie de classes et catégories
    parent_map: dict[str, set] = defaultdict(set)
    class_category: dict[str, str] = {}

    for block in blocks:
        name_m = re.match(r"^:(\w+)\s+a\s+", block)
        if not name_m:
            continue
        cls = name_m.group(1)
        for p in re.findall(r"rdfs:subClassOf\s+:(\w+)", block):
            parent_map[cls].add(p)
        # Catégorie via restriction enables → someValuesFrom :Detect/Harden/…
        for pat in (
            r"owl:onProperty\s+:enables[\s\S]{0,150}?owl:someValuesFrom\s+:(\w+)",
            r"owl:someValuesFrom\s+:(\w+)[\s\S]{0,150}?owl:onProperty\s+:enables",
        ):
            for cat in re.findall(pat, block):
                if cat in CATEGORY_MAP:
                    class_category[cls] = CATEGORY_MAP[cat]
                    break

    def resolve_category(cls: str, visited: set | None = None) -> str:
        if visited is None:
            visited = set()
        if cls in visited:
            return ""
        visited.add(cls)
        if cls in class_category:
            return class_category[cls]
        for p in parent_map.get(cls, set()):
            c = resolve_category(p, visited)
            if c:
                return c
        return ""

    def expand(arts: set, depth: int) -> set:
        """Ajoute les classes parentes jusqu'à `depth` niveaux."""
        result = set(arts)
        frontier = set(arts)
        for _ in range(depth):
            nxt = set()
            for a in frontier:
                nxt |= parent_map.get(a, set())
            nxt -= result
            result |= nxt
            frontier = nxt
            if not frontier:
                break
        return result

    def clean(arts: set) -> set:
        return {
            a for a in arts
            if not any(a.endswith(s) for s in _EXCL_SUFX) and a not in _CAT_WORDS
        }

    # Étape 2 : extraire artefacts par bloc
    d3fend_map: dict[str, dict] = {}
    attack_map: dict[str, set]  = {}

    for block in blocks:
        raw_arts = clean(set(re.findall(r"owl:someValuesFrom\s+:(\w+)", block)))
        if not raw_arts:
            continue

        # Bloc D3FEND
        d3f_id_m = re.search(r":d3fend-id\s+\"([^\"]+)\"", block)
        if d3f_id_m:
            label_m  = re.search(r"rdfs:label\s+\"([^\"]+)\"", block)
            cls_m    = re.match(r"^:(\w+)\s+a\s+", block)
            cls_name = cls_m.group(1) if cls_m else ""
            d3fend_map[d3f_id_m.group(1)] = {
                "name":     label_m.group(1) if label_m else d3f_id_m.group(1),
                "category": resolve_category(cls_name),
                "artifacts": clean(expand(raw_arts, depth=2)),
            }

        # Bloc ATT&CK Enterprise (T1xxx uniquement)
        attack_m = re.search(r":attack-id\s+\"(T1\d{3}(?:\.\d{3})?)\"", block)
        if attack_m:
            attack_map[attack_m.group(1)] = clean(expand(raw_arts, depth=1))

    # Étape 3 : croisement
    entries: list[dict] = []
    for t_code, t_arts in attack_map.items():
        for d3f_id, d3f_data in d3fend_map.items():
            if t_arts & d3f_data["artifacts"]:
                entries.append({
                    "mitre_id":    t_code,
                    "d3f_id":      d3f_id,
                    "name":        d3f_data["name"],
                    "category":    d3f_data["category"],
                    "description": "",
                })

    return entries


# ── Parser JSON-LD (compatibilité pour fichiers de mapping tiers) ─────────────

def _parse_jsonld(data: dict) -> list[dict]:
    graph = data.get("@graph", [])
    id_to_attack: dict[str, str] = {}
    for node in graph:
        nid     = node.get("@id", "")
        att_raw = node.get("d3f:attack-id") or node.get("attack-id") or ""
        if isinstance(att_raw, dict):
            att_raw = att_raw.get("@value", "")
        if att_raw and re.match(r"T\d{4}", str(att_raw)):
            id_to_attack[nid] = str(att_raw)
        local = nid.split(":")[-1] if ":" in nid else nid
        if re.match(r"T\d{4}", local):
            id_to_attack[nid] = local

    entries: list[dict] = []
    for node in graph:
        d3f_id_raw = node.get("d3f:d3fend-id") or node.get("d3fend-id")
        if not d3f_id_raw:
            nid   = node.get("@id", "")
            local = nid.split(":")[-1] if ":" in nid else nid
            if re.match(r"D3-", local):
                d3f_id_raw = local
        if not d3f_id_raw:
            continue
        d3f_id = d3f_id_raw.get("@value", d3f_id_raw) if isinstance(d3f_id_raw, dict) else str(d3f_id_raw)

        label_raw = node.get("rdfs:label") or d3f_id
        if isinstance(label_raw, dict):
            label_raw = label_raw.get("@value", d3f_id)
        if isinstance(label_raw, list):
            label_raw = next((x.get("@value", x) if isinstance(x, dict) else x for x in label_raw), d3f_id)
        name = str(label_raw)

        enables_raw = node.get("d3f:enables") or {}
        if isinstance(enables_raw, list):
            enables_raw = enables_raw[0] if enables_raw else {}
        enables_id = enables_raw.get("@id", "") if isinstance(enables_raw, dict) else str(enables_raw)
        category   = _normalize_category(enables_id.split(":")[-1] if ":" in enables_id else enables_id)

        desc_raw    = node.get("d3f:definition") or ""
        description = (desc_raw.get("@value", "") if isinstance(desc_raw, dict) else str(desc_raw))[:500]

        counters_raw = node.get("d3f:may-counter") or []
        if isinstance(counters_raw, dict):
            counters_raw = [counters_raw]
        for ctr in counters_raw:
            ref_id    = ctr.get("@id", "") if isinstance(ctr, dict) else str(ctr)
            attack_id = id_to_attack.get(ref_id)
            if not attack_id:
                local = ref_id.split(":")[-1] if ":" in ref_id else ref_id
                if re.match(r"T\d{4}", local):
                    attack_id = local
            if attack_id and re.match(r"T\d{4}", attack_id):
                entries.append({
                    "mitre_id":    attack_id,
                    "d3f_id":      d3f_id,
                    "name":        name,
                    "category":    category,
                    "description": description,
                })
    return entries


def _parse_mapping_format(data) -> list[dict]:
    entries: list[dict] = []
    if isinstance(data, dict) and "mapping" in data:
        for item in data["mapping"]:
            attack_id = item.get("attack_id") or item.get("attack_technique") or ""
            if not attack_id:
                continue
            d3f_tech  = item.get("d3fend_technique") or item.get("d3fend_id") or ""
            d3f_label = item.get("d3fend_technique_label") or item.get("name") or ""
            d3f_id    = _extract_d3f_id(d3f_tech) if d3f_tech else (d3f_label.replace(" ", "") if d3f_label else "")
            if attack_id and d3f_id:
                entries.append({
                    "mitre_id":    attack_id.strip(),
                    "d3f_id":      d3f_id,
                    "name":        d3f_label or _camel_to_label(d3f_id),
                    "category":    _normalize_category(item.get("d3fend_category") or item.get("category") or ""),
                    "description": str(item.get("description") or "")[:500],
                })
        return entries
    if isinstance(data, dict) and all(k.startswith(("T", "t")) for k in list(data.keys())[:5]):
        for attack_id, measures in data.items():
            if not isinstance(measures, list):
                continue
            for m in measures:
                d3f_id = m.get("d3f_id") or m.get("id") or ""
                if attack_id and d3f_id:
                    entries.append({
                        "mitre_id":    attack_id.strip(),
                        "d3f_id":      d3f_id,
                        "name":        m.get("name") or _camel_to_label(d3f_id),
                        "category":    _normalize_category(m.get("category") or m.get("cat") or ""),
                        "description": str(m.get("description") or "")[:500],
                    })
        return entries
    if isinstance(data, list):
        for item in data:
            attack_id = item.get("attack_id") or item.get("mitre_id") or ""
            d3f_id    = item.get("d3f_id") or item.get("d3fend_id") or ""
            if not d3f_id:
                d3f_id = _extract_d3f_id(item.get("d3fend_technique") or "")
            if attack_id and d3f_id:
                entries.append({
                    "mitre_id":    attack_id.strip(),
                    "d3f_id":      d3f_id,
                    "name":        item.get("name") or _camel_to_label(d3f_id),
                    "category":    _normalize_category(item.get("category") or item.get("d3fend_category") or ""),
                    "description": str(item.get("description") or "")[:500],
                })
        return entries
    return []


# ── Point d'entrée public (upload fichier) ────────────────────────────────────

def parse_d3fend_json(raw: bytes) -> list[dict]:
    """
    Parse un fichier D3FEND (JSON/JSON-LD) uploadé manuellement.
    Supporte : JSON-LD avec may-counter, {mapping: [...]}, {T1059: [...]}, liste plate.
    Note : d3fend.json officiel (ontologie) ne contient pas de mappings ATT&CK.
    """
    data = json.loads(raw)
    if isinstance(data, dict) and "@graph" in data:
        entries = _parse_jsonld(data)
        if entries:
            return entries
        entries = _parse_mapping_format(data)
        if entries:
            return entries
        raise ValueError(
            "Le fichier JSON-LD D3FEND (d3fend.json) est une ontologie de définitions "
            "et ne contient pas les mappings ATT&CK→D3FEND. "
            "Utilisez le bouton '⬇ Importer' pour les synchroniser automatiquement."
        )
    entries = _parse_mapping_format(data)
    if entries:
        return entries
    raise ValueError(
        "Format non reconnu. Formats supportés : {'mapping': [...]}, {'T1059': [...]}, liste plate."
    )


def import_d3fend(raw: bytes, db: Session, filename: str = "") -> dict[str, Any]:
    """Parse et importe un fichier D3FEND uploadé manuellement."""
    entries = parse_d3fend_json(raw)
    if not entries:
        raise ValueError("Aucune entrée valide trouvée dans le fichier.")
    _persist(entries, db, version="imported", source=f"d3fend.mitre.org ({filename or 'fichier'})")
    attack_ids = len({e["mitre_id"] for e in entries})
    return {
        "name":        D3FEND_REF_NAME,
        "entry_count": len(entries),
        "attack_techniques_covered": attack_ids,
        "synced_at":  datetime.utcnow().isoformat(),
    }


def sync_d3fend(db: Session) -> dict[str, Any]:
    """
    Télécharge l'ontologie TTL D3FEND depuis GitHub et génère les mappings ATT&CK→D3FEND
    par croisement sémantique des artefacts numériques.
    """
    try:
        req = urllib.request.Request(
            D3FEND_TTL_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; PurpleLens/1.0)",
                "Accept": "text/turtle, text/plain, */*",
            },
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw_content = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"Impossible de télécharger l'ontologie D3FEND : {exc}") from exc

    entries = _parse_ttl(raw_content)
    if not entries:
        raise ValueError("Aucun mapping ATT&CK→D3FEND extrait de l'ontologie TTL.")

    _persist(entries, db, version="synced", source=D3FEND_JSON_URL)
    attack_ids = len({e["mitre_id"] for e in entries})
    return {
        "name":        D3FEND_REF_NAME,
        "entry_count": len(entries),
        "attack_techniques_covered": attack_ids,
        "synced_at":  datetime.utcnow().isoformat(),
    }


def _persist(entries: list[dict], db: Session, version: str, source: str) -> None:
    db.query(D3fendMapping).delete()
    for e in entries:
        db.add(D3fendMapping(
            mitre_id=e["mitre_id"],
            d3f_id=e["d3f_id"],
            name=e["name"],
            category=e["category"],
            description=e.get("description", ""),
        ))
    now = datetime.utcnow()
    meta = db.query(ReferentialMeta).filter(ReferentialMeta.name == D3FEND_REF_NAME).first()
    if meta is None:
        meta = ReferentialMeta(name=D3FEND_REF_NAME)
        db.add(meta)
    meta.version     = version
    meta.entry_count = len(entries)
    meta.synced_at   = now
    meta.source_url  = source
    db.commit()


def get_d3fend_status(db: Session) -> dict[str, Any]:
    meta         = db.query(ReferentialMeta).filter(ReferentialMeta.name == D3FEND_REF_NAME).first()
    count        = db.query(D3fendMapping).count()
    attack_count = db.query(D3fendMapping.mitre_id).distinct().count()
    return {
        "name":                      D3FEND_REF_NAME,
        "version":                   meta.version if meta else None,
        "entry_count":               count,
        "attack_techniques_covered": attack_count,
        "synced_at":                 meta.synced_at.isoformat() if meta and meta.synced_at else None,
        "source_url":                D3FEND_JSON_URL,
    }


def get_d3fend_for_technique(mitre_id: str, db: Session) -> list[dict]:
    rows = db.query(D3fendMapping).filter(D3fendMapping.mitre_id == mitre_id).all()
    if not rows and "." in mitre_id:
        parent = mitre_id.split(".")[0]
        rows   = db.query(D3fendMapping).filter(D3fendMapping.mitre_id == parent).all()
    return [{"d3f_id": r.d3f_id, "name": r.name, "cat": r.category} for r in rows]
