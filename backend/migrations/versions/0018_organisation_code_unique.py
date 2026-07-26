"""Unicité du `code` organisation + dédoublonnage des clients dupliqués.

Contexte : le seed (`make seed` / `make bootstrap`) réinsérait les organisations démo avec
un `id` uuid neuf à chaque exécution et un `ON CONFLICT DO NOTHING` **sans cible** — faute
d'unicité sur `code`, aucun conflit ne se déclenchait et chaque run recréait ACME/GLOBEX/
PRESTA, d'où des clients affichés en double dans les filtres.

Cette migration :
  1. bascule temporairement `organisation` en `NO FORCE ROW LEVEL SECURITY` (le propriétaire
     `app_migrator` est sinon soumis à la RLS `USING (app_client_visible(id))`, qui ne voit
     aucune ligne hors contexte applicatif) ;
  2. supprime les doublons ORPHELINS : pour chaque `code`, conserve la ligne canonique (celle
     référencée par une table enfant, à défaut la plus ancienne) et supprime les autres lignes
     de même `code` qui ne sont référencées par AUCUNE des 14 tables à FK vers `organisation` ;
  3. restaure `FORCE ROW LEVEL SECURITY` ;
  4. pose un index unique PARTIEL sur `code` (lignes vivantes uniquement — cohérent avec le
     soft-delete `deleted_at`, même motif que `uq_ressource_user_org` en 0017).

Idempotente sur une base déjà propre (le DELETE ne trouve rien, l'index est `IF NOT EXISTS`).

Revision ID: 0018_organisation_code_unique
Revises: 0017_ressource_app_user_id
"""
from __future__ import annotations

from alembic import op

revision = "0018_organisation_code_unique"
down_revision = "0017_ressource_app_user_id"
branch_labels = None
depends_on = None

# Toutes les tables portant une FK vers organisation (via client_id, sauf ressource :
# organisation_id). Une organisation absente de cet ensemble n'a aucun enfant → orpheline.
_DEDUP = """
WITH ref_org AS (
    SELECT client_id AS id FROM application WHERE client_id IS NOT NULL
    UNION SELECT organisation_id FROM ressource WHERE organisation_id IS NOT NULL
    UNION SELECT client_id FROM audit WHERE client_id IS NOT NULL
    UNION SELECT client_id FROM sla_rule WHERE client_id IS NOT NULL
    UNION SELECT client_id FROM audit_milestone WHERE client_id IS NOT NULL
    UNION SELECT client_id FROM purple_exercise WHERE client_id IS NOT NULL
    UNION SELECT client_id FROM vulnerability WHERE client_id IS NOT NULL
    UNION SELECT client_id FROM deliverable WHERE client_id IS NOT NULL
    UNION SELECT client_id FROM attack_step WHERE client_id IS NOT NULL
    UNION SELECT client_id FROM vulnerability_enrichment WHERE client_id IS NOT NULL
    UNION SELECT client_id FROM remediation_ticket WHERE client_id IS NOT NULL
    UNION SELECT client_id FROM audit_action WHERE client_id IS NOT NULL
    UNION SELECT client_id FROM defense_observation WHERE client_id IS NOT NULL
    UNION SELECT client_id FROM detection_ticket WHERE client_id IS NOT NULL
),
keep AS (
    SELECT DISTINCT ON (o.code) o.id
    FROM organisation o
    LEFT JOIN ref_org r ON r.id = o.id
    ORDER BY o.code, (r.id IS NOT NULL) DESC, o.created_at ASC, o.id ASC
)
DELETE FROM organisation o
WHERE o.id NOT IN (SELECT id FROM keep)
  AND o.id NOT IN (SELECT id FROM ref_org)
"""


def upgrade() -> None:
    op.execute("ALTER TABLE organisation NO FORCE ROW LEVEL SECURITY")
    op.execute(_DEDUP)
    op.execute("ALTER TABLE organisation FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_organisation_code "
        "ON organisation (code) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_organisation_code")
