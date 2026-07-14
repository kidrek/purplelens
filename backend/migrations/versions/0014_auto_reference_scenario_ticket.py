"""Références auto-générées pour scénarios et tickets de détection (cahier §6.1).

Ajoute les colonnes `reference` / `period` / `seq` à `scenario` et `detection_ticket`
pour porter un identifiant métier figé à la création, au même titre que les audits,
vulnérabilités et exercices Purple (qui portent déjà nom|titre/period/seq) :
  - scénario         → SCEN_{AAAAMM}-{NN}                              (catalogue CTI global)
  - detection_ticket → TICK_{AAAAMM}-{NN}_{CLIENT}_{APP}_{TECHNIQUE}   (client/app de l'audit lié)

Idempotent (ADD COLUMN IF NOT EXISTS) : sans effet si les colonnes existent déjà
(base recréée via Base.metadata.create_all en 0001). Les lignes existantes gardent
`reference` NULL — l'affichage retombe sur `nom` / la technique.

Revision ID: 0014_scenario_ticket_refs
Revises: 0013_org_create_service_role

NB : l'identifiant de révision est volontairement court (≤ 32 car.) car la colonne
``alembic_version.version_num`` est un ``varchar(32)`` — un id plus long échoue à
l'écriture de la version. Le nom de fichier peut être aligné (``git mv``) plus tard.
"""
from __future__ import annotations

from alembic import op

revision = "0014_scenario_ticket_refs"
down_revision = "0013_org_create_service_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE scenario
          ADD COLUMN IF NOT EXISTS reference text,
          ADD COLUMN IF NOT EXISTS period varchar(8),
          ADD COLUMN IF NOT EXISTS seq integer
        """
    )
    op.execute(
        """
        ALTER TABLE detection_ticket
          ADD COLUMN IF NOT EXISTS reference text,
          ADD COLUMN IF NOT EXISTS period varchar(8),
          ADD COLUMN IF NOT EXISTS seq integer
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE detection_ticket DROP COLUMN IF EXISTS reference, DROP COLUMN IF EXISTS period, DROP COLUMN IF EXISTS seq")
    op.execute("ALTER TABLE scenario DROP COLUMN IF EXISTS reference, DROP COLUMN IF EXISTS period, DROP COLUMN IF EXISTS seq")
