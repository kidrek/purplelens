"""RLS organisation : autoriser le rôle de service à créer des organisations (fix P1).

La 0010 avait restreint l'INSERT `organisation` à ('admin', 'auditeur'), oubliant le
rôle de service `admin_service` sous lequel tournent le seed, l'import et l'amorçage
(auth_session / service_session). Résultat : ces opérations d'automatisation — pourtant
légitimes — étaient refusées par la RLS (« new row violates row-level security policy »).

On redéfinit `app_role_may_create_org()` pour inclure `admin_service`. Les rôles
interactifs restent gated par la matrice (porte 3) ; le rôle de service opère hors matrice
et doit pouvoir provisionner les organisations.

Revision ID: 0013_org_create_service_role
Revises: 0012_totp_replay_guard
"""
from __future__ import annotations

from alembic import op

revision = "0013_org_create_service_role"
down_revision = "0012_totp_replay_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_role_may_create_org() RETURNS boolean
          LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.role', true), '') IN
              ('admin', 'auditeur', 'admin_service')
          $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_role_may_create_org() RETURNS boolean
          LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.role', true), '') IN ('admin', 'auditeur')
          $$;
        """
    )
