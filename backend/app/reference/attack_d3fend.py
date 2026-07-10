"""Correspondance ATT&CK -> D3FEND (suggestion automatique de contre-mesures).

Portée honnête (même esprit que reference/catalogs.py) : ceci n'est PAS la
correspondance officielle MITRE (qui est bien plus fine et couvre plusieurs milliers de
paires technique/contre-mesure sur 6 tactiques D3FEND — Harden/Detect/Isolate/Deceive/
Evict/Restore). Le socle embarqué ne compte que 10 techniques D3FEND, toutes de la
tactique Detect, donc les suggestions ci-dessous restent volontairement ciblées sur la
détection — pas une contre-mesure clé en main, ni une couverture Harden/Isolate/Deceive/
Evict/Restore. À affiner quand le catalogue D3FEND complet est synchronisé (reference/sync.py).

Utilisé par : /api/reference/d3fend/suggest, et par le calcul serveur automatique du
champ `d3fend` des Vulnérabilités et Scénarios (cahier « constats » — le client ne
choisit plus les contre-mesures à la main, elles sont dérivées des techniques ATT&CK).
"""
from __future__ import annotations

# ext_id ATT&CK -> liste d'ext_id D3FEND suggérés (socle embarqué, cf. reference/catalogs.py).
ATTACK_TO_D3FEND: dict[str, list[str]] = {
    # Reconnaissance / resource-development : peu de télémétrie interne pertinente ici.
    "T1595": ["D3-NTA"],
    "T1592": ["D3-NTA"],
    "T1583": ["D3-NTA"],
    # Initial access.
    "T1566": ["D3-FA", "D3-ELA"],
    "T1566.001": ["D3-ELA", "D3-UBA"],  # pièce jointe piégée : lien/pièce jointe + comportement post-clic
    "T1190": ["D3-NTA", "D3-PA"],
    "T1078": ["D3-PA", "D3-UBA"],
    # Execution.
    "T1059": ["D3-PA", "D3-PSA"],
    "T1059.001": ["D3-SEA"],  # PowerShell : analyse d'exécution de script
    "T1204": ["D3-FA", "D3-PA"],
    "T1053": ["D3-PSA"],
    # Persistence.
    "T1547": ["D3-PSA", "D3-FA"],
    "T1136": ["D3-PA"],
    "T1543": ["D3-PSA"],
    # Privilege escalation.
    "T1548": ["D3-PA"],
    "T1068": ["D3-PA"],
    "T1055": ["D3-PCSV"],  # injection de processus : vérification d'intégrité du segment de code
    # Defense evasion.
    "T1070": ["D3-FA"],
    "T1027": ["D3-FA"],
    "T1562": ["D3-PA"],
    # Credential access.
    "T1110": ["D3-NTA"],
    "T1003": ["D3-PA"],
    "T1056": ["D3-PA"],
    # Discovery.
    "T1087": ["D3-PA"],
    "T1082": ["D3-PA"],
    "T1046": ["D3-NTA"],
    # Lateral movement.
    "T1021": ["D3-NTA"],
    "T1570": ["D3-NTA", "D3-FA"],
    # Collection.
    "T1560": ["D3-FA"],
    "T1005": ["D3-FA"],
    # Command and control.
    "T1071": ["D3-NTA", "D3-DNSTA"],
    "T1071.001": ["D3-NTA", "D3-PMAD"],  # C2 sur HTTPS : trafic + anomalies de métadonnées de protocole
    "T1105": ["D3-NTA", "D3-FA"],
    # Exfiltration.
    "T1041": ["D3-NTA"],
    "T1567": ["D3-NTA", "D3-DNSTA"],
    # Impact.
    "T1486": ["D3-PA", "D3-FA"],
    "T1490": ["D3-PA"],
    "T1498": ["D3-NTA"],
}


def suggest_d3fend(technique_ext_ids: list[str]) -> list[str]:
    """Contre-mesures D3FEND suggérées (dédupliquées, ordre stable) pour un ensemble
    de techniques ATT&CK. Technique inconnue de la table -> ignorée silencieusement
    (pas d'erreur : le socle est partiel par construction)."""
    out: list[str] = []
    for t in technique_ext_ids or []:
        for d in ATTACK_TO_D3FEND.get(str(t).upper(), []):
            if d not in out:
                out.append(d)
    return out
