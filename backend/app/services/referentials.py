"""
Service de synchronisation des référentiels de sécurité.

Télécharge, parse et stocke en base les référentiels OWASP, CWE et CAPEC
depuis leurs sources officielles. Tout le travail réseau se fait ici ;
après sync, PurpleLens fonctionne hors ligne.

Sources :
  OWASP Top 10  — JSON GitHub (OWASP/Top10)
  CWE           — XML zip (cwe.mitre.org)
  CAPEC         — XML zip (capec.mitre.org)
"""

import io
import json
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.referentials import ReferentialEntry, ReferentialMeta

# ── URLs des sources officielles ─────────────────────────────────────────────

SOURCES = {
    "owasp": {
        "url": "https://raw.githubusercontent.com/OWASP/Top10/master/2021/docs/en/index.md",
        "version": "2021",
        "description": "OWASP Top 10 — 10 risques applicatifs critiques (2021)",
    },
    "cwe": {
        "url": "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip",
        "description": "Common Weakness Enumeration (MITRE)",
    },
    "capec": {
        "url": "https://capec.mitre.org/data/xml/capec_latest.xml",
        "description": "Common Attack Pattern Enumeration and Classification (MITRE)",
    },
}

# ── Données OWASP Top 10 (2021) intégrées — fallback si réseau indisponible ──
OWASP_BUILTIN = [
    {"ref_id": "A01:2021", "name": "Broken Access Control",
     "description": "Les restrictions sur ce que les utilisateurs authentifiés peuvent faire ne sont pas correctement appliquées."},
    {"ref_id": "A02:2021", "name": "Cryptographic Failures",
     "description": "Défaillances liées à la cryptographie exposant des données sensibles en transit ou au repos."},
    {"ref_id": "A03:2021", "name": "Injection",
     "description": "SQL, NoSQL, OS, LDAP injection — données non fiables envoyées à un interpréteur."},
    {"ref_id": "A04:2021", "name": "Insecure Design",
     "description": "Risques liés aux défauts de conception et d'architecture de sécurité."},
    {"ref_id": "A05:2021", "name": "Security Misconfiguration",
     "description": "Configurations de sécurité manquantes, incorrectes ou par défaut."},
    {"ref_id": "A06:2021", "name": "Vulnerable and Outdated Components",
     "description": "Utilisation de composants présentant des vulnérabilités connues ou non maintenus."},
    {"ref_id": "A07:2021", "name": "Identification and Authentication Failures",
     "description": "Failles dans la gestion de l'identité, de l'authentification et des sessions."},
    {"ref_id": "A08:2021", "name": "Software and Data Integrity Failures",
     "description": "Code et infrastructure sans vérification d'intégrité — mises à jour non sécurisées."},
    {"ref_id": "A09:2021", "name": "Security Logging and Monitoring Failures",
     "description": "Journalisation et surveillance insuffisantes pour détecter et réagir aux incidents."},
    {"ref_id": "A10:2021", "name": "Server-Side Request Forgery",
     "description": "Requêtes côté serveur forgées vers des ressources internes ou arbitraires."},
]


# ── Helpers réseau ────────────────────────────────────────────────────────────

def _fetch_bytes(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PurpleLens/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _fetch_text(url: str, timeout: int = 30) -> str:
    return _fetch_bytes(url, timeout).decode("utf-8", errors="replace")


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_owasp() -> list[dict]:
    """Retourne les 10 entrées OWASP. Utilise toujours les données intégrées
    (la liste Top 10 change tous les ~4 ans, inutile de parser le Markdown)."""
    return OWASP_BUILTIN


def _parse_cwe(data: bytes) -> tuple[str, list[dict]]:
    """Extrait id, nom et description depuis le ZIP XML CWE de MITRE."""
    entries = []
    version = ""

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml_name = next(n for n in z.namelist() if n.endswith(".xml"))
        xml_bytes = z.read(xml_name)

    root = ET.fromstring(xml_bytes)
    ns = {"cwe": "http://cwe.mitre.org/cwe-7"}

    # Version depuis l'attribut racine
    version = root.attrib.get("Version", "")

    weaknesses = root.find("cwe:Weaknesses", ns)
    if weaknesses is None:
        return version, entries

    for w in weaknesses.findall("cwe:Weakness", ns):
        wid = w.attrib.get("ID", "")
        name = w.attrib.get("Name", "")

        desc_el = w.find("cwe:Description", ns)
        description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

        if wid and name:
            entries.append({
                "ref_id": f"CWE-{wid}",
                "name": name,
                "description": description[:500],
            })

    return version, entries


def _parse_capec(data: bytes) -> tuple[str, list[dict]]:
    """Extrait id, nom et description depuis le XML CAPEC de MITRE."""
    entries = []
    version = ""

    root = ET.fromstring(data)
    ns = {"capec": "http://capec.mitre.org/capec-3"}

    version = root.attrib.get("Version", "")

    patterns = root.find("capec:Attack_Patterns", ns)
    if patterns is None:
        return version, entries

    for p in patterns.findall("capec:Attack_Pattern", ns):
        pid = p.attrib.get("ID", "")
        name = p.attrib.get("Name", "")

        desc_el = p.find("capec:Description", ns)
        description = ""
        if desc_el is not None:
            description = "".join(desc_el.itertext()).strip()[:500]

        if pid and name:
            entries.append({
                "ref_id": f"CAPEC-{pid}",
                "name": name,
                "description": description,
            })

    return version, entries


# ── Fonction principale de sync ───────────────────────────────────────────────

def sync_referential(name: str, db: Session) -> dict[str, Any]:
    """
    Synchronise un référentiel depuis sa source officielle et le stocke en base.

    Retourne un dict { version, entry_count, synced_at, source }.
    Lève une exception en cas d'erreur réseau ou de parsing.
    """
    if name not in SOURCES:
        raise ValueError(f"Référentiel inconnu : {name}")

    source = SOURCES[name]
    url = source["url"]
    entries: list[dict] = []
    version: str = source.get("version", "")

    if name == "owasp":
        entries = _parse_owasp()
        version = "2021"

    elif name == "cwe":
        raw = _fetch_bytes(url)
        version, entries = _parse_cwe(raw)

    elif name == "capec":
        raw = _fetch_bytes(url)
        version, entries = _parse_capec(raw)

    # ── Remplace toutes les entrées du référentiel en base ────────────────
    db.query(ReferentialEntry).filter(ReferentialEntry.referential == name).delete()

    for e in entries:
        db.add(ReferentialEntry(
            referential=name,
            ref_id=e["ref_id"],
            name=e["name"],
            description=e.get("description", ""),
        ))

    # ── Met à jour les métadonnées ────────────────────────────────────────
    meta = db.query(ReferentialMeta).filter(ReferentialMeta.name == name).first()
    now = datetime.utcnow()
    if meta is None:
        meta = ReferentialMeta(name=name)
        db.add(meta)

    meta.version = version
    meta.entry_count = len(entries)
    meta.synced_at = now
    meta.source_url = url

    db.commit()

    return {
        "name": name,
        "version": version,
        "entry_count": len(entries),
        "synced_at": now.isoformat(),
        "source_url": url,
    }


def get_status(db: Session) -> list[dict[str, Any]]:
    """Retourne le statut de tous les référentiels (même non encore synchronisés)."""
    result = []
    for name in ("owasp", "cwe", "capec"):
        meta = db.query(ReferentialMeta).filter(ReferentialMeta.name == name).first()
        if meta:
            result.append({
                "name": name,
                "version": meta.version,
                "entry_count": meta.entry_count,
                "synced_at": meta.synced_at.isoformat() if meta.synced_at else None,
                "source_url": meta.source_url,
            })
        else:
            result.append({
                "name": name,
                "version": None,
                "entry_count": 0,
                "synced_at": None,
                "source_url": SOURCES[name]["url"],
            })
    return result


def search_entries(referential: str, query: str, db: Session, limit: int = 15) -> list[dict]:
    """Recherche dans les entrées d'un référentiel stockées en base."""
    from sqlalchemy import or_
    q = f"%{query.lower()}%"
    rows = (
        db.query(ReferentialEntry)
        .filter(
            ReferentialEntry.referential == referential,
            or_(
                ReferentialEntry.ref_id.ilike(q),
                ReferentialEntry.name.ilike(q),
                ReferentialEntry.description.ilike(q),
            ),
        )
        .limit(limit)
        .all()
    )
    return [{"ref_id": r.ref_id, "name": r.name, "description": r.description} for r in rows]
