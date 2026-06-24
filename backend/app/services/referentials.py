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
    "cpe": {
        "url": "https://services.nvd.nist.gov/rest/json/cpes/2.0",
        "version": "NVD 2.0",
        "description": "Common Platform Enumeration — NVD/NIST",
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


# ── Données CPE intégrées — fallback si API NVD indisponible ─────────────────
CPE_BUILTIN = [
    {"ref_id": "cpe:2.3:a:apache:http_server:*",      "name": "Apache HTTP Server",         "description": "Serveur HTTP Apache"},
    {"ref_id": "cpe:2.3:a:nginx:nginx:*",              "name": "Nginx",                      "description": "Serveur web / reverse proxy Nginx"},
    {"ref_id": "cpe:2.3:a:haproxy:haproxy:*",          "name": "HAProxy",                    "description": "Load balancer / proxy TCP-HTTP"},
    {"ref_id": "cpe:2.3:a:traefik:traefik:*",          "name": "Traefik",                    "description": "Reverse proxy cloud-native"},
    {"ref_id": "cpe:2.3:a:postgresql:postgresql:*",    "name": "PostgreSQL",                 "description": "Base de donnees relationnelle"},
    {"ref_id": "cpe:2.3:a:mysql:mysql:*",              "name": "MySQL",                      "description": "Base de donnees relationnelle MySQL"},
    {"ref_id": "cpe:2.3:a:mariadb:mariadb:*",          "name": "MariaDB",                    "description": "Fork communautaire de MySQL"},
    {"ref_id": "cpe:2.3:a:microsoft:sql_server:*",     "name": "SQL Server",                 "description": "Microsoft SQL Server"},
    {"ref_id": "cpe:2.3:a:oracle:database_server:*",   "name": "Oracle Database",            "description": "Base de donnees Oracle"},
    {"ref_id": "cpe:2.3:a:redis:redis:*",              "name": "Redis",                      "description": "Base de donnees cle-valeur en memoire"},
    {"ref_id": "cpe:2.3:a:mongodb:mongodb:*",          "name": "MongoDB",                    "description": "Base de donnees NoSQL orientee documents"},
    {"ref_id": "cpe:2.3:a:elastic:elasticsearch:*",    "name": "Elasticsearch",              "description": "Moteur de recherche distribue"},
    {"ref_id": "cpe:2.3:a:apache:cassandra:*",         "name": "Apache Cassandra",           "description": "Base de donnees NoSQL distribuee"},
    {"ref_id": "cpe:2.3:a:influxdata:influxdb:*",      "name": "InfluxDB",                   "description": "Base de donnees time-series"},
    {"ref_id": "cpe:2.3:a:python:python:*",            "name": "Python",                     "description": "Langage de programmation Python"},
    {"ref_id": "cpe:2.3:a:nodejs:node.js:*",           "name": "Node.js",                    "description": "Runtime JavaScript cote serveur"},
    {"ref_id": "cpe:2.3:a:php:php:*",                  "name": "PHP",                        "description": "Langage de script cote serveur"},
    {"ref_id": "cpe:2.3:a:ruby-lang:ruby:*",           "name": "Ruby",                       "description": "Langage de programmation Ruby"},
    {"ref_id": "cpe:2.3:a:oracle:jdk:*",               "name": "Java JDK",                   "description": "Java Development Kit (Oracle)"},
    {"ref_id": "cpe:2.3:a:openjdk:openjdk:*",          "name": "OpenJDK",                    "description": "Implementation open-source de Java SE"},
    {"ref_id": "cpe:2.3:a:golang:go:*",                "name": "Go (Golang)",                "description": "Langage de programmation Go (Google)"},
    {"ref_id": "cpe:2.3:a:rust-lang:rust:*",           "name": "Rust",                       "description": "Langage systeme securise"},
    {"ref_id": "cpe:2.3:a:microsoft:dotnet:*",         "name": ".NET",                       "description": "Plateforme de developpement Microsoft"},
    {"ref_id": "cpe:2.3:a:djangoproject:django:*",     "name": "Django",                     "description": "Framework web Python"},
    {"ref_id": "cpe:2.3:a:palletsprojects:flask:*",    "name": "Flask",                      "description": "Micro-framework web Python"},
    {"ref_id": "cpe:2.3:a:fastapi:fastapi:*",          "name": "FastAPI",                    "description": "Framework web Python haute performance"},
    {"ref_id": "cpe:2.3:a:spring:spring_framework:*",  "name": "Spring Framework",           "description": "Framework applicatif Java"},
    {"ref_id": "cpe:2.3:a:spring:spring_boot:*",       "name": "Spring Boot",                "description": "Convention-over-configuration pour Spring"},
    {"ref_id": "cpe:2.3:a:laravel:laravel:*",          "name": "Laravel",                    "description": "Framework PHP"},
    {"ref_id": "cpe:2.3:a:symfony:symfony:*",          "name": "Symfony",                    "description": "Framework PHP Symfony"},
    {"ref_id": "cpe:2.3:a:expressjs:express:*",        "name": "Express.js",                 "description": "Framework web Node.js minimaliste"},
    {"ref_id": "cpe:2.3:a:facebook:react:*",           "name": "React",                      "description": "Bibliotheque UI JavaScript (Meta)"},
    {"ref_id": "cpe:2.3:a:vuejs:vue.js:*",             "name": "Vue.js",                     "description": "Framework JavaScript progressif"},
    {"ref_id": "cpe:2.3:a:google:angular:*",           "name": "Angular",                    "description": "Framework web TypeScript (Google)"},
    {"ref_id": "cpe:2.3:a:jquery:jquery:*",            "name": "jQuery",                     "description": "Bibliotheque JavaScript"},
    {"ref_id": "cpe:2.3:a:wordpress:wordpress:*",      "name": "WordPress",                  "description": "CMS open-source PHP"},
    {"ref_id": "cpe:2.3:a:drupal:drupal:*",            "name": "Drupal",                     "description": "CMS open-source PHP"},
    {"ref_id": "cpe:2.3:a:atlassian:jira:*",           "name": "Jira",                       "description": "Outil de gestion de projet (Atlassian)"},
    {"ref_id": "cpe:2.3:a:confluence:confluence:*",    "name": "Confluence",                 "description": "Wiki collaboratif (Atlassian)"},
    {"ref_id": "cpe:2.3:a:apache:kafka:*",             "name": "Apache Kafka",               "description": "Plateforme de streaming distribue"},
    {"ref_id": "cpe:2.3:a:rabbitmq:rabbitmq:*",        "name": "RabbitMQ",                   "description": "Broker de messages AMQP"},
    {"ref_id": "cpe:2.3:a:apache:activemq:*",          "name": "Apache ActiveMQ",            "description": "Broker de messages open-source"},
    {"ref_id": "cpe:2.3:a:docker:docker:*",            "name": "Docker Engine",              "description": "Plateforme de conteneurisation"},
    {"ref_id": "cpe:2.3:a:kubernetes:kubernetes:*",    "name": "Kubernetes",                 "description": "Orchestrateur de conteneurs"},
    {"ref_id": "cpe:2.3:a:redhat:openshift:*",         "name": "OpenShift",                  "description": "Plateforme Kubernetes entreprise (Red Hat)"},
    {"ref_id": "cpe:2.3:a:jenkins:jenkins:*",          "name": "Jenkins",                    "description": "Serveur d integration continue"},
    {"ref_id": "cpe:2.3:a:gitlab:gitlab:*",            "name": "GitLab",                     "description": "Plateforme DevOps GitLab"},
    {"ref_id": "cpe:2.3:a:hashicorp:terraform:*",      "name": "Terraform",                  "description": "Infrastructure as code (HashiCorp)"},
    {"ref_id": "cpe:2.3:a:hashicorp:vault:*",          "name": "HashiCorp Vault",            "description": "Gestion des secrets"},
    {"ref_id": "cpe:2.3:a:ansible:ansible:*",          "name": "Ansible",                    "description": "Automatisation IT (Red Hat)"},
    {"ref_id": "cpe:2.3:o:linux:linux_kernel:*",       "name": "Linux Kernel",               "description": "Noyau Linux"},
    {"ref_id": "cpe:2.3:o:canonical:ubuntu_linux:*",   "name": "Ubuntu",                     "description": "Distribution Linux Ubuntu (Canonical)"},
    {"ref_id": "cpe:2.3:o:debian:debian_linux:*",      "name": "Debian",                     "description": "Distribution Linux Debian"},
    {"ref_id": "cpe:2.3:o:redhat:enterprise_linux:*",  "name": "RHEL",                       "description": "Red Hat Enterprise Linux"},
    {"ref_id": "cpe:2.3:o:centos:centos:*",            "name": "CentOS",                     "description": "Distribution Linux CentOS"},
    {"ref_id": "cpe:2.3:o:alpine:alpine_linux:*",      "name": "Alpine Linux",               "description": "Distribution Linux minimaliste"},
    {"ref_id": "cpe:2.3:o:microsoft:windows_server_2022:*", "name": "Windows Server 2022",  "description": "Microsoft Windows Server 2022"},
    {"ref_id": "cpe:2.3:o:microsoft:windows_server_2019:*", "name": "Windows Server 2019",  "description": "Microsoft Windows Server 2019"},
    {"ref_id": "cpe:2.3:a:vmware:esxi:*",              "name": "VMware ESXi",                "description": "Hyperviseur bare-metal VMware"},
    {"ref_id": "cpe:2.3:a:vmware:vcenter_server:*",    "name": "VMware vCenter",             "description": "Plateforme de gestion VMware"},
    {"ref_id": "cpe:2.3:a:proxmox:virtual_environment:*", "name": "Proxmox VE",             "description": "Plateforme de virtualisation open-source"},
    {"ref_id": "cpe:2.3:a:microsoft:hyper-v:*",        "name": "Hyper-V",                    "description": "Hyperviseur Microsoft"},
    {"ref_id": "cpe:2.3:a:openssl:openssl:*",          "name": "OpenSSL",                    "description": "Bibliotheque cryptographique TLS/SSL"},
    {"ref_id": "cpe:2.3:a:paloaltonetworks:pan-os:*",  "name": "PAN-OS",                     "description": "Systeme Palo Alto Networks"},
    {"ref_id": "cpe:2.3:a:fortinet:fortios:*",         "name": "FortiOS",                    "description": "Systeme d exploitation Fortinet"},
    {"ref_id": "cpe:2.3:a:cisco:asa:*",                "name": "Cisco ASA",                  "description": "Firewall Cisco ASA"},
    {"ref_id": "cpe:2.3:a:cisco:ios:*",                "name": "Cisco IOS",                  "description": "Systeme d exploitation Cisco IOS"},
    {"ref_id": "cpe:2.3:a:elastic:kibana:*",           "name": "Kibana",                     "description": "Interface de visualisation Elasticsearch"},
    {"ref_id": "cpe:2.3:a:grafana:grafana:*",          "name": "Grafana",                    "description": "Plateforme de monitoring et visualisation"},
    {"ref_id": "cpe:2.3:a:prometheus:prometheus:*",    "name": "Prometheus",                 "description": "Systeme de monitoring et d alerting"},
    {"ref_id": "cpe:2.3:a:splunk:splunk:*",            "name": "Splunk",                     "description": "Plateforme d analyse de donnees machine"},
    {"ref_id": "cpe:2.3:a:zabbix:zabbix:*",            "name": "Zabbix",                     "description": "Solution de supervision reseau"},
    {"ref_id": "cpe:2.3:a:apache:log4j:*",             "name": "Log4j",                      "description": "Bibliotheque de journalisation Java"},
    {"ref_id": "cpe:2.3:a:curl:curl:*",                "name": "curl",                       "description": "Outil de transfert de donnees URL"},
    {"ref_id": "cpe:2.3:a:openssh:openssh:*",          "name": "OpenSSH",                    "description": "Suite SSH open-source"},
    {"ref_id": "cpe:2.3:a:openvpn:openvpn:*",          "name": "OpenVPN",                    "description": "Solution VPN open-source"},
    {"ref_id": "cpe:2.3:a:wireguard:wireguard:*",      "name": "WireGuard",                  "description": "Protocole VPN moderne"},
    {"ref_id": "cpe:2.3:a:microsoft:active_directory:*","name": "Active Directory",          "description": "Service d annuaire Microsoft"},
    {"ref_id": "cpe:2.3:a:openldap:openldap:*",        "name": "OpenLDAP",                   "description": "Implementation open-source de LDAP"},
    {"ref_id": "cpe:2.3:a:keycloak:keycloak:*",        "name": "Keycloak",                   "description": "Solution IAM open-source (Red Hat)"},
    {"ref_id": "cpe:2.3:a:apache:tomcat:*",            "name": "Apache Tomcat",              "description": "Serveur d applications Java"},
    {"ref_id": "cpe:2.3:a:oracle:weblogic_server:*",   "name": "WebLogic Server",            "description": "Serveur d applications Java EE (Oracle)"},
    {"ref_id": "cpe:2.3:a:microsoft:exchange_server:*","name": "Exchange Server",            "description": "Serveur de messagerie Microsoft"},
    {"ref_id": "cpe:2.3:a:microsoft:sharepoint_server:*","name": "SharePoint Server",        "description": "Plateforme collaborative Microsoft"},
    {"ref_id": "cpe:2.3:a:sap:netweaver:*",            "name": "SAP NetWeaver",              "description": "Plateforme applicative SAP"},
    {"ref_id": "cpe:2.3:a:minio:minio:*",              "name": "MinIO",                      "description": "Stockage objet compatible S3"},
    {"ref_id": "cpe:2.3:a:mozilla:firefox:*",          "name": "Mozilla Firefox",            "description": "Navigateur web Firefox"},
    {"ref_id": "cpe:2.3:a:google:chrome:*",            "name": "Google Chrome",              "description": "Navigateur web Chrome"},
    {"ref_id": "cpe:2.3:a:microsoft:edge:*",           "name": "Microsoft Edge",             "description": "Navigateur web Microsoft Edge"},
]


# ── Helpers réseau ────────────────────────────────────────────────────────────

def _fetch_bytes(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PurpleLens/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _fetch_text(url: str, timeout: int = 30) -> str:
    return _fetch_bytes(url, timeout).decode("utf-8", errors="replace")

def _parse_cpe_nvd(data: bytes) -> tuple[str, list[dict]]:
    """Parse la reponse JSON de l API NVD CPE 2.0."""
    entries = []
    payload = json.loads(data)
    version = "NVD 2.0"
    for item in payload.get("products", []):
        cpe = item.get("cpe", {})
        cpe_name = cpe.get("cpeName", "")
        titles = cpe.get("titles", [])
        name = next((t.get("title", "") for t in titles if t.get("lang", "") in ("en", "en-US")), "")
        if not name and titles:
            name = titles[0].get("title", "")
        if cpe_name and name:
            entries.append({"ref_id": cpe_name, "name": name, "description": ""})
    return version, entries



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

    elif name == "cpe":
        try:
            # L API NVD necessite parfois une cle API pour les gros volumes
            # On pagine sur les 2000 premieres entrees (suffisant pour usage courant)
            raw = _fetch_bytes(url + "?resultsPerPage=2000", timeout=60)
            version, entries = _parse_cpe_nvd(raw)
        except Exception:
            # Fallback sur les donnees integrees si NVD indisponible
            entries = CPE_BUILTIN
            version = "builtin"

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
    for name in ("owasp", "cwe", "capec", "cpe"):
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
