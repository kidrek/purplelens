"""RLS organisation : durcissement de la politique INSERT (défense en profondeur).

0009 a ouvert l'INSERT sur `organisation` à tout contexte de sécurité établi
(`app_authenticated()`) parce qu'une organisation neuve — dont la colonne de portée
EST sa propre clé primaire (UUID frais) — ne peut par construction appartenir à
aucun `client_scope` existant. Mais `app_authenticated()` est plus PERMISSIF que la
matrice RBAC : la couche 2 (RLS) doit rester une *seconde barrière* au moins aussi
stricte que la couche 1 (matrice), jamais plus large. Or seuls `admin` et `auditeur`
portent le droit `organisations:C` (cf. app/security/matrix.py). Un rôle scoppé
(`manager`, `ciso`, `voc`, `cert`) ne doit JAMAIS pouvoir créer un tenant, même si un
défaut d'appel à `require()` contournait la porte 3.

On resserre donc le `WITH CHECK` de l'INSERT pour qu'il exige, en plus d'un contexte
établi, que `app.role` figure parmi les rôles créateurs d'organisation — miroir exact
de la matrice, appliqué au niveau SQL. `app.role` provient du contexte vérifié posé
par l'application (SET LOCAL, cf. app/db/session.py) sur un rôle NOBYPASSRLS.

Revision ID: 0010_org_insert_role_guard
Revises: 0009_organisation_insert_policy

Note : l'identifiant de révision est volontairement court (« org » et non
« organisation ») — la colonne alembic_version.version_num est un VARCHAR(32).
"""
from __future__ import annotations

from alembic import op

revision = "0010_org_insert_role_guard"
down_revision = "0009_organisation_insert_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rôles autorisés à créer une organisation : les créateurs interactifs de la
    # matrice (organisations:C = 'admin', 'auditeur') PLUS le rôle de service
    # 'admin_service', sous lequel tournent le seed, l'import et l'amorçage (ces
    # opérations d'automatisation créent légitimement des organisations, hors matrice).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_role_may_create_org() RETURNS boolean
          LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.role', true), '') IN
              ('admin', 'auditeur', 'admin_service')
          $$;
        """
    )
    op.execute("DROP POLICY IF EXISTS organisation_rls_insert ON organisation")
    op.execute(
        """
        CREATE POLICY organisation_rls_insert ON organisation
          FOR INSERT
          WITH CHECK (app_authenticated() AND app_role_may_create_org())
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS organisation_rls_insert ON organisation")
    op.execute(
        """
        CREATE POLICY organisation_rls_insert ON organisation
          FOR INSERT
          WITH CHECK (app_authenticated())
        """
    )
    op.execute("DROP FUNCTION IF EXISTS app_role_may_create_org()")
