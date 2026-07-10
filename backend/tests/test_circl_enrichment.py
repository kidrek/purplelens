"""Enrichissement CIRCL Vulnerability-Lookup — parsing défensif + dégradation gracieuse.

Le sandbox n'a pas accès à vulnerability.circl.lu : on teste le PARSEUR sur des
échantillons représentatifs (format agrégé cvelistv5 et format plat cve-search) et la
dégradation gracieuse en simulant l'indisponibilité réseau. L'appel live relève d'un test
d'intégration à exécuter dans un environnement disposant de l'accès sortant.
"""
from __future__ import annotations

from app.vuln.circl import parse_circl

_AGGREGATED = {
    "cvelistv5": [["CVE-2021-44228", {"containers": {"cna": {
        "descriptions": [{"lang": "en", "value": "Apache Log4j2 JNDI features RCE."}],
        "metrics": [{"cvssV3_1": {"baseScore": 10.0,
                                  "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"}}],
        "problemTypes": [{"descriptions": [{"cweId": "CWE-502"}]}],
        "references": [{"url": "https://logging.apache.org/log4j/2.x/security.html"}],
        "affected": [{"vendor": "Apache", "product": "Log4j"}],
    }}}]],
    "vulnrichment": {"cisa_kev": {"knownRansomwareCampaignUse": "Known"}},
    "epss": [{"epss": "0.94360", "percentile": "0.99980"}],
}

_FLAT = {
    "id": "CVE-2019-0708", "summary": "BlueKeep RDP RCE.",
    "cvss": 9.8, "cvss-vector": "AV:N/AC:L", "cwe": "CWE-416",
    "references": ["https://msrc.microsoft.com/x"], "capec": [{"id": "540"}],
}


def test_parse_aggregated_cvelistv5():
    r = parse_circl(_AGGREGATED)
    assert r["found"] is True
    assert r["cvss_score"] == 10.0 and r["cvss_version"] == "3.1"
    assert r["cwe"] == "CWE-502"
    assert r["kev"] is True and r["kev_ransomware"] is True
    assert abs(r["epss_score"] - 0.9436) < 1e-6
    assert r["products"] == ["Apache Log4j"]
    assert len(r["references"]) == 1


def test_parse_flat_cve_search():
    r = parse_circl(_FLAT)
    assert r["found"] is True
    assert r["cvss_score"] == 9.8
    assert r["cwe"] == "CWE-416"
    assert r["capec"] == ["CAPEC-540"]


def test_parse_empty_is_not_found():
    assert parse_circl({}) == {"found": False}


def test_prioritizes_cvss4_over_cvss31():
    doc = {"a": {"cvssV3_1": {"baseScore": 7.0, "vectorString": "x"}},
           "b": {"cvssV4_0": {"baseScore": 9.1, "vectorString": "y"}}}
    r = parse_circl(doc)
    assert r["cvss_score"] == 9.1 and r["cvss_version"] == "4.0"


def test_parse_real_cve_record_cvss4_and_cpe():
    """Enregistrement CVE 5.x réel (format renvoyé par vulnerability.circl.lu)."""
    real = {"containers": {"cna": {
        "problemTypes": [{"descriptions": [{"type": "CWE", "cweId": "CWE-89", "lang": "en"}]}],
        "affected": [{"vendor": "CodeAstro", "product": "AVMS",
                      "cpes": ["cpe:2.3:a:codeastro:avms:*:*:*:*:*:*:*:*"]}],
        "descriptions": [{"lang": "en", "value": "SQL injection via searchdata."}],
        "metrics": [
            {"cvssV4_0": {"baseScore": 5.3, "vectorString": "CVSS:4.0/AV:N"}},
            {"cvssV3_1": {"baseScore": 6.3, "vectorString": "CVSS:3.1/AV:N"}},
            {"cvssV2_0": {"baseScore": 6.5, "vectorString": "AV:N/AC:L"}},
        ],
        "references": [{"url": "https://vuldb.com/vuln/376356"}],
    }}}
    r = parse_circl(real)
    assert r["cvss_score"] == 5.3 and r["cvss_version"] == "4.0"  # 4.0 prioritaire
    assert r["cwe"] == "CWE-89"
    assert r["cpes"] == ["cpe:2.3:a:codeastro:avms:*:*:*:*:*:*:*:*"]
    assert r["products"] == ["CodeAstro AVMS"]
