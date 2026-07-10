"""Découvreur d'une vulnérabilité : colonne decouvreur_id (lien vers ressource).

Comble le constat « faire en sorte de pouvoir rechercher une ressource de type
auditeur ou voc » pour le champ Découvreur — jusqu'ici un champ texte libre, non
rattaché à une ressource réelle. L'ancienne colonne texte `decouvreur` est conservée
telle quelle (historique, non nettoyée) mais n'est plus alimentée par le formulaire ;
seule `decouvreur_id` est désormais éditable (cf. registry.py).

Revision ID: 0006_vuln_decouvreur_id
Revises: 0005_vuln_audit_link
"""
from __future__ import annotations

from alembic import op

revision = "0006_vuln_decouvreur_id"
down_revision = "0005_vuln_audit_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE vulnerability "
        "ADD COLUMN IF NOT EXISTS decouvreur_id uuid NULL REFERENCES ressource(id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vulnerability_decouvreur_id ON vulnerability (decouvreur_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_vulnerability_decouvreur_id")
    op.execute("ALTER TABLE vulnerability DROP COLUMN IF EXISTS decouvreur_id")
