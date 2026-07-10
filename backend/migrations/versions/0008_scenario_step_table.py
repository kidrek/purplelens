"""Table scenario_step — chaîne d'étapes offensives d'un scénario (cahier §A00.1).

Le modèle ORM `ScenarioStep` existe déjà (app/models/business.py, table déclarée dans
CLIENT_UNSCOPED_TABLES) et serait créé par `Base.metadata.create_all` sur une base neuve
via la migration 0001 — mais aucune migration explicite ne le matérialise pour une base
déjà existante qui aurait tourné avant l'ajout du modèle. Idempotent : sans effet si la
table existe déjà (base recréée via create_all).

Chaque étape porte { technique, tactique, commande, description } — `tactique` est
renseignable mais son affichage peut aussi être dérivé du référentiel ATT&CK (redondance
tolérée : utile hors-ligne / si le référentiel n'est pas synchronisé pour cette technique).
Pas de RLS (scénario = catalogue CTI global, cf. CLIENT_UNSCOPED_TABLES).

Revision ID: 0008_scenario_step_table
Revises: 0007_vuln_statut_vocab
"""
from __future__ import annotations

from alembic import op

revision = "0008_scenario_step_table"
down_revision = "0007_vuln_statut_vocab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS scenario_step (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          scenario_id uuid NOT NULL REFERENCES scenario(id),
          ordre integer NOT NULL DEFAULT 0,
          technique varchar(16),
          tactique varchar(32),
          commande text,
          description text,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_scenario_step_scenario_id ON scenario_step (scenario_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scenario_step")
