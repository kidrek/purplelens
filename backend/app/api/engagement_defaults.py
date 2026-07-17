"""Dérivation du bloc engagement (lettre d'engagement / NDA) d'un audit.

Miroir serveur de `engagementDefaults` du drawer d'audit
(`frontend/src/components/AuditDrawer.vue`). Objectif : pré-remplir
`audit.engagement` (JSONB) dès la création de l'audit, pour que la vue de
consultation l'affiche sans édition préalable ET que la génération de livrable
(lettre d'engagement / NDA) reprenne un contenu riche dérivé de l'audit plutôt
que ses seuls replis génériques.

⚠️ Toute évolution ici doit rester alignée avec la version front (les deux
produisent le même bloc ; le front sert de repli pour les audits créés avant
l'introduction de ce pré-remplissage). Les 18 clés correspondent à
`ENTITY_FIELDS.engagement` (`frontend/src/fields.js`).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

_BOX_LABELS = {
    "blackbox": "boîte noire",
    "graybox": "boîte grise",
    "whitebox": "boîte blanche",
}


def _client_code(nom: str) -> str:
    """Code client normalisé (diacritiques retirés, alphanumérique, 14 car. max)."""
    nfd = unicodedata.normalize("NFD", nom or "")
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9]+", "", stripped.upper())[:14]


def build_engagement_defaults(
    audit: dict[str, Any],
    *,
    client_nom: str | None = None,
    app_names: list[str] | None = None,
    acteur_emule: str | None = None,
) -> dict[str, Any]:
    """Construit le bloc engagement par défaut d'un audit.

    `audit` porte les champs de l'audit (categorie, type_test, environnement,
    referentiels_methodo, date_debut, date_fin, client_id, applications).
    `client_nom`, `app_names`, `acteur_emule` sont résolus par l'appelant
    (noms lisibles, non présents tels quels dans l'audit).
    """
    a = audit or {}
    client_nom = client_nom or "le client"
    apps = [n for n in (app_names or []) if n]
    client_code = _client_code(client_nom)
    year = (str(a.get("date_debut") or "")[:4]) or str(date.today().year)
    fenetres = (
        [f"{a['date_debut']} → {a['date_fin']}"]
        if a.get("date_debut") and a.get("date_fin")
        else []
    )

    cat = a.get("categorie") or "pentest"
    type_test = a.get("type_test")
    box = _BOX_LABELS.get(type_test) or (type_test if type_test else "boîte grise")
    env = a.get("environnement") or "l'environnement convenu"
    refs = a.get("referentiels_methodo") or []
    refs_txt = ", ".join(refs) if refs else "PTES et OWASP WSTG"
    perimetre_txt = ", ".join(apps) if apps else "le périmètre convenu"

    objectifs = {
        "pentest": [
            "Identifier et qualifier les vulnérabilités exploitables du périmètre "
            f"({perimetre_txt}) en conditions réelles.",
            "Évaluer l'impact métier d'une compromission et la profondeur d'accès atteignable.",
            "Formuler des recommandations de remédiation priorisées par le niveau de risque.",
        ],
        "red_team": [
            "Évaluer la capacité de détection et de réaction des équipes défensives "
            "face à un adversaire réaliste"
            + (f" (émulation {acteur_emule})." if acteur_emule else "."),
            "Démontrer une chaîne d'attaque de bout en bout : "
            "accès initial → progression → atteinte de l'objectif.",
            "Mesurer les délais de détection (MTTD) et de réaction (MTTR) sur les TTP mis en œuvre.",
        ],
        "bas": [
            "Valider l'efficacité des contrôles de sécurité en place face à un ensemble de TTP ATT&CK.",
            "Mesurer la couverture de détection et identifier les angles morts de la télémétrie.",
        ],
    }
    livrables = {
        "pentest": [
            "Lettre d'engagement signée",
            "Rapport de test d'intrusion (synthèse exécutive + détails techniques)",
            "Registre des vulnérabilités priorisées (CVSS et SLA de remédiation)",
            "Restitution orale et plan d'action",
        ],
        "red_team": [
            "Lettre d'engagement signée",
            "Rapport Red Team (récit d'attaque, chaîne ATT&CK, recommandations)",
            "Synthèse détection/réaction (MTTD/MTTR) à destination de la Blue Team",
            "Restitution conjointe (purple debrief)",
        ],
        "bas": [
            "Lettre d'engagement signée",
            "Rapport de simulation (couverture ATT&CK, verdicts par TTP)",
            "Matrice des angles morts de détection",
            "Recommandations d'amélioration de la télémétrie",
        ],
    }

    return {
        "objectifs": objectifs.get(cat, objectifs["pentest"]),
        "perimetre_inclus": apps if apps else [],
        "perimetre_exclus": [
            "Tout système, application ou plage réseau non explicitement listé au périmètre inclus.",
            "Attaques par déni de service (DoS/DDoS), sauf autorisation écrite explicite.",
            "Ingénierie sociale et intrusions physiques, sauf mention contraire au périmètre.",
            "Services tiers et infrastructures hébergées non maîtrisés par le client "
            "(autorisation de l'hébergeur requise).",
        ],
        "regles_engagement": (
            f"Tests menés en approche {box} sur {env}, selon la méthodologie {refs_txt}. "
            "Aucune exfiltration réelle de données : les preuves collectées sont limitées "
            "au strict nécessaire à la démonstration de la vulnérabilité. Toute vulnérabilité "
            "critique susceptible d'affecter la disponibilité ou l'intégrité des services fait "
            "l'objet d'une notification immédiate au contact d'urgence avant toute exploitation "
            "approfondie. Les tests destructifs et le déni de service sont proscrits sauf "
            "autorisation écrite. En cas de découverte de données personnelles ou sensibles, "
            "l'auditeur interrompt l'action en cours et en informe sans délai le client."
        ),
        "fenetres_test": (
            [
                *fenetres,
                "Actions à risque planifiées et confirmées avec le contact d'urgence ; "
                "tests hors heures ouvrées à privilégier.",
            ]
            if fenetres
            else [
                "Fenêtre de test à convenir ; actions à risque planifiées et confirmées "
                "avec le contact d'urgence."
            ]
        ),
        "contacts_autorisation": [
            "Responsable habilité du client (RSSI ou équivalent) — "
            "nom, fonction et courriel à compléter"
        ],
        "contacts_urgence": [
            f"Astreinte sécurité / SOC de {client_nom} — "
            "joignable pendant la fenêtre de test (à compléter)"
        ],
        "sow": f"SOW-{year}-{client_code or 'CLIENT'}",
        "ref_nda": f"NDA-{client_code}-{year}" if client_code else f"NDA-{year}",
        "niveau_intensite": (
            "Modéré — exploitation contrôlée, sans impact recherché "
            "sur la disponibilité des services."
        ),
        "livrables_attendus": livrables.get(cat, livrables["pentest"]),
        "clauses_legales": (
            "Prestation exécutée dans le cadre du bon de commande (SOW) référencé et de "
            "l'accord de confidentialité (NDA) en vigueur, sous obligation de moyens. Le "
            "prestataire est tenu à la confidentialité et à la non-divulgation, et déclare "
            "disposer d'une assurance responsabilité civile professionnelle en cours de "
            "validité. Sa responsabilité est limitée au montant de la prestation, hors faute "
            "lourde ou dolosive. Le traitement d'éventuelles données personnelles est réalisé "
            "conformément au RGPD (accord de sous-traitance au titre de l'article 28 le cas "
            "échéant)."
        ),
        "nda_objet": (
            "Sont réputées confidentielles toutes les informations techniques, "
            "organisationnelles ou personnelles relatives au périmètre audité "
            f"({perimetre_txt}), aux vulnérabilités identifiées, aux preuves collectées et "
            "aux livrables produits, quel qu'en soit le support. En sont exclues les "
            "informations publiques, celles déjà légitimement détenues, ou développées de "
            "manière indépendante par la partie réceptrice."
        ),
        "nda_duree": (
            "Trois (3) ans à compter de la fin de la mission, "
            "sans préjudice des obligations légales plus longues."
        ),
        "nda_traitement": (
            "Données cloisonnées par client et marquées selon le protocole TLP ; accès tracé "
            "dans un journal tamper-evident ; preuves chiffrées au repos (AES-256-GCM). Aucun "
            "partage ni corrélation inter-clients. Accès restreint aux seuls intervenants de "
            "la mission (besoin d'en connaître)."
        ),
        "nda_restitution": (
            "Restitution ou destruction certifiée de l'ensemble des données et preuves dans "
            "un délai de 30 jours suivant la diffusion du rapport final, sur demande écrite "
            "du client et attestée par le prestataire."
        ),
        "nda_droit": (
            "Droit français ; tribunaux compétents du ressort du siège du prestataire "
            "(à adapter au contrat)."
        ),
    }
