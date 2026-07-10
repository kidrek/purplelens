"""Unicité de ext_id sur les tables de référentiel (clé naturelle).

Contexte : `ext_id` (T1566, D3-UAC, A01:2021…) est la clé naturelle d'un référentiel.
Sans contrainte d'unicité, `seed_reference` réinsérait des doublons à chaque exécution
(son ON CONFLICT DO NOTHING ne pouvait matcher aucune contrainte) et l'agrégation de
couverture ATT&CK comptait mal. Les installations NEUVES ont déjà la contrainte
(metadata.create_all reflète le modèle) ; cette migration régularise les bases migrées
AVANT ce changement.

Idempotente :
  1. déduplication (on garde une ligne par ext_id, la plus ancienne par ctid) ;
  2. pose de la contrainte UNIQUE si absente.
"""
from __future__ import annotations

from alembic import op

revision = "0002_ref_ext_id_unique"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

# Toutes les tables héritant de _RefBase (colonne ext_id).
_REF_TABLES = (
    "ref_attack_technique",
    "ref_d3fend",
    "ref_owasp",
    "ref_cwe",
    "ref_capec",
)


def upgrade() -> None:
    for table in _REF_TABLES:
        constraint = f"{table}_ext_id_key"
        # 1. Déduplication : conserver une seule ligne par ext_id.
        op.execute(
            f"DELETE FROM {table} a USING {table} b "
            f"WHERE a.ctid < b.ctid AND a.ext_id = b.ext_id"
        )
        # 2. Contrainte UNIQUE si elle n'existe pas déjà (idempotent).
        op.execute(
            f"""
            DO $$ BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = '{constraint}'
              ) THEN
                ALTER TABLE {table} ADD CONSTRAINT {constraint} UNIQUE (ext_id);
              END IF;
            END $$;
            """
        )


def downgrade() -> None:
    for table in _REF_TABLES:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_ext_id_key")
