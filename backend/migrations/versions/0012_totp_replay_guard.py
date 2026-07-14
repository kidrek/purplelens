"""Anti-rejeu TOTP (durcissement P1).

`verify_totp` accepte un code dans une fenêtre glissante (±1 pas de 30 s). Sans mémoire
du dernier pas consommé, un code TOTP intercepté (shoulder-surfing, proxy, log) reste
rejouable pendant toute sa fenêtre de validité. On ajoute `last_totp_step` : l'index du
dernier pas de temps TOTP accepté pour l'utilisateur. Toute présentation d'un code dont
le pas est ≤ `last_totp_step` est refusée (rejeu).

Revision ID: 0012_totp_replay_guard
Revises: 0011_scope_fail_closed
"""
from __future__ import annotations

from alembic import op

revision = "0012_totp_replay_guard"
down_revision = "0011_scope_fail_closed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS : idempotent — tolère une base où la colonne aurait déjà été
    # matérialisée hors migration (create_all au démarrage sur une base pré-existante).
    op.execute("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS last_totp_step BIGINT")


def downgrade() -> None:
    op.execute("ALTER TABLE app_user DROP COLUMN IF EXISTS last_totp_step")
