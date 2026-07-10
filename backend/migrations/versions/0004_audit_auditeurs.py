"""Auditeurs assignés à l'audit : colonne auditeurs uuid[].

Comble l'incohérence du cahier : la lettre d'engagement (§5.A) doit être alimentée
par les « Auditeurs assignés », mais aucun champ ne les portait au niveau audit
(l'équipe est sur l'Exercice, l'auteur sur l'Action d'audit). Références vers
`ressource` (type humaine) — pas de FK sur les ARRAY en PostgreSQL, l'intégrité
est validée applicativement (service._validate_audit_links).

Revision ID: 0004_audit_auditeurs
Revises: 0003_enrichment_raw_cache
"""
from __future__ import annotations

from alembic import op

revision = "0004_audit_auditeurs"
down_revision = "0003_enrichment_raw_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent : ne rien casser si la colonne existe déjà (bases recréées via create_all).
    op.execute(
        "ALTER TABLE audit "
        "ADD COLUMN IF NOT EXISTS auditeurs uuid[] NOT NULL DEFAULT '{}'::uuid[]"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE audit DROP COLUMN IF EXISTS auditeurs")
