"""RLS organisation : autoriser le rôle `operateur` à créer des organisations.

Le rôle `operateur` (prestataire multi-clients « super-utilisateur métier », matrix.ROLES)
a le CRUD complet sur les Organisations côté matrice (porte 3). La couche 2 (RLS) garde
l'INSERT `organisation` par `app_role_may_create_org()` — miroir SQL des droits `organisations:C`
de la matrice (« la couche 2 n'est jamais plus large que la couche 1 »). On l'étend donc à
`operateur`, sinon l'INSERT serait rejeté par la RLS malgré l'autorisation de la matrice.

`app_role_spans_all_clients()` n'est PAS touchée : `operateur` reste strictement scoppé (non
global). Les autres entités (ressources, scénarios, exercices, livrables…) ont un INSERT confiné
par le scope client (`app_client_visible` / WITH CHECK) et non par le rôle — aucune autre garde
RLS à modifier.

Revision ID: 0016_operateur_create_org
Revises: 0015_ref_threat_actors
"""
from __future__ import annotations

from alembic import op

revision = "0016_operateur_create_org"
down_revision = "0015_ref_threat_actors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_role_may_create_org() RETURNS boolean
          LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.role', true), '') IN
              ('admin', 'auditeur', 'operateur', 'admin_service')
          $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_role_may_create_org() RETURNS boolean
          LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.role', true), '') IN
              ('admin', 'auditeur', 'admin_service')
          $$;
        """
    )
