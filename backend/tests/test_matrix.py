"""Test EXHAUSTIF de la matrice RBAC (matrix.py docstring : aucune divergence silencieuse).

On vérifie :
  1. couverture : chaque (rôle × entité) est défini, pour les 7 rôles et 16 entités ;
  2. invariants doctrinaux transverses (journal L-only pour tous, audit_dek sans accès
     humain, deny par défaut hors matrice) ;
  3. quelques droits précis transcrits du cahier (§3 / §6quater.7) qui ne doivent JAMAIS
     régresser silencieusement.
"""
from __future__ import annotations

import pytest

from app.security.matrix import ENTITIES, MATRIX, ROLES, Action, allowed


def test_all_roles_present():
    assert set(MATRIX.keys()) == set(ROLES)


def test_every_role_covers_every_entity():
    """Aucune case manquante : rôle × entité tous définis (pas de trou = pas d'ambiguïté)."""
    for role in ROLES:
        for entity in ENTITIES:
            assert entity in MATRIX[role], f"{role}/{entity} manquant dans la matrice"


@pytest.mark.parametrize("role", ROLES)
def test_journal_is_read_only_for_everyone(role):
    """Le journal est immuable applicativement : L seul, pour tous (admin compris)."""
    acts = MATRIX[role]["journal"]
    assert Action.L in acts
    assert not ({Action.C, Action.E, Action.S, Action.V} & acts), (
        f"{role} ne doit avoir que L sur le journal"
    )


@pytest.mark.parametrize("role", ROLES)
def test_no_human_write_on_audit_dek(role):
    """audit_dek = frontière crypto : aucun rôle humain n'y a le moindre droit."""
    assert MATRIX[role]["audit_dek"] == frozenset(), (
        f"{role} ne doit avoir AUCUN accès à audit_dek"
    )


def test_deny_by_default_outside_matrix():
    """Une entité inconnue n'est jamais autorisée (deny par défaut)."""
    assert allowed("admin", "entite_inexistante", Action.L) is False


def test_unknown_role_denied():
    assert allowed("intrus", "audits", Action.L) is False


# ── Droits précis transcrits du cahier (garde anti-régression) ──────────────
def test_auditeur_can_create_evidence_but_not_access_log():
    """Auditeur : dépose les preuves (L C E) mais ne voit pas evidence_access (§6quater.7)."""
    assert allowed("auditeur", "evidence", Action.C)
    assert allowed("auditeur", "evidence", Action.E)
    assert not allowed("auditeur", "evidence_access", Action.L)


def test_admin_cannot_create_evidence():
    """Admin : L E S sur evidence, PAS de Create (dépôt réservé à l'Auditeur, §3.1)."""
    assert MATRIX["admin"]["evidence"] == frozenset({Action.L, Action.E, Action.S})


def test_auditeur_can_create_applications():
    """Auditeur : L C sur applications (peut référencer une application découverte en
    audit), mais pas d'édition/suppression (cahier des charges v2, tableau RBAC)."""
    assert MATRIX["auditeur"]["applications"] == frozenset({Action.L, Action.C})


def test_auditeur_can_create_organisations():
    """Auditeur : L C sur organisations (peut référencer un client découvert en audit),
    mais pas d'édition/suppression (cahier des charges v2, tableau RBAC)."""
    assert MATRIX["auditeur"]["organisations"] == frozenset({Action.L, Action.C})


def test_auditeur_can_create_ressources():
    """Auditeur : L C sur ressources (peut référencer une ressource découverte en
    audit), mais pas d'édition/suppression (cahier des charges v2, tableau RBAC)."""
    assert MATRIX["auditeur"]["ressources"] == frozenset({Action.L, Action.C})


def test_voc_owns_vulnerabilities_only():
    """VOC : LCES sur vulnérabilités, mais pas de validation (V réservée manager/ciso/admin)."""
    for a in (Action.L, Action.C, Action.E, Action.S):
        assert allowed("voc", "vulnerabilities", a)
    assert not allowed("voc", "vulnerabilities", Action.V)


def test_ciso_validates_without_crud():
    """CISO : peut valider vuln/tickets (V) sans pouvoir les créer/éditer/supprimer."""
    assert allowed("ciso", "vulnerabilities", Action.V)
    assert allowed("ciso", "tickets", Action.V)
    assert not allowed("ciso", "vulnerabilities", Action.C)
    assert not allowed("ciso", "tickets", Action.E)


def test_manager_read_only_on_ambiguous_entities():
    """D6 du DAT : Manager = L seul sur Ressources / Applications / Actions-CRUD."""
    assert MATRIX["manager"]["ressources"] == frozenset({Action.L})
    assert MATRIX["manager"]["applications"] == frozenset({Action.L})
    # Actions d'audit : L + V (validation), mais pas de CRUD.
    assert Action.C not in MATRIX["manager"]["audit_actions"]


def test_cert_owns_detection_side():
    """CERT : LCES Observations, Tickets, Scénarios, Ressources ; L ailleurs."""
    for a in (Action.L, Action.C, Action.E, Action.S):
        assert allowed("cert", "observations", a)
        assert allowed("cert", "ressources", a)
    assert not allowed("cert", "audits", Action.C)


def test_admin_full_crud_except_journal_and_dek():
    for entity in ENTITIES:
        if entity in ("journal", "audit_dek", "evidence", "evidence_access"):
            continue
        assert allowed("admin", entity, Action.L)
        assert allowed("admin", entity, Action.C)


# ── Rôle `operateur` (prestataire multi-clients, super-utilisateur métier) ──────
def test_operateur_full_crud_on_inventory_scenarios_deliverables():
    """Operateur : CRUD complet sur l'inventaire (org/app/ressources), les scénarios
    (+ étapes) et les livrables — là où l'auditeur reste bridé en L / L C."""
    for entity in (
        "organisations",
        "applications",
        "ressources",
        "scenarios",
        "scenario_steps",
        "deliverables",
    ):
        assert MATRIX["operateur"][entity] == frozenset(
            {Action.L, Action.C, Action.E, Action.S}
        ), f"operateur doit avoir le CRUD complet sur {entity}"


def test_operateur_validates_its_own_audits_vulns_tickets():
    """Operateur : seul à bord, il valide (V) ses propres audits (+ actions, jalons),
    vulnérabilités et tickets — en plus du CRUD complet."""
    for entity in ("audits", "audit_actions", "audit_milestones", "vulnerabilities", "tickets"):
        assert MATRIX["operateur"][entity] == frozenset(
            {Action.L, Action.C, Action.E, Action.S, Action.V}
        ), f"operateur doit avoir LCESV sur {entity}"


def test_operateur_deposits_evidence_without_delete_or_access_log():
    """Operateur : dépose les preuves (L C E), mais pas de S (réservé admin) ni d'accès
    au journal d'accès aux preuves — comme l'auditeur (§6quater.7)."""
    assert MATRIX["operateur"]["evidence"] == frozenset({Action.L, Action.C, Action.E})
    assert MATRIX["operateur"]["evidence_access"] == frozenset()


def test_operateur_corpus_read_only():
    """Operateur : le corpus reste un référentiel en lecture seule."""
    assert MATRIX["operateur"]["corpus"] == frozenset({Action.L})


def test_operateur_is_not_global_scope():
    """Invariant de cloisonnement : operateur n'opère JAMAIS sur tous les clients —
    il est confiné à son client_scope explicite (durcissement fail-closed)."""
    from app.security.matrix import GLOBAL_SCOPE_ROLES

    assert "operateur" not in GLOBAL_SCOPE_ROLES
