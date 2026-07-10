"""Registre des entités métier — pont entre le nom d'entité RBAC (pluriel, utilisé
par la matrice et les routes) et le modèle ORM (singulier).

Chaque entrée décrit :
  - model            : la classe ORM
  - client_field     : la colonne portant le cloisonnement (None si entité globale/CTI)
  - writable         : champs acceptés en création/édition (liste blanche stricte)
  - auto             : champs calculés serveur (jamais fournis par le client)
  - order_by         : tri par défaut

Le cahier §2 impose que certains champs soient *dérivés serveur* (noms auto-générés,
SLA, séquences). On ne les expose donc pas en écriture : la liste blanche `writable`
est la seule surface d'écriture, tout le reste est ignoré silencieusement à l'entrée.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.business import (
    Application,
    AttackStep,
    Audit,
    AuditAction,
    AuditMilestone,
    CorpusArticle,
    DefenseObservation,
    Deliverable,
    DetectionTicket,
    Organisation,
    PurpleExercise,
    Ressource,
    Scenario,
    ScenarioStep,
    Vulnerability,
)


@dataclass(frozen=True)
class EntitySpec:
    entity: str                       # nom RBAC (pluriel)
    model: type                       # classe ORM
    client_field: str | None          # colonne de cloisonnement (RLS + porte 4)
    writable: tuple[str, ...]         # champs acceptés en écriture
    auto: tuple[str, ...] = field(default_factory=tuple)  # champs dérivés serveur
    order_by: str = "created_at"
    # Colonnes (clés étrangères) sur lesquelles la liste peut être filtrée via query.
    # Liste blanche stricte : on ne filtre jamais sur une colonne arbitraire.
    filterable: tuple[str, ...] = field(default_factory=tuple)
    # Cahier A000.2 : le code court est OPTIONNEL à la saisie mais NOT NULL en base
    # (il sert de segment d'arborescence S3). Si absent/vide, le serveur le dérive
    # par repli : slug du premier mot du nom. Reste éditable (≠ spec.auto).
    code_fallback: bool = False


# Champs communs jamais écrits directement.
_READONLY = ("id", "created_at", "updated_at", "deleted_at")


REGISTRY: dict[str, EntitySpec] = {
    "organisations": EntitySpec(
        "organisations", Organisation, client_field="id",
        writable=("nom", "code", "role", "secteur", "contacts", "tlp_defaut",
                  "referent_interne", "siren", "statut", "tags", "commentaires"),
        order_by="nom",
        code_fallback=True,
    ),
    "applications": EntitySpec(
        "applications", Application, client_field="client_id",
        filterable=("client_id",),
        writable=("client_id", "nom", "code", "version", "type", "criticite", "stack",
                  "url", "contact_metier", "statut", "exposition", "valeur_metier",
                  "tags", "tlp"),
        order_by="nom",
        code_fallback=True,
    ),
    "ressources": EntitySpec(
        "ressources", Ressource, client_field="organisation_id",
        filterable=("organisation_id",),
        writable=("organisation_id", "nom", "type", "role", "competences",
                  "contact", "description", "tags"),
        order_by="nom",
    ),
    "audits": EntitySpec(
        "audits", Audit, client_field="client_id",
        filterable=("client_id", "statut"),
        writable=("client_id", "categorie", "type_test", "scenario_id", "applications",
                  "auditeurs", "environnement", "source", "date_debut", "date_fin",
                  "statut", "budget", "priorite", "notes", "tlp", "engagement",
                  "jalons", "referentiels_methodo"),
        auto=("nom", "period", "seq"),  # nom auto-généré + séquence annuelle (cahier §2)
    ),
    "audit_actions": EntitySpec(
        "audit_actions", AuditAction, client_field="client_id",
        filterable=("audit_id", "client_id", "ptes_phase", "statut"),
        writable=("audit_id", "client_id", "ptes_phase", "titre", "description",
                  "application_id", "auditeur_id", "technique_attack", "outil",
                  "horodatage_debut", "horodatage_fin", "resultat", "vulnerabilite_id",
                  "statut", "attack_chain_step_id"),
    ),
    "audit_milestones": EntitySpec(
        "audit_milestones", AuditMilestone, client_field="client_id",
        writable=("audit_id", "client_id", "ptes_phase", "statut", "date_prevue",
                  "date_reelle", "livrable", "notes"),
        filterable=("audit_id", "client_id", "ptes_phase"),
        order_by="date_prevue",
    ),
    "attack_steps": EntitySpec(
        "attack_steps", AttackStep, client_field="client_id",
        filterable=("exercise_id", "client_id"),
        writable=("exercise_id", "client_id", "ordre", "technique", "titre",
                  "horodatage", "horodatage_detection", "horodatage_reponse", "verdict"),
        order_by="ordre",
    ),
    "exercices": EntitySpec(
        "exercices", PurpleExercise, client_field="client_id",
        filterable=("audit_id", "client_id"),
        writable=("audit_id", "client_id", "equipe", "date", "statut", "tlp", "notes",
                  "run_number"),
        auto=("nom", "period", "seq"),
    ),
    "observations": EntitySpec(
        "observations", DefenseObservation, client_field="client_id",
        filterable=("attack_step_id", "client_id"),
        writable=("attack_step_id", "client_id", "source", "resultat", "description"),
    ),
    "vulnerabilities": EntitySpec(
        "vulnerabilities", Vulnerability, client_field="client_id",
        filterable=("client_id", "severite", "statut", "audit_id"),
        writable=("client_id", "audit_id", "cve", "cwe", "severite", "cvss_score", "cvss_vector",
                  "statut", "decouvreur_id", "description", "recommandation", "applications",
                  "techniques", "owasp_top10", "phase_decouverte",
                  "exploitabilite", "preuve_exploitation", "impact_metier", "tlp"),
        auto=("titre", "period", "seq", "sla_niveau", "sla_echeance"),  # SLA dérivé (cahier §2)
    ),
    "tickets": EntitySpec(
        "tickets", DetectionTicket, client_field="client_id",
        filterable=("client_id", "statut"),
        writable=("client_id", "source_attack_step_id", "technique_attack",
                  "mesure_d3fend", "description", "priorite", "statut", "regle_sigma",
                  "gap_decouvert_le"),
    ),
    "scenarios": EntitySpec(
        "scenarios", Scenario, client_field=None,  # CTI global — hors RLS client
        writable=("nom", "objectif", "acteur_emule", "type_engagement", "sophistication",
                  "ioc", "ioa", "references", "source_id", "credibilite",
                  "tlp", "pap", "notes"),
        order_by="nom",
    ),
    "scenario_steps": EntitySpec(
        "scenario_steps", ScenarioStep, client_field=None,  # rattaché au scénario (global, hors RLS)
        filterable=("scenario_id",),
        writable=("scenario_id", "ordre", "technique", "tactique", "commande", "description"),
        order_by="ordre",
    ),
    "deliverables": EntitySpec(
        "deliverables", Deliverable, client_field="client_id",
        writable=("client_id", "audit_id", "type", "titre", "langue", "statut", "tlp", "meta"),
        filterable=("client_id", "audit_id"),
    ),
    "corpus": EntitySpec(
        "corpus", CorpusArticle, client_field=None,
        writable=("slug", "nature", "profils", "titre_fr", "titre_en", "contenu",
                  "controles_iso", "gabarit"),
        order_by="slug",
    ),
}


def spec_for(entity: str) -> EntitySpec:
    try:
        return REGISTRY[entity]
    except KeyError as exc:  # pragma: no cover - garde-fou
        raise KeyError(f"entité inconnue: {entity}") from exc
