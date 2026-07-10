"""Lien Vulnérabilité -> Audit : colonne audit_id (nullable).

Comble le constat « pas de possibilité d'ajouter un audit lors de l'ajout d'une
vulnérabilité, pour faire le lien ». Nullable : une vulnérabilité peut être remontée
hors d'un audit formel (VOC, signalement direct). Pas de ON DELETE CASCADE : la
suppression d'un audit ne doit jamais entraîner la perte silencieuse de vulnérabilités
réelles (le lien est simplement détaché applicativement si besoin).

Revision ID: 0005_vuln_audit_link
Revises: 0004_audit_auditeurs
"""
from __future__ import annotations

from alembic import op

revision = "0005_vuln_audit_link"
down_revision = "0004_audit_auditeurs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent : ne rien casser si la colonne existe déjà (bases recréées via create_all).
    op.execute(
        "ALTER TABLE vulnerability "
        "ADD COLUMN IF NOT EXISTS audit_id uuid NULL REFERENCES audit(id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vulnerability_audit_id ON vulnerability (audit_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_vulnerability_audit_id")
    op.execute("ALTER TABLE vulnerability DROP COLUMN IF EXISTS audit_id")
