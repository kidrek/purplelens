"""Lien compte ↔ ressource : `ressource.app_user_id`.

Permet à un compte (`app_user`) — typiquement `operateur`/`auditeur`, autonome sur la
chaîne scénario→audit→exercice — de disposer d'une **fiche ressource** (type humaine)
qui lui est propre, et donc de se sélectionner comme auditeur d'un audit (le picker
liste les ressources humaines). `ressource` reste la source unique de la fiche auditeur.

Colonne FK nullable (rétro-compatible : les fiches existantes restent non liées) +
index de recherche + unicité d'au plus une fiche par (compte, organisation). La policy
RLS `ressource_rls` filtre sur `organisation_id` (agnostique aux colonnes) : rien à y
changer.

Revision ID: 0017_ressource_app_user_id
Revises: 0016_operateur_create_org
"""
from __future__ import annotations

from alembic import op

revision = "0017_ressource_app_user_id"
down_revision = "0016_operateur_create_org"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ressource "
        "ADD COLUMN IF NOT EXISTS app_user_id uuid NULL REFERENCES app_user(id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ressource_app_user_id ON ressource (app_user_id)"
    )
    # Au plus une fiche liée par (compte, organisation) — filet de sécurité de l'upsert
    # « Ma fiche ». Partiel : n'impacte pas les fiches non liées (app_user_id NULL).
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_ressource_user_org "
        "ON ressource (app_user_id, organisation_id) WHERE app_user_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_ressource_user_org")
    op.execute("DROP INDEX IF EXISTS ix_ressource_app_user_id")
    op.execute("ALTER TABLE ressource DROP COLUMN IF EXISTS app_user_id")
