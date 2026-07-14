"""RLS organisation : politique INSERT dédiée (cahier RBAC — auditeur peut créer une
organisation, spec backend v2 §3.1).

`organisation` est la seule table cloisonnée dont la colonne de portée est sa PROPRE
clé primaire (elle EST le client — cf. 0001_initial._SCOPE_COLUMN). La politique
générique `{table}_rls` exige `app_client_visible(id)` aussi bien en lecture qu'en
écriture ; pour un INSERT, l'`id` de la nouvelle ligne est un UUID fraîchement généré
qui ne peut par construction figurer dans AUCUN client_scope existant. Un rôle dont le
client_scope est restreint (cas normal d'un auditeur assigné à des clients précis) ne
peut donc jamais créer d'organisation, même quand la matrice RBAC (couche 1) le permet.

On remplace la politique unique par : SELECT/UPDATE/DELETE inchangés (cloisonnement
strict conservé), et un INSERT séparé qui exige seulement un contexte de sécurité établi
(app.role posé) — le filtrage « qui a le droit de créer » reste entièrement à la charge
de la matrice RBAC (app/security/matrix.py), qui gate déjà l'accès à la route.

Revision ID: 0009_organisation_insert_policy
Revises: 0008_scenario_step_table
"""
from __future__ import annotations

from alembic import op

revision = "0009_organisation_insert_policy"
down_revision = "0008_scenario_step_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_authenticated() RETURNS boolean
          LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.role', true), '') IS NOT NULL
          $$;
        """
    )
    op.execute("DROP POLICY IF EXISTS organisation_rls ON organisation")
    op.execute(
        """
        CREATE POLICY organisation_rls_rw ON organisation
          FOR SELECT
          USING (app_client_visible(id))
        """
    )
    op.execute(
        """
        CREATE POLICY organisation_rls_update ON organisation
          FOR UPDATE
          USING (app_client_visible(id))
          WITH CHECK (app_client_visible(id))
        """
    )
    op.execute(
        """
        CREATE POLICY organisation_rls_delete ON organisation
          FOR DELETE
          USING (app_client_visible(id))
        """
    )
    op.execute(
        """
        CREATE POLICY organisation_rls_insert ON organisation
          FOR INSERT
          WITH CHECK (app_authenticated())
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS organisation_rls_insert ON organisation")
    op.execute("DROP POLICY IF EXISTS organisation_rls_delete ON organisation")
    op.execute("DROP POLICY IF EXISTS organisation_rls_update ON organisation")
    op.execute("DROP POLICY IF EXISTS organisation_rls_rw ON organisation")
    op.execute(
        """
        CREATE POLICY organisation_rls ON organisation
          USING (app_client_visible(id))
          WITH CHECK (app_client_visible(id))
        """
    )
    op.execute("DROP FUNCTION IF EXISTS app_authenticated()")
