"""Catalogues de référence de sécurité embarqués et leur import en base.

Ces catalogues sont un socle de base, versionné avec le produit (fonctionne hors-ligne).
Ils peuplent les tables `ref_*` utilisées par les formulaires et l'analytique. L'import
est idempotent (clé naturelle `ext_id`, ON CONFLICT DO UPDATE) — d'où la migration 0002
qui garantit l'unicité d'`ext_id`.

Portée honnête : OWASP Top 10 (2021) et CWE Top 25 (2023) sont complets ; ATT&CK,
D3FEND et CAPEC sont des sous-ensembles courants (un socle), pas les catalogues MITRE
intégraux. Une synchronisation en ligne depuis les sources amont reste une évolution.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ── Métadonnées des catalogues (ordre d'affichage = ordre ici) ──────────────
# group : regroupement d'affichage (vuln | attack | d3fend)
# table : table cible ; has_tactic : la table porte une colonne `tactic`
CATALOGS: list[dict[str, Any]] = [
    {"id": "owasp", "group": "vuln", "badge": "OWASP", "tone": "amber",
     "table": "ref_owasp", "has_tactic": False, "source": "owasp.org"},
    {"id": "cwe", "group": "vuln", "badge": "CWE", "tone": "cyan",
     "table": "ref_cwe", "has_tactic": False, "source": "cwe.mitre.org"},
    {"id": "capec", "group": "vuln", "badge": "CAPEC", "tone": "violet",
     "table": "ref_capec", "has_tactic": False, "source": "capec.mitre.org"},
    {"id": "attack", "group": "attack", "badge": "ATT&CK", "tone": "red",
     "table": "ref_attack_technique", "has_tactic": True, "source": "attack.mitre.org"},
    {"id": "d3fend", "group": "d3fend", "badge": "D3FEND", "tone": "green",
     "table": "ref_d3fend", "has_tactic": False, "has_category": True, "source": "d3fend.mitre.org"},
    # Acteurs de la menace — le `data` JSONB porte aliases + techniques ATT&CK connues.
    {"id": "attack_groups", "group": "attack", "badge": "ATT&CK Groups", "tone": "red",
     "table": "ref_attack_group", "has_tactic": False, "has_data": True, "source": "attack.mitre.org"},
    {"id": "misp_actors", "group": "attack", "badge": "MISP Actors", "tone": "amber",
     "table": "ref_misp_actor", "has_tactic": False, "has_data": True, "source": "misp-galaxy"},
]
_BY_ID = {c["id"]: c for c in CATALOGS}

# ── Données embarquées ──────────────────────────────────────────────────────
_OWASP = [
    ("A01:2021", "Broken Access Control"),
    ("A02:2021", "Cryptographic Failures"),
    ("A03:2021", "Injection"),
    ("A04:2021", "Insecure Design"),
    ("A05:2021", "Security Misconfiguration"),
    ("A06:2021", "Vulnerable and Outdated Components"),
    ("A07:2021", "Identification and Authentication Failures"),
    ("A08:2021", "Software and Data Integrity Failures"),
    ("A09:2021", "Security Logging and Monitoring Failures"),
    ("A10:2021", "Server-Side Request Forgery (SSRF)"),
]

_CWE = [
    ("CWE-787", "Out-of-bounds Write"),
    ("CWE-79", "Cross-site Scripting (XSS)"),
    ("CWE-89", "SQL Injection"),
    ("CWE-416", "Use After Free"),
    ("CWE-78", "OS Command Injection"),
    ("CWE-20", "Improper Input Validation"),
    ("CWE-125", "Out-of-bounds Read"),
    ("CWE-22", "Path Traversal"),
    ("CWE-352", "Cross-Site Request Forgery (CSRF)"),
    ("CWE-434", "Unrestricted Upload of File with Dangerous Type"),
    ("CWE-862", "Missing Authorization"),
    ("CWE-476", "NULL Pointer Dereference"),
    ("CWE-287", "Improper Authentication"),
    ("CWE-190", "Integer Overflow or Wraparound"),
    ("CWE-502", "Deserialization of Untrusted Data"),
    ("CWE-77", "Command Injection"),
    ("CWE-119", "Improper Restriction of Operations within the Bounds of a Memory Buffer"),
    ("CWE-798", "Use of Hard-coded Credentials"),
    ("CWE-918", "Server-Side Request Forgery (SSRF)"),
    ("CWE-306", "Missing Authentication for Critical Function"),
    ("CWE-362", "Race Condition"),
    ("CWE-269", "Improper Privilege Management"),
    ("CWE-94", "Code Injection"),
    ("CWE-863", "Incorrect Authorization"),
    ("CWE-276", "Incorrect Default Permissions"),
]

_CAPEC = [
    ("CAPEC-66", "SQL Injection"),
    ("CAPEC-63", "Cross-Site Scripting (XSS)"),
    ("CAPEC-88", "OS Command Injection"),
    ("CAPEC-98", "Phishing"),
    ("CAPEC-114", "Authentication Abuse"),
    ("CAPEC-115", "Authentication Bypass"),
    ("CAPEC-122", "Privilege Abuse"),
    ("CAPEC-125", "Flooding"),
    ("CAPEC-242", "Code Injection"),
    ("CAPEC-310", "Scanning for Vulnerable Software"),
]

# ATT&CK Enterprise — socle curé, une technique par couverture de tactique.
_ATTACK = [
    ("T1595", "Active Scanning", "reconnaissance"),
    ("T1592", "Gather Victim Host Information", "reconnaissance"),
    ("T1583", "Acquire Infrastructure", "resource-development"),
    ("T1566", "Phishing", "initial-access"),
    ("T1566.001", "Spearphishing Attachment", "initial-access"),
    ("T1190", "Exploit Public-Facing Application", "initial-access"),
    ("T1078", "Valid Accounts", "initial-access"),
    ("T1059", "Command and Scripting Interpreter", "execution"),
    ("T1059.001", "PowerShell", "execution"),
    ("T1204", "User Execution", "execution"),
    ("T1053", "Scheduled Task/Job", "execution"),
    ("T1547", "Boot or Logon Autostart Execution", "persistence"),
    ("T1136", "Create Account", "persistence"),
    ("T1543", "Create or Modify System Process", "persistence"),
    ("T1548", "Abuse Elevation Control Mechanism", "privilege-escalation"),
    ("T1068", "Exploitation for Privilege Escalation", "privilege-escalation"),
    ("T1055", "Process Injection", "privilege-escalation"),
    ("T1070", "Indicator Removal", "defense-evasion"),
    ("T1027", "Obfuscated Files or Information", "defense-evasion"),
    ("T1562", "Impair Defenses", "defense-evasion"),
    ("T1110", "Brute Force", "credential-access"),
    ("T1003", "OS Credential Dumping", "credential-access"),
    ("T1056", "Input Capture", "credential-access"),
    ("T1087", "Account Discovery", "discovery"),
    ("T1082", "System Information Discovery", "discovery"),
    ("T1046", "Network Service Discovery", "discovery"),
    ("T1021", "Remote Services", "lateral-movement"),
    ("T1570", "Lateral Tool Transfer", "lateral-movement"),
    ("T1560", "Archive Collected Data", "collection"),
    ("T1005", "Data from Local System", "collection"),
    ("T1071", "Application Layer Protocol", "command-and-control"),
    ("T1071.001", "Web Protocols", "command-and-control"),
    ("T1105", "Ingress Tool Transfer", "command-and-control"),
    ("T1041", "Exfiltration Over C2 Channel", "exfiltration"),
    ("T1567", "Exfiltration Over Web Service", "exfiltration"),
    ("T1486", "Data Encrypted for Impact", "impact"),
    ("T1490", "Inhibit System Recovery", "impact"),
    ("T1498", "Network Denial of Service", "impact"),
]

# Socle D3FEND — toutes de la tactique Detect (le socle embarqué ne couvre pas encore
# Harden/Isolate/Deceive/Evict/Restore). Portée honnête : sous-ensemble curé, pas le
# catalogue D3FEND officiel complet (~200 techniques).
_D3FEND = [
    ("D3-NTA", "Network Traffic Analysis", "Detect"),
    ("D3-FA", "File Analysis", "Detect"),
    ("D3-PA", "Process Analysis", "Detect"),
    ("D3-DNSTA", "DNS Traffic Analysis", "Detect"),
    ("D3-PSA", "Process Spawn Analysis", "Detect"),
    ("D3-ELA", "Email Link Analysis", "Detect"),
    ("D3-UBA", "User Behavior Analysis", "Detect"),
    ("D3-SEA", "Script Execution Analysis", "Detect"),
    ("D3-PCSV", "Process Code Segment Verification", "Detect"),
    ("D3-PMAD", "Protocol Metadata Anomaly Detection", "Detect"),
]

# Acteurs de la menace — socle embarqué (offline-first). Format : (ext_id, nom officiel,
# alias/synonymes, techniques). Les techniques sont volontairement restreintes aux ext_id
# présents dans `_ATTACK` ci-dessus pour rester cohérentes hors-ligne (la synchro en ligne
# apporte la couverture complète depuis les relations `uses` du bundle enterprise-attack).
_ATTACK_GROUPS = [
    ("G0016", "APT29", ["Cozy Bear", "The Dukes", "Nobelium", "Midnight Blizzard"],
     ["T1566", "T1566.001", "T1078", "T1059", "T1059.001", "T1027", "T1071.001", "T1105", "T1003"]),
    ("G0046", "FIN7", ["Carbon Spider", "Carbanak", "Sangria Tempest"],
     ["T1566", "T1204", "T1059", "T1053", "T1547", "T1005", "T1105", "T1027"]),
    ("G0007", "APT28", ["Fancy Bear", "Sofacy", "Sednit", "Forest Blizzard"],
     ["T1595", "T1566", "T1078", "T1059", "T1110", "T1003", "T1071", "T1041"]),
]

# MISP Galaxy threat-actor — socle. Mêmes techniques restreintes au socle `_ATTACK`.
# Les alias permettent la fusion/dédup avec les groupes MITRE (ex. « Cozy Bear » ⇄ APT29).
_MISP_ACTORS = [
    ("misp-cozy-bear", "Cozy Bear", ["APT29", "The Dukes", "Nobelium"],
     ["T1566", "T1059", "T1078"]),
    ("misp-carbanak", "Carbanak", ["FIN7", "Carbon Spider", "Anunak"],
     ["T1566", "T1204", "T1059", "T1105"]),
    ("misp-lazarus", "Lazarus Group", ["Hidden Cobra", "APT38", "Zinc"],
     ["T1566", "T1059", "T1105", "T1486"]),
]

_DATA = {
    "owasp": _OWASP, "cwe": _CWE, "capec": _CAPEC,
    "attack": _ATTACK, "d3fend": _D3FEND,
    "attack_groups": _ATTACK_GROUPS, "misp_actors": _MISP_ACTORS,
}


async def import_catalog(session: AsyncSession, cid: str) -> int:
    """Charge/actualise un catalogue en base (idempotent). Retourne le nb d'entrées
    du catalogue embarqué. Nécessite la session posée en contexte de service."""
    cat = _BY_ID.get(cid)
    if cat is None:
        raise KeyError(cid)
    rows = _DATA[cid]
    table = cat["table"]
    if cat["has_tactic"]:
        # Le socle est mono-tactique ; on l'écrit sous forme de liste `data.tactics`
        # (même schéma que la synchro en ligne multi-tactiques) pour un affichage uniforme.
        for ext_id, name, tactic in rows:
            await session.execute(text(
                f"INSERT INTO {table} (id, ext_id, name, tactic, data) "
                "VALUES (gen_random_uuid(), :e, :n, :t, CAST(:d AS jsonb)) "
                "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, "
                "tactic = EXCLUDED.tactic, data = EXCLUDED.data, updated_at = now()"
            ), {"e": ext_id, "n": name, "t": tactic,
                "d": json.dumps({"tactics": [tactic] if tactic else []})})
    elif cat.get("has_category"):
        for ext_id, name, category in rows:
            await session.execute(text(
                f"INSERT INTO {table} (id, ext_id, name, category, data) "
                "VALUES (gen_random_uuid(), :e, :n, :c, '{}') "
                "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, "
                "category = EXCLUDED.category, updated_at = now()"
            ), {"e": ext_id, "n": name, "c": category})
    elif cat.get("has_data"):
        # Acteurs de la menace : le socle porte (ext_id, nom, alias, techniques) → data JSONB.
        for ext_id, name, aliases, techniques in rows:
            await session.execute(text(
                f"INSERT INTO {table} (id, ext_id, name, data) "
                "VALUES (gen_random_uuid(), :e, :n, CAST(:d AS jsonb)) "
                "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, "
                "data = EXCLUDED.data, updated_at = now()"
            ), {"e": ext_id, "n": name, "d": json.dumps(
                {"aliases": list(aliases), "techniques": list(techniques), "source": cat["source"]})})
    else:
        for ext_id, name in rows:
            await session.execute(text(
                f"INSERT INTO {table} (id, ext_id, name, data) "
                "VALUES (gen_random_uuid(), :e, :n, '{}') "
                "ON CONFLICT (ext_id) DO UPDATE SET name = EXCLUDED.name, "
                "updated_at = now()"
            ), {"e": ext_id, "n": name})
    return len(rows)


async def catalog_stats(session: AsyncSession) -> list[dict[str, Any]]:
    """État de chaque catalogue : nb d'entrées en base, dernière mise à jour,
    et nb d'entrées disponibles dans le socle embarqué."""
    out: list[dict[str, Any]] = []
    for cat in CATALOGS:
        row = (await session.execute(text(
            f"SELECT count(*) AS n, max(updated_at) AS upd FROM {cat['table']}"
        ))).first()
        count = row.n if row else 0
        out.append({
            "id": cat["id"], "group": cat["group"], "badge": cat["badge"],
            "tone": cat["tone"], "source": cat["source"],
            "count": count, "available": len(_DATA[cat["id"]]),
            "updated_at": row.upd.isoformat() if row and row.upd else None,
            "imported": count > 0,
        })
    return out
