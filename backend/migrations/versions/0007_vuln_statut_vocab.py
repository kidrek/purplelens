"""Vocabulaire de statut des vulnérabilités aligné sur la maquette.

La maquette (cf. capture d'écran fournie) utilise : Ouverte / En cours / Corrigée /
Acceptée / Faux positif — au lieu de l'ancien vocabulaire (nouveau / corrige / accepte /
resolu / ferme). Pas de contrainte CHECK en base (colonne texte libre, cf. modèle) : cette
migration se contente d'aligner le DEFAULT et de rebasculer les lignes existantes qui
portaient encore l'ancien vocabulaire, pour que les filtres de la nouvelle UI (qui ne
proposent plus que les 5 nouvelles valeurs) ne « perdent » pas silencieusement des lignes
existantes. Column non typée : les valeurs inconnues (saisies manuelles diverses) sont
laissées intactes.

Revision ID: 0007_vuln_statut_vocab
Revises: 0006_vuln_decouvreur_id
"""
from __future__ import annotations

from alembic import op

revision = "0007_vuln_statut_vocab"
down_revision = "0006_vuln_decouvreur_id"
branch_labels = None
depends_on = None

_MAP = {
    "nouveau": "ouverte",
    "corrige": "corrigee",
    "accepte": "acceptee",
    "resolu": "corrigee",
    "ferme": "corrigee",
}


def upgrade() -> None:
    op.execute("ALTER TABLE vulnerability ALTER COLUMN statut SET DEFAULT 'ouverte'")
    for old, new in _MAP.items():
        op.execute(
            f"UPDATE vulnerability SET statut = '{new}' WHERE statut = '{old}'"
        )


def downgrade() -> None:
    op.execute("ALTER TABLE vulnerability ALTER COLUMN statut SET DEFAULT 'nouveau'")
    # Downgrade best-effort (la correspondance resolu/ferme -> corrigee n'est pas
    # réversible de façon univoque ; on retombe sur 'corrige' pour les deux).
    op.execute("UPDATE vulnerability SET statut = 'corrige' WHERE statut = 'corrigee'")
    op.execute("UPDATE vulnerability SET statut = 'accepte' WHERE statut = 'acceptee'")
    op.execute("UPDATE vulnerability SET statut = 'nouveau' WHERE statut = 'ouverte'")
