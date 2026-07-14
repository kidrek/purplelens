"""RLS : scope vide fail-closed (durcissement P1).

Jusqu'ici `app_client_visible` traitait un `client_scope` VIDE comme « tous les clients »
pour N'IMPORTE QUEL rôle authentifié. Un rôle censé être cloisonné (auditeur, ciso, voc,
cert) dont le token porterait par erreur un scope vide obtenait alors un accès multi-tenant
silencieux — la couche 2 (RLS) échouait ouvert.

On introduit `app_role_spans_all_clients()` (miroir SQL de matrix.GLOBAL_SCOPE_ROLES) et on
réécrit `app_client_visible` : un scope vide n'ouvre l'accès global QUE pour admin/manager
et les rôles de service ; pour tout autre rôle, scope vide ⇒ aucune ligne visible.

Revision ID: 0011_scope_fail_closed
Revises: 0010_org_insert_role_guard
"""
from __future__ import annotations

from alembic import op

revision = "0011_scope_fail_closed"
down_revision = "0010_org_insert_role_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_role_spans_all_clients() RETURNS boolean
          LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.role', true), '') IN (
              'admin', 'manager',
              'report_render', 'job_retention', 'job_integrity', 'admin_service'
            )
          $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_client_visible(cid uuid) RETURNS boolean
          LANGUAGE sql STABLE AS $$
            SELECT
              NULLIF(current_setting('app.role', true), '') IS NOT NULL
              AND (
                cid = ANY (app_client_scope())
                OR (cardinality(app_client_scope()) = 0 AND app_role_spans_all_clients())
              )
          $$;
        """
    )


def downgrade() -> None:
    # Revient au comportement historique (scope vide = tous, pour tout rôle établi).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_client_visible(cid uuid) RETURNS boolean
          LANGUAGE sql STABLE AS $$
            SELECT
              NULLIF(current_setting('app.role', true), '') IS NOT NULL
              AND (
                cardinality(app_client_scope()) = 0
                OR cid = ANY (app_client_scope())
              )
          $$;
        """
    )
    op.execute("DROP FUNCTION IF EXISTS app_role_spans_all_clients()")
