"""Tables ref_attack_group / ref_misp_actor — catalogue des acteurs de la menace.

Les acteurs (threat actors) alimentent l'autocomplétion « Émuler un threat actor » de la
page Scénarios : sélectionner un acteur importe ses TTPs ATT&CK connues comme étapes. Deux
sources fusionnées côté lecture : MITRE ATT&CK Groups (Gxxxx) et MISP Galaxy threat-actor.

Chaque ligne porte { ext_id (identifiant de l'acteur), name (nom officiel), data JSONB }.
`data` contient {"aliases": [...], "techniques": ["T1566", ...], "source": ...}. L'index
UNIQUE sur ext_id rend l'import/la synchro idempotents (ON CONFLICT DO UPDATE), au même
titre que les autres tables ref_* (cf. migration 0002). Pas de RLS (catalogue global,
tables déclarées dans CLIENT_UNSCOPED_TABLES).

Idempotent (CREATE TABLE IF NOT EXISTS) : sans effet si les tables existent déjà (base
recréée via Base.metadata.create_all en 0001).

Revision ID: 0015_ref_threat_actors
Revises: 0014_scenario_ticket_refs
"""
from __future__ import annotations

from alembic import op

revision = "0015_ref_threat_actors"
down_revision = "0014_scenario_ticket_refs"
branch_labels = None
depends_on = None


def _create(table: str) -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          ext_id varchar(64) NOT NULL,
          name text NOT NULL,
          data jsonb NOT NULL DEFAULT '{{}}',
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS ix_{table}_ext_id ON {table} (ext_id)")


def upgrade() -> None:
    _create("ref_attack_group")
    _create("ref_misp_actor")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ref_misp_actor")
    op.execute("DROP TABLE IF EXISTS ref_attack_group")
