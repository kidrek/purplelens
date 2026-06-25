"""
Service de synchronisation du catalogue MITRE ATT&CK Enterprise.

Source : dépôt STIX officiel MITRE/CTI sur GitHub
  https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json

Le fichier STIX 2.0 contient l'ensemble des objets ATT&CK : techniques,
sous-techniques, tactiques, groupes, logiciels... On ne retient que les
objets de type "attack-pattern" non dépréciés.

Après synchronisation, le catalogue est disponible hors ligne en base.
Il sert de dénominateur au KPI de couverture ATT&CK par application :
  catalog_coverage_pct = techniques_testées / total_catalogue
"""

import json
import urllib.request
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.mitre_catalog import MitreTechnique
from app.models.referentials import ReferentialMeta

MITRE_STIX_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/"
    "enterprise-attack/enterprise-attack.json"
)

MITRE_REF_NAME = "mitre_attack"


def _fetch_bytes(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PurpleLens/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _extract_tactic(obj: dict) -> str:
    """Extrait la première tactique depuis kill_chain_phases."""
    phases = obj.get("kill_chain_phases", [])
    for phase in phases:
        if phase.get("kill_chain_name") == "mitre-attack":
            # ex. "initial-access" → "Initial Access"
            return phase.get("phase_name", "").replace("-", " ").title()
    return ""


def _parse_stix(data: bytes) -> tuple[str, list[dict]]:
    """Parse le bundle STIX ATT&CK et retourne (version, [entrées])."""
    bundle = json.loads(data)
    objects = bundle.get("objects", [])

    # Récupère la version depuis l'objet x-mitre-collection ou identity
    version = ""
    for obj in objects:
        if obj.get("type") == "x-mitre-collection":
            version = obj.get("x_mitre_version", "")
            break
    if not version:
        # fallback : cherche dans le premier attack-pattern
        for obj in objects:
            if obj.get("type") == "attack-pattern":
                version = obj.get("x_mitre_version", "")
                break

    entries = []
    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue

        # Ignore les objets dépréciés ou révoqués
        if obj.get("x_mitre_deprecated", False) or obj.get("revoked", False):
            continue

        # Identifiant ATT&CK (ex. T1566, T1566.001)
        ext_refs = obj.get("external_references", [])
        mitre_id = ""
        for ref in ext_refs:
            if ref.get("source_name") == "mitre-attack":
                mitre_id = ref.get("external_id", "")
                break
        if not mitre_id:
            continue

        is_sub = obj.get("x_mitre_is_subtechnique", False)
        tactic = _extract_tactic(obj)
        description = obj.get("description", "")[:500]
        name = obj.get("name", "")

        entries.append({
            "mitre_id": mitre_id,
            "name": name,
            "tactic": tactic,
            "description": description,
            "is_subtechnique": is_sub,
            "is_deprecated": False,
        })

    # Tri par identifiant pour cohérence
    entries.sort(key=lambda e: e["mitre_id"])
    return version, entries


def sync_mitre_catalog(db: Session) -> dict[str, Any]:
    """
    Télécharge et importe le catalogue ATT&CK Enterprise depuis MITRE/CTI.
    Remplace toutes les entrées existantes.
    Retourne les métadonnées de la sync.
    """
    raw = _fetch_bytes(MITRE_STIX_URL)
    version, entries = _parse_stix(raw)

    # Remplace le catalogue en base
    db.query(MitreTechnique).delete()
    for e in entries:
        db.add(MitreTechnique(**e))

    # Métadonnées
    now = datetime.utcnow()
    meta = db.query(ReferentialMeta).filter(ReferentialMeta.name == MITRE_REF_NAME).first()
    if meta is None:
        meta = ReferentialMeta(name=MITRE_REF_NAME)
        db.add(meta)
    meta.version = version
    meta.entry_count = len(entries)
    meta.synced_at = now
    meta.source_url = MITRE_STIX_URL

    db.commit()

    return {
        "name": MITRE_REF_NAME,
        "version": version,
        "entry_count": len(entries),
        "synced_at": now.isoformat(),
        "source_url": MITRE_STIX_URL,
    }


def get_mitre_status(db: Session) -> dict[str, Any]:
    """Retourne le statut du catalogue ATT&CK en base."""
    meta = db.query(ReferentialMeta).filter(ReferentialMeta.name == MITRE_REF_NAME).first()
    total = db.query(MitreTechnique).count()
    parent_count = db.query(MitreTechnique).filter(
        MitreTechnique.is_subtechnique == False  # noqa: E712
    ).count()

    if meta:
        return {
            "name": MITRE_REF_NAME,
            "version": meta.version,
            "entry_count": total,
            "parent_count": parent_count,
            "synced_at": meta.synced_at.isoformat() if meta.synced_at else None,
            "source_url": meta.source_url,
        }
    return {
        "name": MITRE_REF_NAME,
        "version": None,
        "entry_count": 0,
        "parent_count": 0,
        "synced_at": None,
        "source_url": MITRE_STIX_URL,
    }


def get_catalog_size(db: Session, include_subtechniques: bool = False) -> int:
    """Retourne le nombre de techniques dans le catalogue (dénominateur KPI)."""
    q = db.query(MitreTechnique)
    if not include_subtechniques:
        q = q.filter(MitreTechnique.is_subtechnique == False)  # noqa: E712
    return q.count()
