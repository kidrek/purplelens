"""Cache d'enrichissement CIRCL sur le finding : colonne raw JSONB.

Stocke le sous-ensemble exploitable renvoyé par Vulnerability-Lookup qui n'a pas de
colonne dédiée (CAPEC, références, produits, variantes CVSS 3.1/4.0). Ainsi l'enrichissement
reste disponible hors-ligne après un premier appel, conformément au cahier (§6, A.2).

Revision ID: 0003_enrichment_raw_cache
Revises: 0002_ref_ext_id_unique
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_enrichment_raw_cache"
down_revision = "0002_ref_ext_id_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent : ne rien casser si la colonne existe déjà (bases recréées via create_all).
    op.execute(
        "ALTER TABLE vulnerability_enrichment "
        "ADD COLUMN IF NOT EXISTS raw JSONB NOT NULL DEFAULT '{}'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE vulnerability_enrichment DROP COLUMN IF EXISTS raw")


# Silence les avertissements de linters sur les imports non utilisés dans certains contextes.
_ = (sa, JSONB)
