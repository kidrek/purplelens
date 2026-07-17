"""Matrice RBAC — UNE DONNÉE, pas du code (DAT §2.4 / spec backend v2 §3.1).

Dictionnaire unique {role -> entité -> actions}, chargé au démarrage et appliqué
par la dépendance `require(entity, action)`. Le contenu transpose la spec v2 §3.1
et le cahier §3 / §6quater.7. Toute divergence code/spec est censée échouer au
test exhaustif (tests/test_matrix.py) — aucune divergence silencieuse possible.

Actions : L (lecture) · C (création) · E (édition) · S (suppression) · V (validation).
"""
from __future__ import annotations

from enum import Enum


class Action(str, Enum):
    L = "L"  # Lecture
    C = "C"  # Création
    E = "E"  # Édition
    S = "S"  # Suppression
    V = "V"  # Validation


# Les 6 rôles de la v1 (spec v2 §2.1) + `operateur` : profil prestataire multi-clients
# « super-utilisateur métier » (auditeur élevé au CRUD complet sur l'inventaire, les scénarios
# et les livrables, avec validation de ses propres audits/vulnérabilités/tickets). Reste
# strictement scoppé (non global) — cf. GLOBAL_SCOPE_ROLES plus bas.
ROLES: tuple[str, ...] = ("admin", "manager", "ciso", "auditeur", "voc", "cert", "operateur")

# Rôles de service (non interactifs, périmètre minimal — spec v2 §2.2).
SERVICE_ROLES: tuple[str, ...] = (
    "report_render",
    "job_retention",
    "job_integrity",
    "admin_service",
)

# Rôles autorisés à opérer sur TOUS les clients quand leur scope est vide (spec v2 §2.1).
# admin/manager sont multi-clients par doctrine ; les rôles de service ont un périmètre
# transverse assumé (jobs, rendu). Pour TOUT autre rôle (auditeur, ciso, voc, cert), un
# scope vide est un ÉCART fail-closed : il ne doit RIEN voir, jamais tout (durcissement P1).
# Cette liste est la source unique ; la RLS (app_role_spans_all_clients) en est le miroir SQL.
GLOBAL_SCOPE_ROLES: frozenset[str] = frozenset({"admin", "manager"}) | frozenset(SERVICE_ROLES)

# Les 13 entités métier + les 2 entités de preuves (spec v2 §3.1).
ENTITIES: tuple[str, ...] = (
    "organisations",
    "applications",
    "ressources",
    "audits",
    "audit_actions",
    "audit_milestones",
    "attack_steps",
    "exercices",
    "observations",
    "vulnerabilities",
    "tickets",
    "scenarios",
    "scenario_steps",
    "corpus",
    "deliverables",
    "journal",
    # v5.0 — sous-système de preuves
    "evidence",
    "evidence_access",
    "audit_dek",
)


def _a(*actions: Action) -> frozenset[Action]:
    return frozenset(actions)


L, C, E, S, V = Action.L, Action.C, Action.E, Action.S, Action.V

# =============================================================================
# La matrice. Lecture directe du cahier §3 (profils) et §6quater.7 (Preuves).
# Les 3 ambiguïtés Manager (Ressources / Applications / Actions d'audit) sont
# figées par D6 du DAT : Manager = L sur ces entités.
# =============================================================================
MATRIX: dict[str, dict[str, frozenset[Action]]] = {
    "admin": {
        # LCES sur toutes les entités ; L seul sur le journal (immuable, même pour l'admin).
        "organisations": _a(L, C, E, S),
        "applications": _a(L, C, E, S),
        "ressources": _a(L, C, E, S),
        "audits": _a(L, C, E, S, V),
        "audit_actions": _a(L, C, E, S, V),
"audit_milestones": _a(L, C, E, S, V),
        "attack_steps": _a(L, C, E, S),
        "exercices": _a(L, C, E, S),
        "observations": _a(L, C, E, S),
        "vulnerabilities": _a(L, C, E, S, V),
        "tickets": _a(L, C, E, S, V),
        "scenarios": _a(L, C, E, S),
        "scenario_steps": _a(L, C, E, S),
"corpus": _a(L, C, E, S),
        "deliverables": _a(L, C, E, S),
        "journal": _a(L),
        "evidence": _a(L, E, S),          # L E¹ S² (§6quater.7)
        "evidence_access": _a(L),
        "audit_dek": _a(),                # aucun accès humain (note ³)
    },
    "manager": {
        # LCES Exercices, Scénarios, Audits, Livrables ; LV Vuln/Tickets/Actions ;
        # L Organisations, Applications, Ressources, Journal. Toujours multi-client.
        "organisations": _a(L),
        "applications": _a(L),
        "ressources": _a(L),
        "audits": _a(L, C, E, S),
        "audit_actions": _a(L, V),
"audit_milestones": _a(L, V),
        "attack_steps": _a(L, C, E, S),
        "exercices": _a(L, C, E, S),
        "observations": _a(L),
        "vulnerabilities": _a(L, V),
        "tickets": _a(L, V),
        "scenarios": _a(L, C, E, S),
        "scenario_steps": _a(L, C, E, S),
"corpus": _a(L, C, E, S),
        "deliverables": _a(L, C, E, S),
        "journal": _a(L),
        "evidence": _a(L, E),             # L E¹
        "evidence_access": _a(L),
        "audit_dek": _a(),
    },
    "ciso": {
        # L large ; LV Vulnérabilités & Tickets (validation sans CRUD).
        "organisations": _a(L),
        "applications": _a(L),
        "ressources": _a(L),
        "audits": _a(L),
        "audit_actions": _a(L),
"audit_milestones": _a(L),
        "attack_steps": _a(L),
        "exercices": _a(L),
        "observations": _a(L),
        "vulnerabilities": _a(L, V),
        "tickets": _a(L, V),
        "scenarios": _a(L),
        "scenario_steps": _a(L),
"corpus": _a(L),
        "deliverables": _a(L),
        "journal": _a(L),
        "evidence": _a(L),
        "evidence_access": _a(L),
        "audit_dek": _a(),
    },
    "auditeur": {
        # LCES Audits, Exercices, Actions, Attaques, Vulnérabilités, Tickets ;
        # LC Livrables, Applications, Organisations, Ressources ; L Scénarios.
        "organisations": _a(L, C),
        "applications": _a(L, C),
        "ressources": _a(L, C),
        "audits": _a(L, C, E, S),
        "audit_actions": _a(L, C, E, S),
"audit_milestones": _a(L, C, E, S),
        "attack_steps": _a(L, C, E, S),
        "exercices": _a(L, C, E, S),
        "observations": _a(L, C, E, S),
        "vulnerabilities": _a(L, C, E, S),
        "tickets": _a(L, C, E, S),
        "scenarios": _a(L),
        "scenario_steps": _a(L),
"corpus": _a(L),
        "deliverables": _a(L, C),
        "journal": _a(L),
        "evidence": _a(L, C, E),          # L C E¹ — dépose les preuves (§6quater.7)
        "evidence_access": _a(),
        "audit_dek": _a(),
    },
    "voc": {
        # L Audits/Exercices, Applications, Organisations ; LCES Vulnérabilités.
        "organisations": _a(L),
        "applications": _a(L),
        "ressources": _a(L),
        "audits": _a(L),
        "audit_actions": _a(L),
"audit_milestones": _a(L),
        "attack_steps": _a(L),
        "exercices": _a(L),
        "observations": _a(L),
        "vulnerabilities": _a(L, C, E, S),
        "tickets": _a(L),
        "scenarios": _a(L),
        "scenario_steps": _a(L),
"corpus": _a(L),
        "deliverables": _a(L),
        "journal": _a(L),
        "evidence": _a(L),
        "evidence_access": _a(),
        "audit_dek": _a(),
    },
    "cert": {
        # LCES Scénarios, Observations, Tickets, Ressources ; L le reste.
        "organisations": _a(L),
        "applications": _a(L),
        "ressources": _a(L, C, E, S),
        "audits": _a(L),
        "audit_actions": _a(L),
"audit_milestones": _a(L),
        "attack_steps": _a(L),
        "exercices": _a(L),
        "observations": _a(L, C, E, S),
        "vulnerabilities": _a(L),
        "tickets": _a(L, C, E, S),
        "scenarios": _a(L, C, E, S),
        "scenario_steps": _a(L, C, E, S),
"corpus": _a(L, C, E, S),
        "deliverables": _a(L),
        "journal": _a(L),
        "evidence": _a(L),
        "evidence_access": _a(),
        "audit_dek": _a(),
    },
    "operateur": {
        # Prestataire multi-clients « super-utilisateur métier » : auditeur élevé au CRUD
        # complet sur l'inventaire (Organisations, Applications, Ressources), les Scénarios
        # (+ étapes) et les Livrables ; validation (V) de ses propres Audits (+ Actions,
        # Jalons), Vulnérabilités et Tickets. Confiné à son client_scope (NON global) :
        # provisionne et pilote de bout en bout les engagements de ses clients.
        "organisations": _a(L, C, E, S),
        "applications": _a(L, C, E, S),
        "ressources": _a(L, C, E, S),
        "audits": _a(L, C, E, S, V),
        "audit_actions": _a(L, C, E, S, V),
        "audit_milestones": _a(L, C, E, S, V),
        "attack_steps": _a(L, C, E, S),
        "exercices": _a(L, C, E, S),
        "observations": _a(L, C, E, S),
        "vulnerabilities": _a(L, C, E, S, V),
        "tickets": _a(L, C, E, S, V),
        "scenarios": _a(L, C, E, S),
        "scenario_steps": _a(L, C, E, S),
        "corpus": _a(L),
        "deliverables": _a(L, C, E, S),
        "journal": _a(L),
        "evidence": _a(L, C, E),          # L C E¹ — dépose les preuves (pas de S : réservé admin)
        "evidence_access": _a(),
        "audit_dek": _a(),
    },
}


def allowed(role: str, entity: str, action: Action) -> bool:
    """Consultation pure de la matrice (porte 3 du moteur de décision)."""
    return action in MATRIX.get(role, {}).get(entity, frozenset())
