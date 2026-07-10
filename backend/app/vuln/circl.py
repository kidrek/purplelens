"""Enrichissement CVE via CIRCL Vulnerability-Lookup (cahier §6, A.1/A.2).

À la saisie d'un CVE, on interroge une instance Vulnerability-Lookup (défaut public
`vulnerability.circl.lu`, surchargeable vers une instance auto-hébergée ou GCVE pour les
engagements sensibles — l'instance publique journalise les requêtes). On met en cache sur
le finding : CVSS (3.1/4.0 + vecteur), CWE, CAPEC, description, produits, références, et —
quand disponibles — EPSS/KEV. Rien de global n'est stocké : le volume reste proportionnel
aux findings.

Parsing DÉFENSIF : le format agrégé de vulnerability-lookup varie selon les sources
(cvelistv5, fkie_nvd, vulnrichment…) et diffère de l'ancien cve-search plat. On extrait ce
qu'on peut, on ignore le reste, on n'échoue jamais sur une clé absente.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class EnrichmentUnavailable(Exception):
    """Source injoignable / indisponible → enrichissement différé (hors-ligne)."""


async def fetch_cve(cve_id: str, base_url: str | None = None, timeout: float | None = None) -> dict:
    """Récupère le document brut d'un CVE. Lève EnrichmentUnavailable si indisponible."""
    base = (base_url or settings.enrichment_base_url).rstrip("/")
    url = f"{base}/api/vulnerability/{cve_id}"
    try:
        async with httpx.AsyncClient(timeout=timeout or settings.enrichment_timeout_seconds) as c:
            r = await c.get(url, headers={"Accept": "application/json"})
    except (httpx.HTTPError, OSError) as exc:  # réseau, DNS, TLS, timeout…
        raise EnrichmentUnavailable(str(exc)) from exc
    if r.status_code == 404:
        return {}  # CVE inconnu de la source (pas une erreur réseau)
    if r.status_code >= 400:
        raise EnrichmentUnavailable(f"HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError as exc:
        raise EnrichmentUnavailable("réponse non-JSON") from exc


async def fetch_epss(cve_id: str, base_url: str | None = None, timeout: float | None = None) -> dict:
    """Score EPSS depuis l'endpoint dédié de CIRCL (domaine distinct de la source
    principale — cf. réponse type `{"data": [{"cve", "epss", "percentile", "date"}]}`).
    Retourne {} si le CVE est inconnu de cette source (pas une erreur en soi) ;
    lève EnrichmentUnavailable seulement si la source elle-même est injoignable."""
    base = (base_url or settings.enrichment_epss_url).rstrip("/")
    url = f"{base}/api/epss/{cve_id.lower()}"
    try:
        async with httpx.AsyncClient(timeout=timeout or settings.enrichment_timeout_seconds) as c:
            r = await c.get(url, headers={"Accept": "application/json"})
    except (httpx.HTTPError, OSError) as exc:
        raise EnrichmentUnavailable(str(exc)) from exc
    if r.status_code >= 400:
        raise EnrichmentUnavailable(f"HTTP {r.status_code}")
    try:
        doc = r.json()
    except ValueError as exc:
        raise EnrichmentUnavailable("réponse non-JSON") from exc
    rows = doc.get("data") if isinstance(doc, dict) else None
    if not isinstance(rows, list) or not rows:
        return {}
    return rows[0] if isinstance(rows[0], dict) else {}


def parse_epss_row(row: dict) -> tuple[float | None, float | None]:
    """Convertit la ligne EPSS (chaînes) en (score, percentile) flottants."""
    try:
        score = float(row["epss"]) if row.get("epss") is not None else None
    except (TypeError, ValueError):
        score = None
    try:
        pct = float(row["percentile"]) if row.get("percentile") is not None else None
    except (TypeError, ValueError):
        pct = None
    return (score, pct)


# ── Parsing défensif ────────────────────────────────────────────────────────
def _first_str(*vals: Any) -> str | None:
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v
    return None


def _walk(obj: Any):
    """Parcours récursif (dicts et listes) pour repérer des métriques CVSS enfouies."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _extract_cvss(raw: Any) -> tuple[float | None, str | None, str | None]:
    """Meilleur CVSS trouvé : (score, version, vecteur). Priorité 4.0 > 3.1 > 3.0."""
    best = None  # (rank, score, version, vector)
    for node in _walk(raw):
        for key, ver in (("cvssV4_0", "4.0"), ("cvssV3_1", "3.1"), ("cvssV3_0", "3.0"), ("cvssV3", "3.x")):
            m = node.get(key) if isinstance(node, dict) else None
            if isinstance(m, dict):
                score = m.get("baseScore")
                vec = _first_str(m.get("vectorString"))
                if isinstance(score, (int, float)):
                    rank = {"4.0": 4, "3.1": 3, "3.0": 2, "3.x": 1}[ver]
                    if best is None or rank > best[0]:
                        best = (rank, float(score), ver, vec)
        # Format plat cve-search : "cvss" + "cvss-vector"
        if isinstance(node, dict) and isinstance(node.get("cvss"), (int, float)) and best is None:
            best = (0, float(node["cvss"]), node.get("cvss-version", "3.x"), _first_str(node.get("cvss-vector")))
    if best is None:
        return (None, None, None)
    return (best[1], best[2], best[3])


def _extract_cwe(raw: Any) -> str | None:
    for node in _walk(raw):
        if not isinstance(node, dict):
            continue
        # cvelistv5 : problemTypes[].descriptions[].cweId
        cid = node.get("cweId")
        if isinstance(cid, str) and cid.upper().startswith("CWE-"):
            return cid.upper()
        # cve-search plat : "cwe": "CWE-79"
        c = node.get("cwe")
        if isinstance(c, str) and c.upper().startswith("CWE-"):
            return c.upper()
    return None


def _extract_description(raw: Any) -> str | None:
    for node in _walk(raw):
        if not isinstance(node, dict):
            continue
        # cvelistv5 : descriptions[] {lang,value}
        descs = node.get("descriptions")
        if isinstance(descs, list):
            en = next((d.get("value") for d in descs
                       if isinstance(d, dict) and str(d.get("lang", "")).startswith("en")), None)
            if _first_str(en):
                return en
        s = _first_str(node.get("summary"))  # cve-search plat
        if s:
            return s
    return None


def _extract_references(raw: Any) -> list[str]:
    urls: list[str] = []
    for node in _walk(raw):
        if isinstance(node, dict):
            refs = node.get("references")
            if isinstance(refs, list):
                for r in refs:
                    u = r.get("url") if isinstance(r, dict) else (r if isinstance(r, str) else None)
                    if isinstance(u, str) and u.startswith("http") and u not in urls:
                        urls.append(u)
    return urls[:20]


def _extract_capec(raw: Any) -> list[str]:
    out: list[str] = []
    for node in _walk(raw):
        if isinstance(node, dict):
            cap = node.get("capec")
            if isinstance(cap, list):
                for c in cap:
                    cid = c.get("id") if isinstance(c, dict) else c
                    if cid is not None:
                        s = f"CAPEC-{cid}" if not str(cid).upper().startswith("CAPEC") else str(cid)
                        if s not in out:
                            out.append(s)
    return out[:20]


def _extract_products(raw: Any) -> list[str]:
    out: list[str] = []
    for node in _walk(raw):
        if isinstance(node, dict):
            aff = node.get("affected")
            if isinstance(aff, list):
                for a in aff:
                    if isinstance(a, dict):
                        vendor = _first_str(a.get("vendor"))
                        product = _first_str(a.get("product"))
                        label = " ".join(x for x in (vendor, product) if x)
                        if label and label not in out:
                            out.append(label)
    return out[:20]


def _extract_cpes(raw: Any) -> list[str]:
    """Identifiants CPE 2.3 (rapprochement avec l'inventaire d'applications)."""
    out: list[str] = []
    for node in _walk(raw):
        if isinstance(node, dict):
            cpes = node.get("cpes")
            if isinstance(cpes, list):
                for c in cpes:
                    if isinstance(c, str) and c.startswith("cpe:") and c not in out:
                        out.append(c)
    return out[:20]


def _extract_epss(raw: Any) -> tuple[float | None, float | None]:
    for node in _walk(raw):
        if isinstance(node, dict) and ("epss" in node or "percentile" in node):
            score = node.get("epss")
            pct = node.get("percentile")
            try:
                score = float(score) if score is not None else None
                pct = float(pct) if pct is not None else None
            except (TypeError, ValueError):
                score, pct = None, None
            if score is not None:
                return (score, pct)
    return (None, None)


def _extract_kev(raw: Any) -> tuple[bool, bool]:
    kev = False
    ransom = False
    for node in _walk(raw):
        if isinstance(node, dict):
            if node.get("cisa_kev") or node.get("knownExploited") is True or node.get("kev") is True:
                kev = True
            # Marqueur rançongiciel : peut être imbriqué (cisa_kev.knownRansomwareCampaignUse).
            if node.get("knownRansomwareCampaignUse") in (True, "Known") or node.get("kev_ransomware") is True:
                ransom = True
    return (kev, ransom and kev)


def parse_circl(raw: dict) -> dict:
    """Extrait les champs exploitables d'un document Vulnerability-Lookup (best-effort)."""
    if not raw:
        return {"found": False}
    score, version, vector = _extract_cvss(raw)
    epss, epss_pct = _extract_epss(raw)
    kev, kev_ransom = _extract_kev(raw)
    return {
        "found": True,
        "cvss_score": score,
        "cvss_version": version,
        "cvss_vector": vector,
        "cwe": _extract_cwe(raw),
        "description": _extract_description(raw),
        "references": _extract_references(raw),
        "capec": _extract_capec(raw),
        "products": _extract_products(raw),
        "cpes": _extract_cpes(raw),
        "epss_score": epss,
        "epss_percentile": epss_pct,
        "kev": kev,
        "kev_ransomware": kev_ransom,
    }
